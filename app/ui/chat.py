"""Datalens Chat component: Conversation history, dynamic suggested question chips, and interactive agent loop."""

from datetime import datetime
from pathlib import Path
import streamlit as st

from app.config import settings
from app.ui.answer_card import render_answer_card
from app.ui.sidebar import _load_sample_data, SAMPLE_DATA_DIR

DEFAULT_SUGGESTED_QUESTIONS = [
    "Show total revenue",
    "Which region performs best?",
    "Find anomalies",
    "Show monthly trends",
    "Top customers",
]

def get_dynamic_suggested_questions() -> list:
    """Generate intelligent suggestions based on currently loaded tables and columns."""
    profiles = st.session_state.get("table_profiles", {})
    if not profiles:
        return DEFAULT_SUGGESTED_QUESTIONS

    all_cols = set()
    for prof in profiles.values():
        all_cols.update([c.lower() for c in prof.columns.keys()])

    suggestions = []
    if any(c in all_cols for c in ["revenue", "sales", "total_sales"]):
        suggestions.append("Show total revenue")
    if "region" in all_cols:
        suggestions.append("Which region performs best?")
    if any(c in all_cols for c in ["revenue", "profit", "quantity", "price"]):
        suggestions.append("Find anomalies")
    if any(c in all_cols for c in ["order_date", "date", "signup_date"]):
        suggestions.append("Show monthly trends")
    if any(c in all_cols for c in ["customer_name", "customer_id"]):
        suggestions.append("Top customers")

    # Fallback to defaults if needed
    for default_q in DEFAULT_SUGGESTED_QUESTIONS:
        if len(suggestions) < 5 and default_q not in suggestions:
            suggestions.append(default_q)

    return suggestions[:5]

def render_empty_state():
    """Render modern SaaS empty state with 4 feature cards."""
    st.markdown(
        """
        <div class="empty-hero-card">
            <div style="display: inline-block; padding: 0.25rem 0.75rem; background-color: #F0FDFA; color: #0D9488; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.85rem; border: 1px solid #CCFBF1;">
                Enterprise AI Analyst
            </div>
            <div class="empty-hero-title">Datalens</div>
            <div class="empty-hero-lead">Turn your data into decisions.</div>
            <div class="empty-hero-sub">Upload one or more CSV files and ask questions using natural language.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4 Feature Cards Grid
    st.markdown(
        """
        <div class="feature-cards-grid">
            <div class="feature-card">
                <div style="color: #0D9488; margin-bottom: 8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                </div>
                <div class="feature-card-title">Natural Language</div>
                <div class="feature-card-desc">Ask questions about your data in plain English.</div>
            </div>
            <div class="feature-card">
                <div style="color: #0284C7; margin-bottom: 8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <div class="feature-card-title">AI Insights</div>
                <div class="feature-card-desc">Generate business insights from verified queries.</div>
            </div>
            <div class="feature-card">
                <div style="color: #6366F1; margin-bottom: 8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                </div>
                <div class="feature-card-title">Visual Analytics</div>
                <div class="feature-card-desc">Create interactive charts automatically.</div>
            </div>
            <div class="feature-card">
                <div style="color: #D97706; margin-bottom: 8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <div class="feature-card-title">Anomaly Detection</div>
                <div class="feature-card-desc">Find unusual records and statistical outliers.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if SAMPLE_DATA_DIR.exists():
        st.markdown("<div style='text-align: center; margin-top: 2rem;'>", unsafe_allow_html=True)
        col_pad1, col_btn, col_pad2 = st.columns([2, 2, 2])
        with col_btn:
            if st.button("Load sample datasets", type="primary", use_container_width=True):
                _load_sample_data()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

def render_chat_tab():
    """Render the main Chat interface with greeting, message history, suggested chips, and prompt input."""
    if not st.session_state.table_profiles:
        render_empty_state()
        return

    # Dynamic time-of-day greeting
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")

    st.markdown(
        f"""
        <div class="chat-welcome-banner">
            <div class="chat-welcome-greeting">{greeting}</div>
            <div class="chat-welcome-sub">Ask anything about your data.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render Conversation History
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            st.markdown(
                f"""
                <div class="user-msg-bubble">
                    {msg['content']}
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif msg["role"] == "assistant":
            if "result" in msg:
                render_answer_card(msg["result"], card_index=idx)
            else:
                st.markdown(
                    f"""
                    <div class="answer-card">
                        <div class="answer-direct-text">{msg['content']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Suggested Questions Chips
    suggestions = get_dynamic_suggested_questions()
    st.markdown(
        "<div style='font-size: 0.725rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin: 1rem 0 0.4rem 0;'>Suggested questions</div>",
        unsafe_allow_html=True,
    )
    chip_cols = st.columns(len(suggestions))
    for col_idx, question in enumerate(suggestions):
        with chip_cols[col_idx]:
            if st.button(question, key=f"chip_{col_idx}", use_container_width=True):
                _process_user_query(question)

    # Chat Input Box
    user_input = st.chat_input("Ask a question about your data...")
    if user_input:
        _process_user_query(user_input)

def _process_user_query(query: str):
    """Execute query against DataAnalystAgent with subtle spinner and graceful error handling."""
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.spinner("Analyzing your data..."):
        try:
            agent = st.session_state.get_agent()
            result = agent.ask(query)
            st.session_state.last_result = result
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": result.answer,
                "result": result,
            })
        except Exception as exc:
            exc_str = str(exc)
            if hasattr(settings, "groq_api_key") and settings.groq_api_key and settings.groq_api_key in exc_str:
                exc_str = exc_str.replace(settings.groq_api_key, "[REDACTED]")
            if "401" in exc_str or "auth" in exc_str.lower() or "api_key" in exc_str.lower() or "invalid api key" in exc_str.lower():
                err_msg = "Unable to connect to Groq. Please check your API key."
            else:
                err_msg = (
                    f"**Unable to complete analysis**\n\n"
                    f"We encountered an issue while processing your request: *{exc_str}*.\n"
                    f"Please verify your table columns or rephrase your question."
                )
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": err_msg,
            })

    st.rerun()
