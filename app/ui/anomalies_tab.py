"""Datalens Anomalies tab component: Multi-method anomaly detection and interactive inspection."""

from typing import Dict
import pandas as pd
import streamlit as st

from app.tools.anomaly_tool import detect_anomalies_pipeline

def render_anomalies_tab():
    """Render anomaly detection audit, consensus tiles, and interactive record table."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file or load sample datasets from the sidebar.")
        return

    # Header and Actions
    head_col1, head_col2, head_col3 = st.columns([3, 1, 1])
    with head_col1:
        st.markdown(
            """
            <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: #0F172A;">
                Anomaly Detection
            </div>
            <div style="font-size: 0.825rem; color: #64748B;">
                Identify unusual records and understand why they were flagged.
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
    total_dataset_rows = sum(len(df) for df in st.session_state.dataframes.values())

    for t_name, df in st.session_state.dataframes.items():
        if t_name not in st.session_state.anomalies_cache:
            with st.spinner(f"Scanning '{t_name}' for anomalies..."):
                flagged_df, summary = detect_anomalies_pipeline(df, random_state=42)
                st.session_state.anomalies_cache[t_name] = (flagged_df, summary)

        flagged_df, summary = st.session_state.anomalies_cache[t_name]
        if not flagged_df.empty:
            for idx, r in flagged_df.iterrows():
                # Extract identifying column
                id_col = next((c for c in df.columns if "id" in c.lower()), df.columns[0])
                row_id_val = str(r.get(id_col, idx))

                # Extract primary flagged numeric column and value
                col_name = "Multiple"
                col_val = "-"
                reasons = str(r.get("anomaly_reasons", ""))
                for candidate in ["revenue", "profit", "quantity", "discount", "price", "temperature_c"]:
                    if candidate in reasons.lower() and candidate in r:
                        col_name = candidate
                        val_num = r[candidate]
                        col_val = f"${val_num:,.2f}" if "rev" in candidate or "prof" in candidate or "price" in candidate else f"{val_num}"
                        break

                methods_str = str(r.get("anomaly_methods", "Ensemble"))
                confidence = "High Confidence" if r.get("methods_agreed", 1) >= 2 else "Possible"

                all_flagged_rows.append({
                    "Record": row_id_val,
                    "Table": t_name,
                    "Column": col_name,
                    "Value": col_val,
                    "Method": methods_str,
                    "Severity": confidence,
                    "Reason": reasons,
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

    # 4 Top Metrics: Total Records, Anomalies, High Confidence, Possible
    total_flagged = len(all_flagged_rows)
    high_conf_count = sum(1 for r in all_flagged_rows if r["Severity"] == "High Confidence")
    possible_count = total_flagged - high_conf_count

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Total Records</div>
                <div class="stat-value">{total_dataset_rows:,}</div>
                <div class="stat-sub">Across all tables</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        flagged_pct = (total_flagged / total_dataset_rows * 100) if total_dataset_rows else 0.0
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Anomalies</div>
                <div class="stat-value">{total_flagged:,}</div>
                <div class="stat-sub">{flagged_pct:.2f}% anomaly rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">High Confidence</div>
                <div class="stat-value">{high_conf_count}</div>
                <div class="stat-sub">≥2 methods agreed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="stat-tile">
                <div class="stat-label">Possible</div>
                <div class="stat-value">{possible_count}</div>
                <div class="stat-sub">Single detector flag</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    if not all_flagged_rows:
        st.success("No statistical or business rule anomalies detected across loaded tables.")
        return

    # Results Table Display: Record, Column, Value, Method, Severity, Reason
    display_data = []
    for r in all_flagged_rows:
        display_data.append({
            "Record": r["Record"],
            "Column": r["Column"],
            "Value": r["Value"],
            "Method": r["Method"],
            "Severity": r["Severity"],
            "Reason": r["Reason"],
        })

    anom_display_df = pd.DataFrame(display_data)
    st.dataframe(
        anom_display_df,
        use_container_width=True,
        column_config={
            "Reason": st.column_config.TextColumn("Reason", width="large"),
            "Severity": st.column_config.TextColumn("Severity", width="medium"),
            "Method": st.column_config.TextColumn("Method", width="medium"),
        },
        hide_index=True,
    )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Detailed Anomaly Record Inspector
    with st.expander("Inspect Detailed Anomaly Record", expanded=False):
        row_options = [f"{r['Table']} • {r['Record']} ({r['Severity']})" for r in all_flagged_rows]
        chosen = st.selectbox("Select anomalous record to inspect:", options=row_options)
        chosen_idx = row_options.index(chosen)
        selected_rec = all_flagged_rows[chosen_idx]["_full_record"]

        st.markdown(f"**Explanation:** {all_flagged_rows[chosen_idx]['Reason']}")

        # Format as 2-column key-value attribute table
        rec_df = pd.DataFrame([
            {"Attribute": k, "Value": str(v)}
            for k, v in selected_rec.items()
            if not k.startswith("anomaly_") and k != "methods_agreed"
        ])
        st.dataframe(rec_df, use_container_width=True, hide_index=True)
