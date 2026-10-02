"""Datalens Dashboard tab component: Automated dynamic KPIs and chart visualizations."""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st

from app.tools.chart_tool import build_plotly_chart
from app.ui.theme import apply_datalens_chart_styling


def format_display_name(col_name: str) -> str:
    """Format snake_case or underscored column names for human-readable display."""
    clean = str(col_name).replace("_", " ").strip()
    return clean.title() if clean else str(col_name)


def format_metric_value(val: Any) -> str:
    """Format numeric KPI values cleanly with commas or suffixes."""
    if val is None or pd.isna(val):
        return "—"
    try:
        float_val = float(val)
        if abs(float_val) >= 1_000_000_000:
            return f"{float_val / 1_000_000_000:.2f}B"
        if abs(float_val) >= 1_000_000:
            return f"{float_val / 1_000_000:.2f}M"
        if abs(float_val) >= 10_000:
            return f"{float_val:,.0f}"
        if float_val.is_integer():
            return f"{int(float_val):,}"
        return f"{float_val:,.2f}"
    except (ValueError, TypeError, OverflowError):
        return str(val)


def inspect_dataset_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Dynamically inspect a DataFrame to identify date, useful numeric, and categorical columns.
    Excludes pure ID columns from primary quantitative metrics where appropriate.
    """
    date_cols: List[str] = []
    numeric_cols: List[str] = []
    id_numeric_cols: List[str] = []
    categorical_cols: List[str] = []

    total_rows = len(df)

    # 1. Detect Date / Datetime columns
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        if non_null.empty:
            continue

        if pd.api.types.is_datetime64_any_dtype(series):
            date_cols.append(col)
            continue

        # Check for string date hints
        col_lower = str(col).lower()
        date_keywords = ("date", "time", "timestamp", "year", "month", "day", "created", "period")
        has_date_keyword = any(k in col_lower for k in date_keywords)

        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            sample = non_null.head(20).astype(str)
            # Avoid testing long paragraphs or non-date strings
            if sample.str.len().max() <= 35:
                # If name suggests date or contains separators commonly in dates
                if has_date_keyword or sample.str.contains(r"[-/:T]").any():
                    try:
                        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
                        if parsed.notna().mean() >= 0.8:
                            date_cols.append(col)
                            continue
                    except Exception:
                        pass

    # 2. Detect Numeric & Categorical columns
    for col in df.columns:
        if col in date_cols:
            continue

        series = df[col]
        non_null = series.dropna()
        if non_null.empty:
            continue

        col_lower = str(col).lower()
        n_unique = int(non_null.nunique())

        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            # Check if column is an ID or index-like column
            is_id = False
            if col_lower.endswith("_id") or col_lower == "id" or col_lower.endswith("_key") or col_lower.endswith("_no"):
                is_id = True
            elif total_rows > 30 and n_unique == total_rows:
                # 100% unique numeric is likely an ID or row number
                is_id = True

            # Must have non-zero variance to be a useful quantitative metric
            try:
                if non_null.min() == non_null.max():
                    # Constant value
                    continue
            except Exception:
                pass

            if is_id:
                id_numeric_cols.append(col)
            else:
                numeric_cols.append(col)
        else:
            # Categorical / string / boolean candidates
            # Useful categories have 2 to 50 unique values and are not unique keys per row in large tables
            is_high_card_id = (total_rows > 30 and n_unique >= total_rows * 0.95)
            if 1 < n_unique <= 50 and not is_high_card_id:
                # Avoid long text / comments
                sample_str = non_null.head(10).astype(str)
                if sample_str.str.len().mean() < 60:
                    categorical_cols.append(col)

    # Sort useful numerics: prioritize floating point or larger variety metrics
    numeric_cols.sort(
        key=lambda c: (
            pd.api.types.is_float_dtype(df[c]),
            df[c].dropna().nunique(),
        ),
        reverse=True,
    )

    # If no non-ID numeric columns exist, fallback to ID numerics so we don't return empty
    useful_numerics = numeric_cols if numeric_cols else id_numeric_cols

    # Sort categoricals: prioritize columns with 2 to 15 categories (ideal for visualization)
    categorical_cols.sort(
        key=lambda c: (
            2 <= df[c].dropna().nunique() <= 15,
            -abs(df[c].dropna().nunique() - 6),
        ),
        reverse=True,
    )

    return {
        "date_columns": date_cols,
        "numeric_columns": useful_numerics,
        "categorical_columns": categorical_cols,
    }


def generate_kpi_cards(
    df: pd.DataFrame,
    numeric_cols: List[str],
    categorical_cols: List[str],
) -> List[Dict[str, str]]:
    """
    Generate up to 4 high-value KPI metrics from the dataset:
    - Total Records
    - Numeric Total
    - Numeric Average
    - Unique Categories
    """
    kpis: List[Dict[str, str]] = []
    total_records = len(df)

    # 1. Total Records
    kpis.append({
        "label": "Total Records",
        "value": f"{total_records:,}",
        "sub": "Ingested dataset rows",
    })

    # 2. Numeric Total
    if numeric_cols:
        primary_num = numeric_cols[0]
        try:
            total_sum = df[primary_num].sum(skipna=True)
            kpis.append({
                "label": f"Total {format_display_name(primary_num)}",
                "value": format_metric_value(total_sum),
                "sub": f"Sum across records",
            })
        except Exception:
            pass

    # 3. Numeric Average
    if numeric_cols:
        # Use primary or second numeric column for average
        avg_col = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
        try:
            mean_val = df[avg_col].mean(skipna=True)
            kpis.append({
                "label": f"Average {format_display_name(avg_col)}",
                "value": format_metric_value(mean_val),
                "sub": f"Mean per record",
            })
        except Exception:
            pass

    # 4. Unique Categories
    if categorical_cols:
        primary_cat = categorical_cols[0]
        try:
            cat_count = int(df[primary_cat].dropna().nunique())
            kpis.append({
                "label": f"Unique {format_display_name(primary_cat)}",
                "value": f"{cat_count:,}",
                "sub": f"Distinct categories",
            })
        except Exception:
            pass

    # Graceful fallback to guarantee 4 cards if some types were absent
    if len(kpis) < 4 and len(categorical_cols) > 1:
        second_cat = categorical_cols[1]
        try:
            kpis.append({
                "label": f"Unique {format_display_name(second_cat)}",
                "value": f"{int(df[second_cat].dropna().nunique()):,}",
                "sub": f"Distinct categories",
            })
        except Exception:
            pass

    if len(kpis) < 4:
        kpis.append({
            "label": "Total Attributes",
            "value": f"{len(df.columns)}",
            "sub": "Detected columns",
        })

    if len(kpis) < 4:
        total_nulls = int(df.isna().sum().sum())
        kpis.append({
            "label": "Missing Values",
            "value": f"{total_nulls:,}",
            "sub": "Total null cells",
        })

    return kpis[:4]


def generate_dashboard_charts(
    df: pd.DataFrame,
    date_cols: List[str],
    numeric_cols: List[str],
    categorical_cols: List[str],
) -> List[Tuple[Dict[str, Any], pd.DataFrame, str]]:
    """
    Automatically select and construct chart configurations:
    - Bar chart for categorical vs numeric data (or frequency)
    - Line chart when date column exists
    - Pie chart when suitable categorical data exists
    - Scatter chart when at least two useful numeric columns exist

    Returns:
        List of (spec, plot_df, unique_key_suffix)
    """
    charts: List[Tuple[Dict[str, Any], pd.DataFrame, str]] = []

    # 1. Bar Chart: Categorical vs Numeric Data (or Categorical Frequency)
    if categorical_cols:
        bar_cat = categorical_cols[0]
        if numeric_cols:
            bar_num = numeric_cols[0]
            try:
                agg_df = (
                    df.dropna(subset=[bar_cat, bar_num])
                    .groupby(bar_cat, as_index=False)[bar_num]
                    .sum()
                    .sort_values(by=bar_num, ascending=False)
                    .head(10)
                )
                if not agg_df.empty:
                    spec = {
                        "chart_type": "bar",
                        "x": bar_cat,
                        "y": bar_num,
                        "title": f"Top {format_display_name(bar_cat)} by Total {format_display_name(bar_num)}",
                    }
                    charts.append((spec, agg_df, f"bar_{bar_cat}_{bar_num}"))
            except Exception:
                pass
        else:
            # Frequency count bar chart
            try:
                counts = df[bar_cat].dropna().value_counts().head(10).reset_index()
                counts.columns = [bar_cat, "record_count"]
                spec = {
                    "chart_type": "bar",
                    "x": bar_cat,
                    "y": "record_count",
                    "title": f"Top {format_display_name(bar_cat)} by Record Count",
                }
                charts.append((spec, counts, f"bar_{bar_cat}_freq"))
            except Exception:
                pass

    # 2. Line Chart: When a Date column exists
    if date_cols:
        date_col = date_cols[0]
        try:
            temp_df = df.copy()
            temp_df["_parsed_date"] = pd.to_datetime(temp_df[date_col], errors="coerce", format="mixed")
            valid_dates = temp_df.dropna(subset=["_parsed_date"])

            if not valid_dates.empty:
                if numeric_cols:
                    line_num = numeric_cols[0]
                    # Check cardinality of dates
                    unique_dates = valid_dates["_parsed_date"].dt.date.nunique()
                    if unique_dates > 60:
                        valid_dates["timeline_period"] = valid_dates["_parsed_date"].dt.strftime("%Y-%m")
                    else:
                        valid_dates["timeline_period"] = valid_dates["_parsed_date"].dt.strftime("%Y-%m-%d")

                    line_df = (
                        valid_dates.groupby("timeline_period", as_index=False)[line_num]
                        .sum()
                        .sort_values(by="timeline_period")
                    )
                    if not line_df.empty:
                        spec = {
                            "chart_type": "line",
                            "x": "timeline_period",
                            "y": line_num,
                            "title": f"{format_display_name(line_num)} Trend Over Time",
                        }
                        charts.append((spec, line_df, f"line_{date_col}_{line_num}"))
                else:
                    valid_dates["record_count"] = 1
                    valid_dates["timeline_period"] = valid_dates["_parsed_date"].dt.strftime("%Y-%m-%d")
                    line_df = (
                        valid_dates.groupby("timeline_period", as_index=False)["record_count"]
                        .sum()
                        .sort_values(by="timeline_period")
                    )
                    if not line_df.empty:
                        spec = {
                            "chart_type": "line",
                            "x": "timeline_period",
                            "y": "record_count",
                            "title": "Record Volume Over Time",
                        }
                        charts.append((spec, line_df, f"line_{date_col}_count"))
        except Exception:
            pass

    # 3. Pie Chart: When suitable categorical data exists
    if categorical_cols:
        # Choose a suitable categorical column (ideally with 2 to 12 distinct values)
        pie_cat = categorical_cols[0]
        for c in categorical_cols:
            n_unq = df[c].dropna().nunique()
            if 2 <= n_unq <= 10:
                pie_cat = c
                break

        if numeric_cols:
            pie_num = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
            pie_df = df[[pie_cat, pie_num]].dropna().copy()
            if not pie_df.empty:
                spec = {
                    "chart_type": "pie",
                    "x": pie_cat,
                    "y": pie_num,
                    "title": f"Distribution of {format_display_name(pie_num)} by {format_display_name(pie_cat)}",
                }
                charts.append((spec, pie_df, f"pie_{pie_cat}_{pie_num}"))
        else:
            pie_df = df[[pie_cat]].dropna().copy()
            pie_df["record_count"] = 1
            if not pie_df.empty:
                spec = {
                    "chart_type": "pie",
                    "x": pie_cat,
                    "y": "record_count",
                    "title": f"Share by {format_display_name(pie_cat)}",
                }
                charts.append((spec, pie_df, f"pie_{pie_cat}_count"))

    # 4. Scatter Chart: When at least two useful numeric columns exist
    if len(numeric_cols) >= 2:
        num_x = numeric_cols[0]
        num_y = numeric_cols[1]
        try:
            scatter_cols = [num_x, num_y]
            color_col = None
            if categorical_cols and df[categorical_cols[0]].dropna().nunique() <= 8:
                color_col = categorical_cols[0]
                scatter_cols.append(color_col)

            scatter_df = df[scatter_cols].dropna().copy()
            if not scatter_df.empty:
                spec = {
                    "chart_type": "scatter",
                    "x": num_x,
                    "y": num_y,
                    "title": f"{format_display_name(num_y)} vs {format_display_name(num_x)}",
                }
                if color_col:
                    spec["color"] = color_col

                charts.append((spec, scatter_df, f"scatter_{num_x}_{num_y}"))
        except Exception:
            pass

    return charts


def render_dashboard_tab():
    """Render automated dynamic analytics dashboard for uploaded CSV datasets."""
    if not st.session_state.table_profiles:
        st.info("No datasets loaded. Please upload a CSV file from the sidebar.")
        return

    # Header and Refresh Action
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(
            """
            <div style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700; color: #0F172A;">
                Analytics Dashboard
            </div>
            <div style="font-size: 0.825rem; color: #64748B;">
                Automatically generated insights from your uploaded dataset.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with head_col2:
        if st.button("Refresh Dashboard", type="secondary", use_container_width=True, key="dashboard_refresh_btn"):
            st.rerun()

    # Active Table Selection (if multiple datasets loaded)
    tables = list(st.session_state.table_profiles.keys())
    if len(tables) > 1:
        selected_table = st.selectbox(
            "Select dataset for dashboard",
            options=tables,
            format_func=lambda t: f"{t} ({len(st.session_state.dataframes[t]):,} rows · {len(st.session_state.dataframes[t].columns)} columns)",
            key="dashboard_table_select",
        )
    else:
        selected_table = tables[0]

    df = st.session_state.dataframes.get(selected_table)
    if df is None or df.empty:
        st.warning("Selected dataset contains no records.")
        return

    # Dataset Meta Pill Badge
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 8px; margin: 0.5rem 0 1rem 0;">
            <span class="badge-teal">{selected_table}</span>
            <span class="badge-stone">{len(df):,} rows</span>
            <span class="badge-stone">{len(df.columns)} columns</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Automatic Column Inspection
    columns_info = inspect_dataset_columns(df)
    date_cols = columns_info["date_columns"]
    numeric_cols = columns_info["numeric_columns"]
    categorical_cols = columns_info["categorical_columns"]

    # 2. KPI Summary Cards Grid
    kpis = generate_kpi_cards(df, numeric_cols, categorical_cols)
    kpi_cols = st.columns(len(kpis))
    for idx, kpi in enumerate(kpis):
        with kpi_cols[idx]:
            st.markdown(
                f"""
                <div class="stat-tile">
                    <div class="stat-label">{kpi['label']}</div>
                    <div class="stat-value">{kpi['value']}</div>
                    <div class="stat-sub">{kpi['sub']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # 3. Visual Charts Grid
    charts = generate_dashboard_charts(df, date_cols, numeric_cols, categorical_cols)

    if not charts:
        st.info("No suitable numeric, categorical, or date columns found to generate automated charts for this dataset.")
        return

    st.markdown(
        f"<div style='font-family: var(--font-heading); font-size: 0.95rem; font-weight: 700; color: #0F172A; margin-bottom: 0.75rem;'>Visual Insights ({len(charts)} charts)</div>",
        unsafe_allow_html=True,
    )

    # Render charts in a responsive 2-column grid
    for i in range(0, len(charts), 2):
        row_charts = charts[i : i + 2]
        if len(row_charts) == 2:
            col_left, col_right = st.columns(2)
            with col_left:
                _render_single_chart(row_charts[0], idx=i)
            with col_right:
                _render_single_chart(row_charts[1], idx=i + 1)
        else:
            col_single, _ = st.columns([1, 1])
            with col_single:
                _render_single_chart(row_charts[0], idx=i)


def _render_single_chart(chart_info: Tuple[Dict[str, Any], pd.DataFrame, str], idx: int):
    """Render a single chart inside a clean container card with DataLens styling."""
    spec, plot_df, key_suffix = chart_info
    with st.container(border=True):
        try:
            fig = build_plotly_chart(spec, plot_df)
            fig = apply_datalens_chart_styling(fig)
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"dashboard_chart_{idx}_{key_suffix}",
                config={"displayModeBar": False},
            )
        except Exception as exc:
            st.caption(f"Chart render notice: {exc}")
