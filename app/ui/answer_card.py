"""Datalens Answer Card component: Structured presentation of answers, insights, charts, and code."""

from typing import Any, Dict, Optional
import pandas as pd
import streamlit as st

from app.agent import AgentTurnResult
from app.tools.chart_tool import build_plotly_chart
from app.ui.theme import apply_datalens_chart_styling

def render_answer_card(result: AgentTurnResult, card_index: int = 0):
    """
    Render standardized 5-part answer card:
    1. Direct Answer
    2. Key Insights
    3. Plotly Chart (if present)
    4. Collapsed 'SQL used' with real DuckDB execution time
    5. Collapsed 'How I got this' reasoning
    6. Footer actions: copy SQL & export CSV
    """
    with st.container():
        # Outer Card Container
        st.markdown(
            f"""
            <div class="answer-container">
                <div class="answer-header">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="badge-teal">DuckDB In-Memory</span>
                        {f'<span class="badge-stone">{result.execution_time_ms:.1f}ms</span>' if result.execution_time_ms > 0 else ''}
                    </div>
                    <div class="answer-meta">
                        {f'{result.iterations_used} steps' if result.iterations_used else ''}
                    </div>
                </div>
            """,
            unsafe_allow_html=True,
        )

        # 1. Direct Answer
        answer_text = result.answer
        # Strip header markers if already embedded
        for header in ["### 1. Direct Answer", "### 2. Key Insights", "### 3. Visualizations", "### 4. Code Used", "### 5. How I Got This"]:
            if header in answer_text:
                answer_text = answer_text.split("### 2. Key Insights")[0].replace("### 1. Direct Answer", "").strip()
                break

        st.markdown(f"<div class='answer-text'>{answer_text}</div>", unsafe_allow_html=True)

        # 2. Key Insights
        if result.insights:
            insights_html = "".join([f"<li style='margin-bottom: 0.35rem;'>{item}</li>" for item in result.insights])
            st.markdown(
                f"""
                <div class="answer-insights-box">
                    <div class="answer-insights-title">Key Insights</div>
                    <ul style="margin: 0; padding-left: 1.2rem; font-size: 0.88rem; color: #1C1917;">
                        {insights_html}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Data Grounding Warning (if any unsupported numbers were flagged)
        if result.unsupported_numbers:
            st.caption(
                f"Note: Some figures quoted could not be verified directly against query results: "
                f"{', '.join(result.unsupported_numbers)}."
            )

        # 3. Visualizations (Plotly Chart)
        if result.chart_spec and result.data_preview is not None and not result.data_preview.empty:
            try:
                fig = build_plotly_chart(result.chart_spec, result.data_preview)
                fig = apply_datalens_chart_styling(fig)
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"chart_{card_index}_{result.chart_spec.get('title', 'spec')}",
                    config={"displayModeBar": False},
                )
            except Exception as chart_err:
                st.caption(f"Chart render notice: {chart_err}")

        # 4. Collapsed "SQL used" expander (DuckDB & execution time)
        if result.sql_executed:
            time_label = f" • {result.execution_time_ms:.1f}ms execution" if result.execution_time_ms > 0 else ""
            with st.expander(f"SQL used (DuckDB{time_label})", expanded=False):
                st.code(result.sql_executed, language="sql")
        elif result.pandas_executed:
            with st.expander("Python Code used (Pandas)", expanded=False):
                st.code(result.pandas_executed, language="python")

        # 5. Collapsed "How I got this" reasoning expander
        if result.reasoning:
            with st.expander("How I got this (Reasoning)", expanded=False):
                st.markdown(f"<div style='font-size: 0.85rem; color: #57534E;'>{result.reasoning}</div>", unsafe_allow_html=True)

        # 6. Data Preview Expander
        if result.data_preview is not None and not result.data_preview.empty:
            with st.expander(f"Data preview ({len(result.data_preview)} rows)", expanded=False):
                st.dataframe(result.data_preview, use_container_width=True)

        # 7. Footer Actions: Export CSV and Copy SQL
        col_actions = st.columns([1, 1, 4])
        with col_actions[0]:
            if result.data_preview is not None and not result.data_preview.empty:
                csv_bytes = result.data_preview.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Export CSV",
                    data=csv_bytes,
                    file_name=f"query_result_{card_index}.csv",
                    mime="text/csv",
                    key=f"dl_csv_{card_index}",
                    use_container_width=True,
                )
        with col_actions[1]:
            if result.sql_executed:
                sql_bytes = result.sql_executed.encode("utf-8")
                st.download_button(
                    label="Download SQL",
                    data=sql_bytes,
                    file_name=f"query_{card_index}.sql",
                    mime="text/plain",
                    key=f"dl_sql_{card_index}",
                    use_container_width=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)
