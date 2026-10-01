"""Datalens Anomalies tab component: Multi-method anomaly detection and interactive inspection."""

from typing import Dict
import pandas as pd
import streamlit as st

from app.tools.anomaly_tool import detect_anomalies_pipeline

def render_anomalies_tab():
    """Render anomaly detection audit, consensus tiles, and interactive record inspector."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample data from the sidebar.")
        return

    # Trigger scan button & CSV export
    head_col1, head_col2, head_col3 = st.columns([3, 1, 1])
    with head_col1:
        st.markdown(
            """
            <div style="font-size: 1.15rem; font-weight: 700; color: #1C1917;">
                Anomalies & Outliers
            </div>
            <div style="font-size: 0.825rem; color: #78716C;">
                Multi-method statistical (IQR, Modified Z-score) and machine learning (Isolation Forest) detection.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with head_col2:
        if st.button("Run anomaly scan", type="primary", use_container_width=True):
            st.session_state.anomalies_cache.clear()
            st.rerun()

    # Run detection on all loaded tables if not cached
    all_flagged_rows = []
    affected_tables: Dict[str, int] = {}
    total_dataset_rows = sum(len(df) for df in st.session_state.dataframes.values())

    for t_name, df in st.session_state.dataframes.items():
        if t_name not in st.session_state.anomalies_cache:
            with st.spinner(f"Scanning '{t_name}' for anomalies..."):
                flagged_df, summary = detect_anomalies_pipeline(df, random_state=42)
                st.session_state.anomalies_cache[t_name] = (flagged_df, summary)

        flagged_df, summary = st.session_state.anomalies_cache[t_name]
        if not flagged_df.empty:
            affected_tables[t_name] = len(flagged_df)
            for idx, r in flagged_df.iterrows():
                # Extract first identifying column
                id_col = next((c for c in df.columns if "id" in c.lower()), df.columns[0])
                row_id_val = str(r.get(id_col, idx))

                all_flagged_rows.append({
                    "Row ID": row_id_val,
                    "Table": t_name,
                    "Confidence": "High confidence" if r.get("anomaly_confidence") == "high" else "Possible",
                    "Methods Agreed": r.get("methods_agreed", 1),
                    "Reason": r.get("anomaly_reasons", "Statistical outlier"),
                    "_full_record": r.to_dict(),
                })

    with head_col3:
        if all_flagged_rows:
            export_df = pd.DataFrame([
                {k: v for k, v in row.items() if not k.startswith("_")}
                for row in all_flagged_rows
            ])
            st.download_button(
                label="Export CSV",
                data=export_df.to_csv(index=False).encode("utf-8"),
                file_name="datalens_anomalies.csv",
                mime="text/csv",
                use_container_width=True,
            )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Summary Tiles
    tile1, tile2, tile3 = st.columns(3)
    total_flagged = len(all_flagged_rows)
    high_conf_count = sum(1 for r in all_flagged_rows if r["Confidence"] == "High confidence")
    flagged_pct = (total_flagged / total_dataset_rows * 100) if total_dataset_rows else 0.0

    with tile1:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Flagged Records</div>
                <div class="stat-value">{total_flagged:,} / {total_dataset_rows:,}</div>
                <div class="stat-sub">{flagged_pct:.2f}% of total dataset</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile2:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Consensus Agreement</div>
                <div class="stat-value">{high_conf_count} High Confidence</div>
                <div class="stat-sub">≥2 methods agreed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tile3:
        tables_str = ", ".join([f"{t} ({cnt})" for t, cnt in affected_tables.items()]) if affected_tables else "None"
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Affected Tables</div>
                <div class="stat-value">{len(affected_tables)} Tables</div>
                <div class="stat-sub">{tables_str}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if not all_flagged_rows:
        st.success("No statistical or business rule anomalies detected across loaded tables.")
        return

    # Anomalies Table Display
    display_data = []
    for r in all_flagged_rows:
        display_data.append({
            "Row ID": r["Row ID"],
            "Table": r["Table"],
            "Confidence": r["Confidence"],
            "Methods": f"{r['Methods Agreed']} methods",
            "Reason": r["Reason"],
        })

    anom_display_df = pd.DataFrame(display_data)
    st.dataframe(
        anom_display_df,
        use_container_width=True,
        column_config={
            "Reason": st.column_config.TextColumn("Reason", width="large"),
            "Confidence": st.column_config.TextColumn("Confidence", width="medium"),
        },
        hide_index=True,
    )

    # Inspect Full Row Expander
    with st.expander("Inspect Anomalous Row Attributes", expanded=False):
        row_options = [f"{r['Table']} • {r['Row ID']}" for r in all_flagged_rows]
        chosen = st.selectbox("Select anomalous record to inspect:", options=row_options)
        chosen_idx = row_options.index(chosen)
        selected_rec = all_flagged_rows[chosen_idx]["_full_record"]
        # Format as clean 2-column key-value dataframe
        rec_df = pd.DataFrame([
            {"Attribute": k, "Value": str(v)}
            for k, v in selected_rec.items()
            if not k.startswith("anomaly_") and k != "methods_agreed"
        ])
        st.dataframe(rec_df, use_container_width=True, hide_index=True)
