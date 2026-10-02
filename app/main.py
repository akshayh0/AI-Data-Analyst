"""Datalens - Production AI Data Analyst Web Application."""

import os
from pathlib import Path
import sys

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st

# Configure page layout and metadata
st.set_page_config(
    page_title="Datalens",
    page_icon="D",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.agent import DataAnalystAgent
from app.config import settings
from app.llm.groq_provider import GroqProvider
from app.tools.sql_tool import DuckDBManager
from app.ui.anomalies_tab import render_anomalies_tab
from app.ui.chat import render_chat_tab
from app.ui.dashboard_tab import render_dashboard_tab
from app.ui.data_tab import render_data_tab
from app.ui.quality_tab import render_quality_tab
from app.ui.sidebar import render_sidebar
from app.llm.mock_provider import SmokeTestMockProvider

CSS_PATH = Path(__file__).resolve().parent / "ui" / "styles.css"

def load_custom_css():
    """Inject Datalens custom CSS styles."""
    if CSS_PATH.exists():
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def init_session_state():
    """Initialize persistent session variables."""
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = DuckDBManager()
    if "table_profiles" not in st.session_state:
        st.session_state.table_profiles = {}
    if "dataframes" not in st.session_state:
        st.session_state.dataframes = {}
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "anomalies_cache" not in st.session_state:
        st.session_state.anomalies_cache = {}
    if "quality_cache" not in st.session_state:
        st.session_state.quality_cache = {}

    def get_agent() -> DataAnalystAgent:
        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key and api_key != "your_groq_api_key_here":
            llm = GroqProvider(
                api_key=api_key,
                model=settings.groq_model,
                fallback_model=settings.groq_fallback_model,
            )
        else:
            llm = SmokeTestMockProvider()

        return DataAnalystAgent(
            llm_provider=llm,
            db_manager=st.session_state.db_manager,
            table_profiles=st.session_state.table_profiles,
        )

    st.session_state.get_agent = get_agent

def render_app_header():
    """Render top application header bar with brand and AI connection status."""
    is_connected = settings.is_groq_configured()
    status_text = "AI Connected" if is_connected else "AI Ready"
    
    st.markdown(
        f"""
        <div class="app-header-bar">
            <div>
                <div class="app-brand-title">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0D9488" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                        <polyline points="2 17 12 22 22 17"></polyline>
                        <polyline points="2 12 12 17 22 12"></polyline>
                    </svg>
                    Datalens
                </div>
                <div class="app-brand-subtitle">AI-Powered Data Analysis</div>
            </div>
            <div class="status-indicator-pill">
                <span class="status-dot"></span>
                {status_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def main():
    load_custom_css()
    init_session_state()

    # 1. Render Top App Header
    render_app_header()

    # 2. Render Left Sidebar
    render_sidebar()

    # 3. Main Content Tabs (Chat | Data | Quality | Anomalies | Dashboard)
    tab_chat, tab_data, tab_quality, tab_anomalies, tab_dashboard = st.tabs(["Chat", "Data", "Quality", "Anomalies", "Dashboard"])

    with tab_chat:
        render_chat_tab()

    with tab_data:
        render_data_tab()

    with tab_quality:
        render_quality_tab()

    with tab_anomalies:
        render_anomalies_tab()

    with tab_dashboard:
        render_dashboard_tab()

if __name__ == "__main__":
    main()
