"""Datalens Quality tab component: Dataset health scores, completeness audits, and quality reports."""

from typing import Dict
import pandas as pd
import streamlit as st

from app.tools.quality_tool import generate_quality_report

def render_quality_tab():
    """Render data quality health audits across all loaded datasets."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample data from the sidebar.")
        return

    # Compute or retrieve cached quality reports per table
    reports: Dict[str, Tuple[str, pd.DataFrame]] = {}
    combined_markdown = []

    for t_name, df in st.session_state.dataframes.items():
        if t_name not in st.session_state.quality_cache:
            report_text, report_df = generate_quality_report(df, t_name)
            st.session_state.quality_cache[t_name] = (report_text, report_df)
        reports[t_name] = st.session_state.quality_cache[t_name]
        combined_markdown.append(reports[t_name][0])

    # Compute Global Quality Metrics
    total_rows = sum(len(df) for df in st.session_state.dataframes.values())
    total_cells = sum(len(df) * len(df.columns) for df in st.session_state.dataframes.values())
    total_nulls = sum(int(df.isna().sum().sum()) for df in st.session_state.dataframes.values())
    total_dups = sum(int(df.duplicated().sum()) for df in st.session_state.dataframes.values())

    # Overall Health Score (averaged or aggregated across tables)
    scores = [reports[t][1].attrs.get("health_score", 100) for t in reports if not reports[t][1].empty]
    overall_health = round(sum(scores) / len(scores)) if scores else 100

    # Header and Export Action
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(
            f"""
            <div style="font-size: 1.15rem; font-weight: 700; color: #1C1917;">
                Data Quality & Health
            </div>
            <div style="font-size: 0.825rem; color: #78716C;">
                Column-level validation, completeness metrics, schema consistency, and duplicate audits across {len(reports)} tables.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with head_col2:
        export_md = "\n\n---\n\n".join(combined_markdown)
        st.download_button(
            label="Export Quality Report",
            data=export_md.encode("utf-8"),
            file_name="datalens_quality_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Global Health Score Summary Tiles
    tile1, tile2, tile3, tile4 = st.columns(4)
    with tile1:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Overall Health Score</div>
                <div class="stat-value">{overall_health}/100</div>
                <div class="stat-sub">Aggregated audit</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile2:
        null_rate = (total_nulls / total_cells * 100) if total_cells else 0.0
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Missing Cells</div>
                <div class="stat-value">{total_nulls:,}</div>
                <div class="stat-sub">{null_rate:.2f}% global rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile3:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Duplicate Rows</div>
                <div class="stat-value">{total_dups:,}</div>
                <div class="stat-sub">Exact duplicates</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile4:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Audited Records</div>
                <div class="stat-value">{total_rows:,}</div>
                <div class="stat-sub">Across {len(reports)} tables</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # Per-Table Quality Audit Cards
    table_tabs = st.tabs([f"{t}.csv" for t in reports.keys()])
    for idx, (t_name, (rep_text, rep_df)) in enumerate(reports.items()):
        with table_tabs[idx]:
            table_health = rep_df.attrs.get("health_score", 100) if not rep_df.empty else 100
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                    <div style="font-weight: 600; font-size: 0.95rem;">Table: {t_name}.csv</div>
                    <span class="{'badge-teal' if table_health >= 90 else ('badge-warn' if table_health >= 70 else 'badge-fail')}">
                        Health Score: {table_health}/100
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not rep_df.empty:
                st.dataframe(
                    rep_df[["check", "column", "metric", "status", "recommendation"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(f"No quality issues identified in table '{t_name}'.")
