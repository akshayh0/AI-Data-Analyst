"""Unit tests for Plotly chart generator and specification validator."""

import pandas as pd
import pytest
import plotly.graph_objects as go
from app.tools.chart_tool import (
    ChartValidationError,
    build_plotly_chart,
)

@pytest.fixture
def sample_sales_data():
    return pd.DataFrame({
        "region": ["North", "South", "East", "West", "Central", "Overseas", "Remote", "Unknown"],
        "revenue": [5000.0, 3200.0, 4100.0, 6800.0, 1500.0, 800.0, 400.0, 200.0],
        "quantity": [50, 32, 41, 68, 15, 8, 4, 2],
    })

def test_build_valid_bar_chart(sample_sales_data):
    spec = {
        "chart_type": "bar",
        "x": "region",
        "y": "revenue",
        "title": "Revenue by Region",
    }
    fig = build_plotly_chart(spec, sample_sales_data)
    assert isinstance(fig, go.Figure)
    assert fig.layout.title.text == "Revenue by Region"

def test_build_valid_line_chart(sample_sales_data):
    spec = {
        "chart_type": "line",
        "x": "quantity",
        "y": "revenue",
        "title": "Revenue vs Quantity",
    }
    fig = build_plotly_chart(spec, sample_sales_data)
    assert isinstance(fig, go.Figure)

def test_build_valid_pie_chart_top_n_other(sample_sales_data):
    # 8 regions provided -> top 6 kept, 2 smallest grouped into 'Other'
    spec = {
        "chart_type": "pie",
        "x": "region",
        "y": "revenue",
        "title": "Revenue Share",
    }
    fig = build_plotly_chart(spec, sample_sales_data)
    assert isinstance(fig, go.Figure)
    labels = fig.data[0].labels
    assert "Other" in labels
    assert len(labels) == 7  # 6 top + 1 Other

def test_invalid_chart_type(sample_sales_data):
    spec = {
        "chart_type": "bubble_3d",
        "x": "region",
        "y": "revenue",
    }
    with pytest.raises(ChartValidationError, match="Unsupported chart type"):
        build_plotly_chart(spec, sample_sales_data)

def test_missing_column_error(sample_sales_data):
    spec = {
        "chart_type": "bar",
        "x": "non_existent_column",
        "y": "revenue",
    }
    with pytest.raises(ChartValidationError, match="X-axis column 'non_existent_column' not found"):
        build_plotly_chart(spec, sample_sales_data)

def test_empty_dataframe_chart():
    empty_df = pd.DataFrame()
    spec = {
        "chart_type": "bar",
        "x": "col1",
        "y": "col2",
        "title": "Empty Chart",
    }
    fig = build_plotly_chart(spec, empty_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.layout.annotations) > 0
    assert "No data available" in fig.layout.annotations[0].text
