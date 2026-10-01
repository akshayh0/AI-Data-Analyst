"""Datalens Chat component: Conversation history, suggested question chips, and interactive agent loop."""

import streamlit as st

from app.config import settings
from app.ui.answer_card import render_answer_card
from app.ui.sidebar import _load_sample_data

SUGGESTED_QUESTIONS = [
    "Which region generated the highest revenue?",
    "Show monthly sales trends.",
    "Which products are underperforming?",
    "What are the top five customers?",
    "Detect anomalies in the dataset.",
]

def render_empty_state():
    """Render 3-step checklist onboarding empty state."""
    st.markdown(
        """
        <div style="margin-top: 1rem; margin-bottom: 2rem;">
            <div style="font-size: 1.35rem; font-weight: 700; color: #1C1917; margin-bottom: 0.35rem;">
                Get started with your data
            </div>
            <div style="font-size: 0.9rem; color: #78716C;">
                Upload tabular CSV files to interrogate distributions, detect structural anomalies, or run natural language queries against an in-memory DuckDB engine.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="checklist-step">
            <div class="step-num">1</div>
            <div>
                <div class="step-title">Upload datasets</div>
                <div class="step-desc">
                    Drag and drop one or more CSV files into the left sidebar (supports up to {settings.max_file_size_mb}MB per file). Datalens automatically detects delimiters, encodings, and infers schema join keys.
                </div>
            </div>
        </div>

        <div class="checklist-step">
            <div class="step-num">2</div>
            <div>
                <div class="step-title">Ask a question</div>
                <div class="step-desc">
                    Query your tables using plain natural language. Datalens generates verified DuckDB SQL and sandboxed Pandas code to compute deterministic results.
                </div>
            </div>
        </div>

        <div class="checklist-step">
            <div class="step-num">3</div>
            <div>
                <div class="step-title">Review verified answers</div>
                <div class="step-desc">
                    Examine structured insights, interactive Plotly charts, exact recorded execution SQL, and audited anomaly indicators.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    if st.button("Load sample data (sales, customers, products)", type="primary"):
        _load_sample_data()
        st.rerun()

def render_chat_tab():
    """Render the main Chat interface with message history, suggested chips, and prompt input."""
    if not st.session_state.table_profiles:
        render_empty_state()
        return

    # Render Conversation History
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(f"<div style='font-size: 0.95rem; font-weight: 500;'>{msg['content']}</div>", unsafe_allow_html=True)
        elif msg["role"] == "assistant":
            with st.chat_message("assistant"):
                if "result" in msg:
                    render_answer_card(msg["result"], card_index=idx)
                else:
                    st.markdown(msg["content"])

    # Suggested Questions Chips (shown if history is short or at bottom)
    if len(st.session_state.chat_history) == 0:
        st.markdown(
            "<div style='font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #78716C; margin: 1.25rem 0 0.5rem 0;'>Suggested questions</div>",
            unsafe_allow_html=True,
        )
        chip_cols = st.columns(len(SUGGESTED_QUESTIONS))
        for col_idx, question in enumerate(SUGGESTED_QUESTIONS):
            with chip_cols[col_idx]:
                if st.button(question, key=f"chip_{col_idx}", use_container_width=True):
                    _process_user_query(question)

    # Chat Input Box
    user_input = st.chat_input("Ask a question about your datasets (e.g. 'Show monthly sales trends')...")
    if user_input:
        _process_user_query(user_input)

def _process_user_query(query: str):
    """Execute query against DataAnalystAgent with spinner and error boundary."""
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.spinner("Analyzing data & executing queries..."):
        try:
            # Lazy initialize agent with session state db & profiles
            agent = st.session_state.get_agent()
            result = agent.ask(query)
            st.session_state.last_result = result
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": result.answer,
                "result": result,
            })
        except Exception as exc:
            err_msg = f"An unexpected error occurred during analysis: {str(exc)}"
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": err_msg,
            })

    st.rerun()
