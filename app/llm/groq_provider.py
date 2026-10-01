"""Groq API provider implementation with exponential backoff and automatic model fallback."""

import json
import random
import time
from typing import Any, Dict, List, Optional
from groq import APIConnectionError, APIError, Groq, InternalServerError, RateLimitError

from app.config import settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, TokenUsage, ToolCall
from app.utils.logging import get_logger

logger = get_logger()

class GroqProvider(LLMProvider):
    """Production Groq LLM provider featuring retry backoff, error correction, and fallback models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.api_key = api_key or settings.groq_api_key
        self.primary_model = model or settings.groq_model
        self.fallback_model = fallback_model or settings.groq_fallback_model
        self.max_retries = max_retries
        self._current_model = self.primary_model

        if self.api_key and self.api_key != "your_groq_api_key_here":
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

    def get_model_name(self) -> str:
        return self._current_model

    def _convert_messages_to_groq_format(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert internal LLMMessage list to Groq/OpenAI compatible JSON payload."""
        groq_messages: List[Dict[str, Any]] = []

        for m in messages:
            msg_dict: Dict[str, Any] = {"role": m.role}

            if m.content is not None:
                msg_dict["content"] = m.content

            if m.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]

            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            if m.name:
                msg_dict["name"] = m.name

            groq_messages.append(msg_dict)

        return groq_messages

    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """
        Execute chat completion with exponential backoff on 429 and fallback model switching.
        """
        if not self.client:
            raise ValueError(
                "Groq API key is not configured. Please set the GROQ_API_KEY environment variable or enter it in the app sidebar."
            )

        groq_msgs = self._convert_messages_to_groq_format(messages)
        models_to_try = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        last_error: Optional[Exception] = None

        for attempt_model in models_to_try:
            backoff_delay = 2.0
            for attempt in range(1, self.max_retries + 1):
                try:
                    kwargs: Dict[str, Any] = {
                        "model": attempt_model,
                        "messages": groq_msgs,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if tools:
                        kwargs["tools"] = tools
                        kwargs["tool_choice"] = "auto"

                    logger.debug(f"Calling Groq model='{attempt_model}' (attempt {attempt})")
                    completion = self.client.chat.completions.create(**kwargs)

                    # Parse choice and tool calls
                    choice = completion.choices[0]
                    message = choice.message

                    parsed_tool_calls: List[ToolCall] = []
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            args = {}
                            if tc.function.arguments:
                                try:
                                    args = json.loads(tc.function.arguments)
                                except Exception:
                                    args = {"raw_arguments": tc.function.arguments}

                            parsed_tool_calls.append(
                                ToolCall(
                                    id=tc.id,
                                    name=tc.function.name,
                                    arguments=args,
                                )
                            )

                    # Track usage
                    usage = TokenUsage()
                    if completion.usage:
                        usage.prompt_tokens = completion.usage.prompt_tokens
                        usage.completion_tokens = completion.usage.completion_tokens
                        usage.total_tokens = completion.usage.total_tokens

                    logger.info(
                        f"Groq API call succeeded ({attempt_model}). Tokens: "
                        f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}"
                    )
                    self._current_model = attempt_model

                    return LLMResponse(
                        content=message.content,
                        tool_calls=parsed_tool_calls,
                        usage=usage,
                        model=attempt_model,
                    )

                except RateLimitError as rle:
                    last_error = rle
                    logger.warning(
                        f"Groq rate limit (429) on '{attempt_model}' (attempt {attempt}/{self.max_retries}): {rle}"
                    )
                    if attempt < self.max_retries:
                        sleep_time = backoff_delay + random.uniform(0.5, 1.5)
                        logger.info(f"Sleeping for {sleep_time:.2f}s before retry...")
                        time.sleep(sleep_time)
                        backoff_delay *= 2.0
                    else:
                        logger.warning(f"Exhausted retries on model: {attempt_model}")
                        break

                except (APIConnectionError, InternalServerError) as conn_err:
                    last_error = conn_err
                    logger.warning(f"Groq connection or server error: {conn_err}. Attempt {attempt}")
                    if attempt < self.max_retries:
                        time.sleep(backoff_delay)
                        backoff_delay *= 2.0
                    else:
                        break

                except APIError as api_err:
                    last_error = api_err
                    err_str = str(api_err).lower()
                    if "tool_use_failed" in err_str or "tool" in err_str:
                        logger.warning(f"Groq tool call formatting error: {api_err}. Retrying once...")
                        if attempt == 1:
                            groq_msgs.append({
                                "role": "user",
                                "content": "Please format all tool arguments strictly as valid JSON.",
                            })
                            continue
                    logger.error(f"Groq API error: {api_err}")
                    raise RuntimeError(f"Groq API error: {str(api_err)}") from api_err

        raise RuntimeError(
            f"Failed to obtain response from Groq API after multiple attempts. Last error: {last_error}"
        )
