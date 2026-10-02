"""Datalens Sidebar component: File uploader, dataset listing, schema join key detection, and dataset removal."""

from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import streamlit as st

from app.config import settings
from app.data.loader import load_csv_file
from app.data.profiler import TableProfile

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"

def detect_schema_join_keys(profiles: Dict[str, TableProfile]) -> List[Tuple[str, str, str, str]]:
    """
    Infer foreign key relationships across loaded tables using shared primary/foreign key naming conventions.
    Returns: list of (table1, col1, table2, col2)
    """
    relationships = []
    tables = list(profiles.keys())

    for i in range(len(tables)):
        for j in range(i + 1, len(tables)):
            t1, t2 = tables[i], tables[j]
            p1, p2 = profiles[t1], profiles[t2]

            cols1 = {c.lower(): c for c in p1.columns.keys()}
            cols2 = {c.lower(): c for c in p2.columns.keys()}

            for col_lower in cols1.keys() & cols2.keys():
                if col_lower.endswith("_id") or col_lower == "id" or "id" in col_lower:
                    relationships.append((t1, cols1[col_lower], t2, cols2[col_lower]))

    return relationships

def remove_dataset(table_name: str) -> None:
    """Safely remove a dataset from session state and DuckDB."""
    if table_name in st.session_state.table_profiles:
        del st.session_state.table_profiles[table_name]
    if table_name in st.session_state.dataframes:
        del st.session_state.dataframes[table_name]
    if "db_manager" in st.session_state:
        st.session_state.db_manager.unregister_dataframe(table_name)
    if table_name in st.session_state.anomalies_cache:
        del st.session_state.anomalies_cache[table_name]
    if table_name in st.session_state.quality_cache:
        del st.session_state.quality_cache[table_name]
    st.rerun()

def clear_all_data() -> None:
    """Clear all loaded tables, cache, and conversation history."""
    if "db_manager" in st.session_state:
        for t in list(st.session_state.db_manager.list_tables()):
            st.session_state.db_manager.unregister_dataframe(t)
    st.session_state.table_profiles.clear()
    st.session_state.dataframes.clear()
    if "loaded_file_ids" in st.session_state:
        st.session_state.loaded_file_ids.clear()
    st.session_state.anomalies_cache.clear()
    st.session_state.quality_cache.clear()
    st.session_state.chat_history.clear()
    st.session_state.last_result = None
    st.rerun()

def render_sidebar():
    """Render sidebar matching modern SaaS data sources specification."""
    with st.sidebar:
        # Header: Datalens / AI Data Analyst
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.25rem;">
                <div style="width: 28px; height: 28px; background-color: #0D9488; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                        <polyline points="2 17 12 22 22 17"></polyline>
                        <polyline points="2 12 12 17 22 12"></polyline>
                    </svg>
                </div>
                <div>
                    <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: #0F172A; letter-spacing: -0.02em; line-height: 1.1;">Datalens</div>
                    <div style="font-size: 0.75rem; font-weight: 500; color: #64748B;">AI Data Analyst</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<hr style='margin: 0.75rem 0 1rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

        # Section: DATA SOURCES
        st.markdown(
            "<div class='sidebar-section-title'>Data Sources</div>",
            unsafe_allow_html=True,
        )

        # Large upload area description
        st.markdown(
            """
            <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 0.5rem; line-height: 1.4;">
                <strong style="color: #0F172A;">Upload CSV files</strong><br>
                Drag & drop or browse. Multiple files supported.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # File Uploader
        uploaded_files = st.file_uploader(
            "Upload CSV files",
            type=["csv"],
            accept_multiple_files=True,
            help=f"Maximum file size: {settings.max_file_size_mb}MB per file.",
            label_visibility="collapsed",
            key="csv_file_uploader",
        )

        if uploaded_files:
            if "loaded_file_ids" not in st.session_state:
                st.session_state.loaded_file_ids = set()
            new_file_loaded = False
            for up_file in uploaded_files:
                file_sig = getattr(up_file, "file_id", f"{up_file.name}_{up_file.size}")
                if file_sig not in st.session_state.loaded_file_ids:
                    try:
                        df, profile, table_name, mapping = load_csv_file(
                            up_file,
                            existing_tables=set(st.session_state.table_profiles.keys()),
                        )
                        st.session_state.db_manager.register_dataframe(table_name, df)
                        st.session_state.table_profiles[table_name] = profile
                        st.session_state.dataframes[table_name] = df
                        st.session_state.loaded_file_ids.add(file_sig)
                        new_file_loaded = True
                    except Exception as exc:
                        st.error(f"Error loading {up_file.name}: {exc}")
            if new_file_loaded:
                st.rerun()

        # Quick Load Sample Data Button (only when no data is loaded)
        if not st.session_state.table_profiles and SAMPLE_DATA_DIR.exists():
            st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)
            if st.button("Load sample datasets", type="secondary", use_container_width=True):
                _load_sample_data()
                st.rerun()

        # Loaded Datasets Section
        if st.session_state.table_profiles:
            st.markdown("<hr style='margin: 1.25rem 0 1rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
            
            total_tables = len(st.session_state.table_profiles)
            total_rows = sum(len(df) for df in st.session_state.dataframes.values())
            
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.65rem;">
                    <div class='sidebar-section-title' style='margin-bottom: 0;'>Loaded Tables ({total_tables})</div>
                    <div style="font-family: var(--font-mono); font-size: 0.7rem; color: #64748B;">{total_rows:,} total rows</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Display each loaded table with table icon, name, row count, column count, and remove button
            tables_to_remove = []
            for t_name in list(st.session_state.table_profiles.keys()):
                df = st.session_state.dataframes.get(t_name)
                if df is None:
                    continue
                
                row_count = len(df)
                col_count = len(df.columns)

                col_info, col_del = st.columns([3.5, 1.2])
                with col_info:
                    st.markdown(
                        f"""
                        <div style="display: flex; align-items: flex-start; gap: 8px; padding: 4px 0;">
                            <div style="color: #0D9488; margin-top: 2px;">
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"></path>
                                    <line x1="4" y1="9" x2="20" y2="9"></line>
                                    <line x1="4" y1="15" x2="20" y2="15"></line>
                                    <line x1="10" y1="3" x2="10" y2="21"></line>
                                </svg>
                            </div>
                            <div>
                                <div class="dataset-name-text">{t_name}</div>
                                <div class="dataset-meta-text">{row_count:,} rows · {col_count} columns</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_del:
                    if st.button("✕", key=f"del_{t_name}", help=f"Remove {t_name}", use_container_width=True):
                        tables_to_remove.append(t_name)

            for t_remove in tables_to_remove:
                remove_dataset(t_remove)

            # Schema Join Keys
            join_keys = detect_schema_join_keys(st.session_state.table_profiles)
            if join_keys:
                st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
                st.markdown(
                    "<div class='sidebar-section-title' style='margin-bottom: 0.35rem;'>Detected Schema Joins</div>",
                    unsafe_allow_html=True,
                )
                join_text_lines = [f"{t1}.{c1} → {t2}.{c2}" for t1, c1, t2, c2 in join_keys]
                st.markdown(
                    f"""
                    <div class="join-keys-card">
                        {"<br>".join(join_text_lines)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Clear All Data Button
            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
            if st.button("Clear all data", type="secondary", use_container_width=True):
                clear_all_data()

def _load_sample_data():
    """Load default sample datasets (sales, customers, products)."""
    for file_name in ["customers.csv", "products.csv", "sales.csv"]:
        f_path = SAMPLE_DATA_DIR / file_name
        if f_path.exists():
            df, profile, table_name, mapping = load_csv_file(f_path)
            st.session_state.db_manager.register_dataframe(table_name, df)
            st.session_state.table_profiles[table_name] = profile
            st.session_state.dataframes[table_name] = df
