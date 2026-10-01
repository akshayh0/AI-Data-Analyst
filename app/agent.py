"""Agent orchestration loop with tool calling, memory, self-correction, and result caching."""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Tuple
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
    chart_spec: Optional[Dict[str, Any]] = None
    sql_executed: Optional[str] = None
    pandas_executed: Optional[str] = None
    data_preview: Optional[pd.DataFrame] = None
    tool_calls_made: List[str] = field(default_factory=list)
    iterations_used: int = 0
    total_tokens_used: int = 0

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
                return f"<error>\nSQL Error: {str(err)}\nPlease review the table columns and syntax, correct the query, and retry.\n</error>", None, None

        elif name == "run_pandas":
            code = args.get("code", "")
            # Gather all registered DataFrames
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
            # Delegate to anomaly detector
            table = args.get("table", "")
            cols = args.get("columns", [])
            df = self.db.get_dataframe(table)
            if df is None:
                return f"<error>Table '{table}' not found.</error>", None, None

            # Simple fallback anomaly output for agent loop if module not yet imported
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

    def ask(self, user_question: str) -> AgentTurnResult:
        """
        Main multi-turn agent entry point.
        Executes reasoning loop with tool calling up to max_iterations.
        """
        logger.info(f"User asked: {user_question}")

        # Add user message to conversation history
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

            # Call LLM
            response = self.llm.generate(
                messages=self.conversation_history,
                tools=TOOLS_DEFINITION,
            )
            total_tokens += response.usage.total_tokens

            # If model produced tool calls
            if response.tool_calls:
                # Add assistant message with tool calls to history
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

                    # Add tool response to history
                    tool_msg = LLMMessage(
                        role="tool",
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=tool_output,
                    )
                    self.conversation_history.append(tool_msg)

                # Continue loop to allow model to observe tool outputs or call more tools
                continue

            else:
                # Model produced final text answer without further tool calls
                final_answer = response.content or "No response generated."
                self.conversation_history.append(LLMMessage(role="assistant", content=final_answer))

                final_data_preview = turn_data_preview if turn_data_preview is not None else self.last_result_df

                return AgentTurnResult(
                    answer=final_answer,
                    chart_spec=turn_chart_spec if turn_chart_spec is not None else self.last_chart_spec,
                    sql_executed=turn_sql if turn_sql is not None else self.last_sql,
                    pandas_executed=turn_pandas if turn_pandas is not None else self.last_pandas,
                    data_preview=final_data_preview,
                    tool_calls_made=tools_executed,
                    iterations_used=iteration,
                    total_tokens_used=total_tokens,
                )

        # Max iterations reached without final text output
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
