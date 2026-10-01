"""Datalens Sidebar component: File uploader, dataset listing, and schema join key detection."""

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

def render_sidebar():
    """Render sidebar with branding, file uploader, dataset list, and inferred join keys."""
    with st.sidebar:
        # App Branding Header
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 1.25rem;">
                <div style="background-color: #0F766E; width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                    <span style="color: #FFFFFF; font-weight: 700; font-size: 14px;">D</span>
                </div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #1C1917; letter-spacing: -0.02em;">Datalens</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption("Upload tabular CSV files to interrogate with DuckDB SQL & Pandas.")

        # File Uploader
        uploaded_files = st.file_uploader(
            "Upload CSV files",
            type=["csv"],
            accept_multiple_files=True,
            help=f"Maximum file size: {settings.max_file_size_mb}MB per file.",
            label_visibility="collapsed",
        )

        if uploaded_files:
            for up_file in uploaded_files:
                table_cand = Path(up_file.name).stem.lower().replace("-", "_").replace(" ", "_")
                if table_cand not in st.session_state.table_profiles:
                    try:
                        df, profile, table_name, mapping = load_csv_file(up_file)
                        st.session_state.db_manager.register_dataframe(table_name, df)
                        st.session_state.table_profiles[table_name] = profile
                        st.session_state.dataframes[table_name] = df
                        st.success(f"Loaded '{table_name}' ({len(df):,} rows)")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error loading {up_file.name}: {exc}")

        # Quick Load Sample Data Button
        if not st.session_state.table_profiles:
            st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)
            if st.button("Load sample data", type="primary", use_container_width=True):
                _load_sample_data()
                st.rerun()

        # Loaded Datasets Section
        if st.session_state.table_profiles:
            st.markdown("<hr style='margin: 1rem 0; border: none; border-top: 1px solid #E7E5E4;'>", unsafe_allow_html=True)
            total_tables = len(st.session_state.table_profiles)
            total_rows = sum(len(df) for df in st.session_state.dataframes.values())
            st.markdown(
                f"<div style='font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #78716C; margin-bottom: 0.5rem;'>"
                f"Datasets ({total_tables} tables • {total_rows:,} rows)"
                f"</div>",
                unsafe_allow_html=True,
            )

            for t_name, profile in st.session_state.table_profiles.items():
                df = st.session_state.dataframes[t_name]
                st.markdown(
                    f"""
                    <div class="dataset-item">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center;">
                                <span class="dataset-badge"></span>
                                <span class="dataset-name">{t_name}.csv</span>
                            </div>
                        </div>
                        <div class="dataset-meta">{len(df):,} rows • {len(df.columns)} cols</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Schema Join Keys
            join_keys = detect_schema_join_keys(st.session_state.table_profiles)
            if join_keys:
                st.markdown("<div style='margin-top: 0.85rem;'></div>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: #78716C; margin-bottom: 0.35rem;'>Detected Schema Joins</div>",
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

            # Session Reset Button
            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
            if st.button("Reset session", type="secondary", use_container_width=True):
                st.session_state.clear()
                st.rerun()

def _load_sample_data():
    """Load default sample datasets (sales, customers, products)."""
    for file_name in ["customers.csv", "products.csv", "sales.csv"]:
        f_path = SAMPLE_DATA_DIR / file_name
        if f_path.exists():
            df, profile, table_name, mapping = load_csv_file(f_path)
            st.session_state.db_manager.register_dataframe(table_name, df)
            st.session_state.table_profiles[table_name] = profile
            st.session_state.dataframes[table_name] = df
