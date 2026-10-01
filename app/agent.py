"""Agent orchestration loop with tool calling, memory, self-correction, and hallucination verification."""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Set
import numpy as np
import pandas as pd

from app.config import settings
from app.data.profiler import TableProfile
from app.llm.base import LLMMessage, LLMProvider, ToolCall
from app.llm.prompts import TOOLS_DEFINITION, build_system_prompt
from app.tools.pandas_tool import PandasSandboxError, execute_sandboxed_pandas
from app.tools.sql_tool import DuckDBManager, SQLExecutionError, SQLSecurityError
from app.utils.logging import get_logger

logger = get_logger()

@dataclass
class AgentTurnResult:
    """Outcome of a single user turn in the agent conversation."""
    answer: str
    insights: List[str] = field(default_factory=list)
    reasoning: str = ""
    unsupported_numbers: List[str] = field(default_factory=list)
    chart_spec: Optional[Dict[str, Any]] = None
    sql_executed: Optional[str] = None
    pandas_executed: Optional[str] = None
    data_preview: Optional[pd.DataFrame] = None
    tool_calls_made: List[str] = field(default_factory=list)
    iterations_used: int = 0
    total_tokens_used: int = 0

def verify_answer_numbers(text: str, result_df: Optional[pd.DataFrame]) -> List[str]:
    """
    Extract numbers mentioned in the answer and verify whether they exist
    in the tool output DataFrame. Returns any unsupported numbers.
    """
    # Remove commas in numbers (e.g. 1,450.00 -> 1450.00)
    cleaned = re.sub(r"(?<=\d),(?=\d)", "", text)
    tokens = re.findall(r"\b\d+\.?\d*\b", cleaned)

    # Gather numeric values from result_df if provided
    df_numbers: Set[float] = set()
    if result_df is not None and not result_df.empty:
        for col in result_df.columns:
            for val in result_df[col].dropna():
                try:
                    num = float(val)
                    df_numbers.add(round(num, 2))
                    df_numbers.add(float(int(num)))
                except (ValueError, TypeError):
                    pass

    # Exclude common small counting numbers and current calendar years
    safe_common = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 100.0, 2023.0, 2024.0, 2025.0, 2026.0}
    unsupported = []

    for token in tokens:
        try:
            val = float(token)
            if val in safe_common:
                continue
            if round(val, 2) not in df_numbers and float(int(val)) not in df_numbers:
                norm_str = str(int(val)) if val.is_integer() else token
                unsupported.append(norm_str)
        except ValueError:
            continue

    return list(dict.fromkeys(unsupported))

class DataAnalystAgent:
    """Autonomous data analyst agent managing multi-turn dialogue, tool execution, and self-correction."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        db_manager: DuckDBManager,
        table_profiles: Dict[str, TableProfile],
        max_iterations: Optional[int] = None,
    ):
        self.llm = llm_provider
        self.db = db_manager
        self.table_profiles = table_profiles
        self.max_iterations = max_iterations or settings.max_tool_iterations

        # Session memory
        self.conversation_history: List[LLMMessage] = []
        self.last_result_df: Optional[pd.DataFrame] = None
        self.last_sql: Optional[str] = None
        self.last_pandas: Optional[str] = None
        self.last_chart_spec: Optional[Dict[str, Any]] = None

        # Initialize system prompt
        self._system_prompt = build_system_prompt(self.table_profiles)
        self.conversation_history.append(LLMMessage(role="system", content=self._system_prompt))

    def _truncate_df_for_llm(self, df: pd.DataFrame, max_rows: Optional[int] = None) -> str:
        """Format DataFrame into token-budgeted, data-tagged string."""
        if max_rows is None:
            max_rows = settings.max_llm_result_rows

        if df.empty:
            return "<data>\n[Empty result: 0 rows returned]\n</data>"

        total_rows = len(df)
        preview = df.head(max_rows)
        table_str = preview.to_string(index=False)

        info = f"[Showing {min(total_rows, max_rows)} of {total_rows} rows]\n" if total_rows > max_rows else ""
        return f"<data>\n{info}{table_str}\n</data>"

    def _execute_tool(self, tool_call: ToolCall) -> Tuple[str, Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
        """
        Execute an individual tool call and return (tool_response_text, result_df, chart_spec).
        """
        name = tool_call.name
        args = tool_call.arguments
        logger.info(f"Agent executing tool '{name}' with args={args}")

        if name == "run_sql":
            query = args.get("query", "")
            try:
                res = self.db.execute_query(query)
                self.last_result_df = res.df
                self.last_sql = res.sql
                formatted = self._truncate_df_for_llm(res.df)
                return formatted, res.df, None
            except (SQLSecurityError, SQLExecutionError) as err:
                logger.warning(f"SQL execution error for tool call: {err}")
                return f"<error>\nSQL Error: {str(err)}\nPlease review table columns and syntax, correct the query, and retry.\n</error>", None, None

        elif name == "run_pandas":
            code = args.get("code", "")
            dfs: Dict[str, pd.DataFrame] = {}
            for t_name in self.db.list_tables():
                df = self.db.get_dataframe(t_name)
                if df is not None:
                    dfs[t_name] = df
            try:
                res_df = execute_sandboxed_pandas(code, dfs)
                self.last_result_df = res_df
                self.last_pandas = code
                formatted = self._truncate_df_for_llm(res_df)
                return formatted, res_df, None
            except PandasSandboxError as err:
                logger.warning(f"Pandas execution error for tool call: {err}")
                return f"<error>\nPandas Error: {str(err)}\nPlease correct your code and retry.\n</error>", None, None

        elif name == "make_chart":
            chart_spec = {
                "chart_type": args.get("chart_type"),
                "x": args.get("x"),
                "y": args.get("y"),
                "title": args.get("title"),
                "color": args.get("color"),
            }
            self.last_chart_spec = chart_spec
            return "<data>\nChart specification successfully recorded and generated.\n</data>", None, chart_spec

        elif name == "detect_anomalies":
            table = args.get("table", "")
            cols = args.get("columns", [])
            df = self.db.get_dataframe(table)
            if df is None:
                return f"<error>Table '{table}' not found.</error>", None, None

            from app.tools.anomaly_tool import detect_anomalies_pipeline
            anom_df, summary = detect_anomalies_pipeline(df, cols)
            self.last_result_df = anom_df
            return f"<data>\n{summary}\n{self._truncate_df_for_llm(anom_df)}\n</data>", anom_df, None

        elif name == "data_quality_report":
            table = args.get("table", "")
            df = self.db.get_dataframe(table)
            if df is None:
                return f"<error>Table '{table}' not found.</error>", None, None

            from app.tools.quality_tool import generate_quality_report
            report_text, report_df = generate_quality_report(df, table)
            self.last_result_df = report_df
            return f"<data>\n{report_text}\n</data>", report_df, None

        else:
            return f"<error>Unknown tool: '{name}'</error>", None, None

    def _format_final_response(
        self,
        raw_content: Optional[str],
        data_preview: Optional[pd.DataFrame],
        sql_executed: Optional[str],
        pandas_executed: Optional[str],
        chart_spec: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[str], str, List[str]]:
        """
        Parse structured JSON response from LLM and assemble standardized 5-part output.
        """
        raw_text = (raw_content or "").strip()
        answer = raw_text
        insights: List[str] = []
        reasoning = ""

        # Attempt parsing JSON object
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                answer = parsed.get("answer", raw_text)
                insights = parsed.get("insights", [])
                reasoning = parsed.get("reasoning", "")
            except Exception:
                pass

        # Verify numbers in answer against tool output
        unsupported = verify_answer_numbers(answer, data_preview)

        # Assemble standardized 5-part markdown
        parts = [
            f"### 1. Direct Answer\n{answer}\n",
        ]

        if insights:
            insights_str = "\n".join([f"- {item}" for item in insights])
            parts.append(f"### 2. Key Insights\n{insights_str}\n")
        elif "### 2. Key Insights" in raw_text:
            pass  # Already formatted in raw text
        else:
            parts.append("### 2. Key Insights\n- Key figures computed and presented above.\n")

        if chart_spec:
            chart_type = chart_spec.get("chart_type", "chart").title()
            title = chart_spec.get("title", "")
            parts.append(f"### 3. Visualizations\nGenerated interactive {chart_type} chart: *{title}*\n")
        else:
            parts.append("### 3. Visualizations\nNo visualization requested for this query.\n")

        if sql_executed:
            parts.append(f"### 4. Code Used\n```sql\n{sql_executed}\n```\n")
        elif pandas_executed:
            parts.append(f"### 4. Code Used\n```python\n{pandas_executed}\n```\n")
        else:
            parts.append("### 4. Code Used\nNo database query executed.\n")

        if reasoning:
            parts.append(f"### 5. How I Got This\n{reasoning}\n")
        elif "### 5. How I Got This" in raw_text:
            pass
        else:
            parts.append("### 5. How I Got This\nExtracted directly from registered dataset tables.\n")

        if unsupported:
            parts.append(
                f"> [!CAUTION]\n> **Data Grounding Warning**: The following numbers quoted in the answer could not be verified in the query result: {', '.join(unsupported)}.\n"
            )

        full_formatted = "\n".join(parts)
        return full_formatted, insights, reasoning, unsupported

    def ask(self, user_question: str) -> AgentTurnResult:
        """
        Main multi-turn agent entry point.
        Executes reasoning loop with tool calling up to max_iterations.
        """
        logger.info(f"User asked: {user_question}")

        user_msg = LLMMessage(role="user", content=user_question)
        self.conversation_history.append(user_msg)

        tools_executed: List[str] = []
        turn_chart_spec: Optional[Dict[str, Any]] = None
        turn_data_preview: Optional[pd.DataFrame] = None
        turn_sql: Optional[str] = None
        turn_pandas: Optional[str] = None
        total_tokens = 0

        for iteration in range(1, self.max_iterations + 1):
            logger.debug(f"Agent iteration {iteration}/{self.max_iterations}")

            response = self.llm.generate(
                messages=self.conversation_history,
                tools=TOOLS_DEFINITION,
            )
            total_tokens += response.usage.total_tokens

            if response.tool_calls:
                assistant_msg = LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                self.conversation_history.append(assistant_msg)

                for tc in response.tool_calls:
                    tools_executed.append(tc.name)
                    tool_output, result_df, chart_spec = self._execute_tool(tc)

                    if result_df is not None:
                        turn_data_preview = result_df
                    if chart_spec is not None:
                        turn_chart_spec = chart_spec
                    if tc.name == "run_sql":
                        turn_sql = self.last_sql
                    elif tc.name == "run_pandas":
                        turn_pandas = self.last_pandas

                    tool_msg = LLMMessage(
                        role="tool",
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=tool_output,
                    )
                    self.conversation_history.append(tool_msg)

                continue

            else:
                final_data_preview = turn_data_preview if turn_data_preview is not None else self.last_result_df
                final_sql = turn_sql if turn_sql is not None else self.last_sql
                final_pandas = turn_pandas if turn_pandas is not None else self.last_pandas
                final_chart_spec = turn_chart_spec if turn_chart_spec is not None else self.last_chart_spec

                full_answer, insights, reasoning, unsupported = self._format_final_response(
                    raw_content=response.content,
                    data_preview=final_data_preview,
                    sql_executed=final_sql,
                    pandas_executed=final_pandas,
                    chart_spec=final_chart_spec,
                )

                self.conversation_history.append(LLMMessage(role="assistant", content=full_answer))

                return AgentTurnResult(
                    answer=full_answer,
                    insights=insights,
                    reasoning=reasoning,
                    unsupported_numbers=unsupported,
                    chart_spec=final_chart_spec,
                    sql_executed=final_sql,
                    pandas_executed=final_pandas,
                    data_preview=final_data_preview,
                    tool_calls_made=tools_executed,
                    iterations_used=iteration,
                    total_tokens_used=total_tokens,
                )

        fallback_answer = (
            "I reached the maximum analysis steps for this question. "
            "Here is the data obtained from the executed queries above."
        )
        final_data_preview = turn_data_preview if turn_data_preview is not None else self.last_result_df
        return AgentTurnResult(
            answer=fallback_answer,
            chart_spec=turn_chart_spec if turn_chart_spec is not None else self.last_chart_spec,
            sql_executed=turn_sql if turn_sql is not None else self.last_sql,
            pandas_executed=turn_pandas if turn_pandas is not None else self.last_pandas,
            data_preview=final_data_preview,
            tool_calls_made=tools_executed,
            iterations_used=self.max_iterations,
            total_tokens_used=total_tokens,
        )
