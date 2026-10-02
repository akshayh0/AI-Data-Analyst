"""Datalens Data tab component: Table inspection, dataset schema exploration, and column profiles."""

import pandas as pd
import streamlit as st

def render_data_tab():
    """Render table cards, schema profiles, and data exploration interface."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample datasets from the sidebar.")
        return

    tables = list(st.session_state.table_profiles.keys())

    # 1. Loaded Datasets Overview Cards Grid
    st.markdown("<div style='font-family: var(--font-heading); font-size: 0.95rem; font-weight: 700; color: #0F172A; margin-bottom: 0.75rem;'>Loaded Datasets</div>", unsafe_allow_html=True)
    
    card_cols = st.columns(min(len(tables), 4))
    for idx, t in enumerate(tables):
        t_df = st.session_state.dataframes[t]
        with card_cols[idx % 4]:
            st.markdown(
                f"""
                <div class="stat-tile" style="margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span class="stat-label">{t}</span>
                        <span class="badge-teal">{len(t_df.columns)} cols</span>
                    </div>
                    <div class="stat-value">{len(t_df):,}</div>
                    <div class="stat-sub">Total records</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<hr style='margin: 0.75rem 0 1.25rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 2. Selected Table Selector
    selected_table = st.selectbox(
        "Select dataset to inspect",
        options=tables,
        format_func=lambda t: f"{t} ({len(st.session_state.dataframes[t]):,} rows · {len(st.session_state.dataframes[t].columns)} columns)",
        key="data_tab_table_select",
    )

    df = st.session_state.dataframes[selected_table]
    profile = st.session_state.table_profiles[selected_table]

    # Metrics for selected dataset
    m1, m2, m3, m4 = st.columns(4)
    with m1:
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
    with m2:
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
    with m3:
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
    with m4:
        total_nulls = int(df.isna().sum().sum())
        null_rate = (total_nulls / (len(df) * len(df.columns))) * 100 if len(df) and len(df.columns) else 0.0
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Null Cells</div>
                <div class="stat-value">{total_nulls:,}</div>
                <div class="stat-sub">{null_rate:.2f}% null rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # 3. Column Schema Profiles Table
    st.markdown(
        f"<div style='font-family: var(--font-heading); font-size: 0.95rem; font-weight: 700; color: #0F172A; margin-bottom: 0.5rem;'>Column Schema Profiles ({len(profile.columns)} attributes)</div>",
        unsafe_allow_html=True,
    )

    profile_records = []
    for col_name, col_prof in profile.columns.items():
        samples_str = ", ".join(str(s) for s in col_prof.sample_values[:3])
        profile_records.append({
            "Column": col_name,
            "Type": col_prof.dtype,
            "Missing": f"{col_prof.null_count:,} ({col_prof.null_percentage:.1f}%)",
            "Unique": f"{col_prof.unique_count:,}",
            "Example": samples_str,
        })

    profile_df = pd.DataFrame(profile_records)
    st.dataframe(profile_df, use_container_width=True, hide_index=True)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # 4. Tabular Data Preview
    st.markdown(
        f"<div style='font-family: var(--font-heading); font-size: 0.95rem; font-weight: 700; color: #0F172A; margin-bottom: 0.5rem;'>Data Table Preview ({len(df):,} rows)</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(df, use_container_width=True, height=320)
