"""Datalens Answer Card component: Structured presentation of answers, insights, charts, and code."""

import re
from typing import Any, Dict, Optional
import pandas as pd
import streamlit as st

from app.agent import AgentTurnResult
from app.tools.chart_tool import build_plotly_chart
from app.ui.theme import apply_datalens_chart_styling

def extract_primary_metric(text: str) -> Optional[str]:
    """Find a primary headline figure (currency, percentage, or large number) from answer text."""
    # Match currency like $674,429.67 or $1.2M
    curr_match = re.search(r"(\$[\d,]+(?:\.\d+)?\s*(?:[KkMmBb])?)", text)
    if curr_match:
        return curr_match.group(1).strip()
    return None

def render_answer_card(result: AgentTurnResult, card_index: int = 0):
    """
    Render modern SaaS 5-part answer card matching specification:
    - Engine & latency badges
    - Direct Answer
    - Headline Metric (if present)
    - Key Insights
    - Plotly Chart (in clean card)
    - SQL Section with execution state & download/copy
    - Safe "How I got this" reasoning steps
    - Data Preview with row count & CSV export
    """
    with st.container(border=True):

        # 1. Header with execution badges
        if result.sql_executed:
            engine_label = "DuckDB"
        elif result.pandas_executed:
            engine_label = "Pandas"
        elif any("anom" in tc for tc in result.tool_calls_made):
            engine_label = "Anomaly Ensemble"
        else:
            engine_label = "Analytical Agent"

        time_str = f"{result.execution_time_ms:.1f}ms" if result.execution_time_ms > 0 else "Instant"
        steps_str = f"{result.iterations_used} steps" if result.iterations_used else "1 step"

        st.markdown(
            f"""
            <div class="answer-card-header">
                <div class="answer-card-engine">
                    <span style="font-family: var(--font-heading); font-size: 0.75rem; font-weight: 700; color: #64748B; letter-spacing: 0.05em; text-transform: uppercase;">AI Analysis</span>
                    <span class="badge-teal">{engine_label} · {time_str}</span>
                </div>
                <div class="answer-meta">
                    <span class="badge-stone">{steps_str}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. Direct Answer
        answer_text = result.answer
        if "### 1. Direct Answer" in answer_text:
            parts = re.split(r"### \d+\.\s+", answer_text)
            if len(parts) > 1 and parts[1].strip():
                answer_text = parts[1].strip()
            else:
                answer_text = answer_text.replace("### 1. Direct Answer", "").split("### 2. Key Insights")[0].strip()

        # Clean any redundant leading "Direct Answer" prefix
        answer_text = re.sub(r"^(?:###\s*\d+\.\s*)?Direct Answer[:\s]*", "", answer_text, flags=re.IGNORECASE).strip()

        st.markdown(f"<div class='answer-direct-text'>{answer_text}</div>", unsafe_allow_html=True)

        # Prominent primary metric callout if available
        primary_metric = extract_primary_metric(answer_text)
        if primary_metric:
            st.markdown(f"<div class='answer-metric-callout'>{primary_metric}</div>", unsafe_allow_html=True)

        # 3. Key Insights
        if result.insights:
            insights_html = "".join([f"<li style='margin-bottom: 0.35rem;'>{item}</li>" for item in result.insights])
            st.markdown(
                f"""
                <div class="answer-insights-box">
                    <div class="answer-insights-title">Key Insights</div>
                    <ul class="answer-insights-list">{insights_html}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Data Grounding Warning (if any unsupported numbers were flagged)
        if result.unsupported_numbers:
            st.markdown(
                f"""
                <div style="background-color: #FFFBEB; border: 1px solid #FDE68A; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #92400E; margin-bottom: 0.85rem;">
                    <strong>Grounding Notice:</strong> Some numbers could not be verified directly against query results: {', '.join(result.unsupported_numbers)}.
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 4. Visual Analytics / Plotly Chart (Inside Clean Card)
        if result.chart_spec and result.data_preview is not None and not result.data_preview.empty:
            with st.container(border=True):
                try:
                    fig = build_plotly_chart(result.chart_spec, result.data_preview)
                    fig = apply_datalens_chart_styling(fig)
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        key=f"chart_{card_index}_{result.chart_spec.get('title', 'chart')}",
                        config={"displayModeBar": False},
                    )
                except Exception as chart_err:
                    st.caption(f"Chart render notice: {chart_err}")

                st.markdown("<div class='chart-card-caption'>Generated from executed analysis</div>", unsafe_allow_html=True)

        # 5. Collapsible Sections: SQL, How I got this, Data Preview
        col_sql, col_reason, col_prev = st.columns(3)

        # A. SQL Section
        if result.sql_executed:
            time_label = f" · Executed in {result.execution_time_ms:.1f}ms" if result.execution_time_ms > 0 else ""
            with st.expander(f"SQL Query (DuckDB{time_label})", expanded=False):
                st.markdown(f"<div style='font-size: 0.75rem; font-weight: 600; color: #0D9488; margin-bottom: 0.4rem;'>DUCKDB · EXECUTED IN {result.execution_time_ms:.1f}MS</div>", unsafe_allow_html=True)
                st.code(result.sql_executed, language="sql")
                sql_bytes = result.sql_executed.encode("utf-8")
                st.download_button(
                    label="Download SQL",
                    data=sql_bytes,
                    file_name=f"query_{card_index}.sql",
                    mime="text/plain",
                    key=f"dl_sql_{card_index}",
                    use_container_width=True,
                )
        elif result.pandas_executed:
            with st.expander("Python Code (Pandas Sandbox)", expanded=False):
                st.markdown("<div style='font-size: 0.75rem; font-weight: 600; color: #0D9488; margin-bottom: 0.4rem;'>PANDAS · SANDBOX EXECUTED</div>", unsafe_allow_html=True)
                st.code(result.pandas_executed, language="python")
        else:
            with st.expander("SQL Query (NOT EXECUTED)", expanded=False):
                st.markdown("<div style='font-size: 0.8rem; color: #64748B;'>SQL was not executed for this direct informational query.</div>", unsafe_allow_html=True)

        # B. How I Got This (Safe High-Level Explanation)
        with st.expander("How I got this", expanded=False):
            steps_html = (
                "<div style='font-size: 0.85rem; color: #334155; line-height: 1.6;'>"
                "<div style='font-weight: 600; margin-bottom: 0.35rem;'>Analysis Workflow:</div>"
                "<ol style='margin: 0; padding-left: 1.2rem;'>"
                "<li>Selected relevant tables and inspected schema profiles</li>"
                "<li>Identified required join keys and filter dimensions</li>"
                "<li>Generated deterministic DuckDB query / aggregation logic</li>"
                "<li>Executed query against isolated in-memory engine</li>"
                "<li>Validated computed numbers against raw data preview</li>"
                "<li>Synthesized executive insights from verified facts</li>"
                "</ol>"
            )
            if result.reasoning:
                steps_html += f"<div style='margin-top: 0.65rem; padding-top: 0.5rem; border-top: 1px solid #E2E8F0; font-size: 0.825rem; color: #64748B;'><strong>Agent Notes:</strong> {result.reasoning}</div>"
            steps_html += "</div>"
            st.markdown(steps_html, unsafe_allow_html=True)

        # C. Data Preview
        if result.data_preview is not None and not result.data_preview.empty:
            preview_count = len(result.data_preview)
            with st.expander(f"Data Preview ({preview_count:,} rows analyzed)", expanded=False):
                st.dataframe(result.data_preview, use_container_width=True)
                csv_bytes = result.data_preview.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download CSV",
                    data=csv_bytes,
                    file_name=f"query_result_{card_index}.csv",
                    mime="text/csv",
                    key=f"dl_csv_{card_index}",
                    use_container_width=True,
                )
