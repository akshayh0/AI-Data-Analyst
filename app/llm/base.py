"""Abstract Base Class and data contracts for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ToolCall:
    """Represents a tool call requested by the model."""
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class TokenUsage:
    """Token consumption statistics for an LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class LLMMessage:
    """Normalized message representation across providers."""
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

@dataclass
class LLMResponse:
    """Structured response from an LLM provider."""
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""

class LLMProvider(ABC):
    """Abstract interface for swappable LLM providers."""

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """
        Execute an inference call with optional tool definitions.

        Parameters:
            messages: List of conversation messages.
            tools: OpenAI/Groq compatible list of tool definitions.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            LLMResponse containing text content and/or tool calls.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the active model identifier."""
        pass
