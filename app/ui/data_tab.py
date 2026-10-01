"""Datalens Data tab component: Table inspection, dataset schema exploration, and column profiles."""

import pandas as pd
import streamlit as st

def render_data_tab():
    """Render table preview and column profile exploration interface."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample data from the sidebar.")
        return

    tables = list(st.session_state.table_profiles.keys())
    selected_table = st.selectbox(
        "Select dataset table",
        options=tables,
        format_func=lambda t: f"{t}.csv ({len(st.session_state.dataframes[t]):,} rows)",
        label_visibility="collapsed",
    )

    df = st.session_state.dataframes[selected_table]
    profile = st.session_state.table_profiles[selected_table]

    # Dataset Summary Metrics Tiles
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Total Records</div>
                <div class="stat-value">{len(df):,}</div>
                <div class="stat-sub">Rows ingested</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Columns</div>
                <div class="stat-value">{len(df.columns)}</div>
                <div class="stat-sub">Attributes detected</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">In-Memory Size</div>
                <div class="stat-value">{mem_mb:.2f} MB</div>
                <div class="stat-sub">RAM consumed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        total_nulls = int(df.isna().sum().sum())
        null_rate = (total_nulls / (len(df) * len(df.columns))) * 100 if len(df) and len(df.columns) else 0.0
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Total Null Cells</div>
                <div class="stat-value">{total_nulls:,}</div>
                <div class="stat-sub">{null_rate:.2f}% null rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # 1. Tabular Data Preview
    st.markdown(
        f"<div style='font-size: 0.85rem; font-weight: 600; color: #1C1917; margin-bottom: 0.5rem;'>Data Table Preview ({len(df):,} rows)</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(df, use_container_width=True, height=320)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # 2. Column Profiles Breakdown Table
    st.markdown(
        f"<div style='font-size: 0.85rem; font-weight: 600; color: #1C1917; margin-bottom: 0.5rem;'>Column Schema Profiles ({len(profile.columns)} fields)</div>",
        unsafe_allow_html=True,
    )

    profile_records = []
    for col_name, col_prof in profile.columns.items():
        samples_str = ", ".join(str(s) for s in col_prof.sample_values[:3])
        profile_records.append({
            "Column Name": col_name,
            "Type": col_prof.dtype,
            "Null Count": f"{col_prof.null_count:,}",
            "Null %": f"{col_prof.null_percentage:.1f}%",
            "Distinct": f"{col_prof.unique_count:,}",
            "Sample Values": samples_str,
        })

    profile_df = pd.DataFrame(profile_records)
    st.dataframe(profile_df, use_container_width=True, hide_index=True)
