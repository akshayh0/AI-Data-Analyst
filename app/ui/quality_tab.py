"""Datalens Quality tab component: Dataset health scores, completeness audits, and quality reports."""

from typing import Dict, Tuple
import pandas as pd
import streamlit as st

from app.tools.quality_tool import generate_quality_report

def render_quality_tab():
    """Render data quality health audits across all loaded datasets."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample datasets from the sidebar.")
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
    total_cols = sum(len(df.columns) for df in st.session_state.dataframes.values())
    total_cells = sum(len(df) * len(df.columns) for df in st.session_state.dataframes.values())
    total_nulls = sum(int(df.isna().sum().sum()) for df in st.session_state.dataframes.values())
    total_dups = sum(int(df.duplicated().sum()) for df in st.session_state.dataframes.values())

    # Overall Health Score (average across tables)
    scores = [reports[t][1].attrs.get("health_score", 100) for t in reports if not reports[t][1].empty]
    overall_health = round(sum(scores) / len(scores)) if scores else 100

    # Header and Export Action
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(
            """
            <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: #0F172A;">
                Data Quality & Health
            </div>
            <div style="font-size: 0.825rem; color: #64748B;">
                Automated multi-dimensional assessment of dataset integrity, completeness, and validity.
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

    # 1. Top Metrics: Rows, Columns, Missing Values, Duplicate Rows
    tile1, tile2, tile3, tile4 = st.columns(4)
    with tile1:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Total Rows</div>
                <div class="stat-value">{total_rows:,}</div>
                <div class="stat-sub">Across {len(reports)} tables</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile2:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Columns</div>
                <div class="stat-value">{total_cols:,}</div>
                <div class="stat-sub">Attributes checked</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile3:
        null_rate = (total_nulls / total_cells * 100) if total_cells else 0.0
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Missing Values</div>
                <div class="stat-value">{total_nulls:,}</div>
                <div class="stat-sub">{null_rate:.2f}% null cell rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile4:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Duplicate Rows</div>
                <div class="stat-value">{total_dups:,}</div>
                <div class="stat-sub">Exact duplicate records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)

    # 2. Data Quality Score Hero Banner
    score_badge_class = "badge-teal" if overall_health >= 90 else ("badge-warn" if overall_health >= 70 else "badge-fail")
    score_desc = (
        "Clean, high-integrity dataset ready for production analysis." if overall_health >= 90
        else ("Moderate warnings detected; standard filtering recommended." if overall_health >= 70
        else "Significant structural issues detected; cleaning recommended before critical analysis.")
    )

    st.markdown(
        f"""
        <div class="stat-tile" style="display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;">
            <div>
                <div style="font-family: var(--font-heading); font-size: 0.85rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Global Data Quality Score</div>
                <div style="font-size: 0.9rem; color: #0F172A;">{score_desc}</div>
            </div>
            <div style="text-align: right;">
                <span class="{score_badge_class}" style="font-size: 1.4rem; padding: 0.35rem 0.85rem; border-radius: 8px;">
                    {overall_health} / 100
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Per-Table Quality Details Tabs
    table_tabs = st.tabs([f"{t}" for t in reports.keys()])
    for idx, (t_name, (rep_text, rep_df)) in enumerate(reports.items()):
        with table_tabs[idx]:
            df = st.session_state.dataframes[t_name]
            profile = st.session_state.table_profiles.get(t_name)
            table_health = rep_df.attrs.get("health_score", 100) if not rep_df.empty else 100

            tab_badge_class = "badge-teal" if table_health >= 90 else ("badge-warn" if table_health >= 70 else "badge-fail")

            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
                    <div style="font-family: var(--font-heading); font-size: 1rem; font-weight: 700; color: #0F172A;">
                        Table: {t_name}
                    </div>
                    <span class="{tab_badge_class}">
                        Health Score: {table_health}/100
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Sub-sections: Potential Issues & Column Types
            col_issues, col_types = st.columns([3, 2])

            with col_issues:
                st.markdown("<div style='font-size: 0.85rem; font-weight: 600; color: #0F172A; margin-bottom: 0.4rem;'>Quality Audit Checks & Potential Issues</div>", unsafe_allow_html=True)
                if not rep_df.empty:
                    st.dataframe(
                        rep_df[["check", "column", "metric", "status", "recommendation"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.success(f"No quality issues identified in table '{t_name}'.")

            with col_types:
                st.markdown("<div style='font-size: 0.85rem; font-weight: 600; color: #0F172A; margin-bottom: 0.4rem;'>Column Types & Missing Values</div>", unsafe_allow_html=True)
                if profile:
                    type_records = []
                    for c_name, c_prof in profile.columns.items():
                        type_records.append({
                            "Column": c_name,
                            "Type": c_prof.dtype,
                            "Nulls": f"{c_prof.null_count:,} ({c_prof.null_percentage:.1f}%)",
                            "Unique": c_prof.unique_count,
                        })
                    st.dataframe(pd.DataFrame(type_records), use_container_width=True, hide_index=True)
