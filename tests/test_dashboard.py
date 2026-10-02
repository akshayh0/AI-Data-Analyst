"""Unit tests for automated dashboard inspection, KPIs, and chart generation."""

import pandas as pd
import pytest

from app.ui.dashboard_tab import (
    format_display_name,
    format_metric_value,
    inspect_dataset_columns,
    generate_kpi_cards,
    generate_dashboard_charts,
)
from app.tools.chart_tool import build_plotly_chart
from app.ui.theme import apply_datalens_chart_styling


def test_format_display_name():
    """Verify snake_case and messy column names are formatted to Title Case."""
    assert format_display_name("total_revenue") == "Total Revenue"
    assert format_display_name("customer_segment") == "Customer Segment"
    assert format_display_name("id") == "Id"
    assert format_display_name("col") == "Col"


def test_format_metric_value():
    """Verify numeric metric formatting with suffixes and commas."""
    assert format_metric_value(None) == "—"
    assert format_metric_value(float("nan")) == "—"
    assert format_metric_value(500) == "500"
    assert format_metric_value(15420) == "15,420"
    assert format_metric_value(2500000) == "2.50M"
    assert format_metric_value(3500000000) == "3.50B"
    assert format_metric_value(42.567) == "42.57"


def test_inspect_dataset_columns_multi_type():
    """Verify inspection detects date, numeric, and categorical columns on generic datasets."""
    df = pd.DataFrame({
        "order_id": [1, 2, 3, 4, 5],
        "order_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "region": ["North", "South", "North", "East", "West"],
        "revenue": [120.5, 340.0, 95.2, 510.0, 230.1],
        "quantity": [2, 5, 1, 8, 3],
    })

    cols = inspect_dataset_columns(df)

    assert "order_date" in cols["date_columns"]
    assert "revenue" in cols["numeric_columns"]
    assert "quantity" in cols["numeric_columns"]
    assert "region" in cols["categorical_columns"]
    # order_id is an ID and not prioritized over quantitative revenue/quantity
    assert cols["numeric_columns"][0] in ["revenue", "quantity"]


def test_inspect_dataset_columns_no_dates():
    """Verify dataset with no date columns handles inspection without errors."""
    df = pd.DataFrame({
        "item": ["Alpha", "Beta", "Gamma"],
        "score_a": [10.0, 20.0, 30.0],
        "score_b": [1.5, 2.5, 3.5],
    })

    cols = inspect_dataset_columns(df)
    assert len(cols["date_columns"]) == 0
    assert "score_a" in cols["numeric_columns"]
    assert "score_b" in cols["numeric_columns"]
    assert "item" in cols["categorical_columns"]


def test_inspect_dataset_columns_categorical_only():
    """Verify inspection handles non-numeric datasets gracefully."""
    df = pd.DataFrame({
        "status": ["active", "pending", "active", "closed"],
        "priority": ["high", "low", "medium", "high"],
    })

    cols = inspect_dataset_columns(df)
    assert len(cols["numeric_columns"]) == 0
    assert len(cols["date_columns"]) == 0
    assert "status" in cols["categorical_columns"]
    assert "priority" in cols["categorical_columns"]


def test_generate_kpi_cards():
    """Verify KPI cards render 4 valid metrics with correct values."""
    df = pd.DataFrame({
        "cat": ["A", "B", "A", "C"],
        "val": [100.0, 200.0, 300.0, 400.0],
        "qty": [1, 2, 3, 4],
    })
    cols = inspect_dataset_columns(df)
    kpis = generate_kpi_cards(df, cols["numeric_columns"], cols["categorical_columns"])

    assert len(kpis) == 4
    # Check Total Records
    assert kpis[0]["label"] == "Total Records"
    assert kpis[0]["value"] == "4"

    # Check Total Numeric
    assert "Total" in kpis[1]["label"]
    assert "1,000" in kpis[1]["value"]

    # Check Average Numeric
    assert "Average" in kpis[2]["label"]

    # Check Unique Categories
    assert "Unique" in kpis[3]["label"]
    assert kpis[3]["value"] == "3"


def test_generate_dashboard_charts_full():
    """Verify bar, line, pie, and scatter charts are generated when suitable columns exist."""
    df = pd.DataFrame({
        "txn_date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "category": ["Hardware", "Software"] * 5,
        "amount": [150.0, 300.0, 220.0, 450.0, 180.0, 520.0, 90.0, 310.0, 410.0, 290.0],
        "units": [1, 3, 2, 5, 2, 6, 1, 4, 5, 3],
    })

    cols = inspect_dataset_columns(df)
    charts = generate_dashboard_charts(
        df,
        cols["date_columns"],
        cols["numeric_columns"],
        cols["categorical_columns"],
    )

    chart_types = [spec["chart_type"] for spec, _, _ in charts]
    assert "bar" in chart_types
    assert "line" in chart_types
    assert "pie" in chart_types
    assert "scatter" in chart_types

    # Ensure every generated chart builds successfully with existing build_plotly_chart
    for spec, plot_df, key in charts:
        fig = build_plotly_chart(spec, plot_df)
        styled_fig = apply_datalens_chart_styling(fig)
        assert styled_fig is not None


def test_generate_dashboard_charts_graceful_partial():
    """Verify charts without dates or without scatter columns still generate available charts."""
    df = pd.DataFrame({
        "type": ["Gold", "Silver", "Bronze"],
        "metric": [100.0, 50.0, 25.0],
    })
    cols = inspect_dataset_columns(df)
    charts = generate_dashboard_charts(
        df,
        cols["date_columns"],
        cols["numeric_columns"],
        cols["categorical_columns"],
    )

    chart_types = [spec["chart_type"] for spec, _, _ in charts]
    # No date -> no line chart
    assert "line" not in chart_types
    # Only 1 numeric -> no scatter chart
    assert "scatter" not in chart_types
    # Bar chart and pie chart should exist
    assert "bar" in chart_types
    assert "pie" in chart_types
