"""Unit tests for Datalens UI components, theme styling, and schema join key detection."""

from pathlib import Path
import pandas as pd
import plotly.express as px
import pytest

from app.data.loader import load_csv_file
from app.ui.sidebar import detect_schema_join_keys
from app.ui.theme import apply_datalens_chart_styling, get_datalens_plotly_template
from app.llm.mock_provider import SmokeTestMockProvider

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

def test_detect_schema_join_keys():
    """Verify join key detector finds foreign keys across sales, customers, and products."""
    profiles = {}
    for fname in ["customers.csv", "products.csv", "sales.csv"]:
        fpath = SAMPLE_DATA_DIR / fname
        if fpath.exists():
            _, prof, tname, _ = load_csv_file(fpath)
            profiles[tname] = prof

    joins = detect_schema_join_keys(profiles)
    assert len(joins) >= 2, f"Expected at least 2 join relationships, found {len(joins)}"

    # Check sales-customers and sales-products joins
    join_str = " ".join([f"{t1}.{c1}->{t2}.{c2}" for t1, c1, t2, c2 in joins]).lower()
    assert "customer_id" in join_str
    assert "product_id" in join_str

def test_apply_datalens_chart_styling():
    """Verify Plotly figure receives Datalens template styling."""
    df = pd.DataFrame({"x": ["A", "B", "C"], "y": [10, 20, 30]})
    fig = px.bar(df, x="x", y="y", title="Test Bar")
    styled_fig = apply_datalens_chart_styling(fig)

    assert styled_fig.layout.paper_bgcolor == "#FFFFFF"
    assert styled_fig.layout.font.family == "Hanken Grotesk, sans-serif"
    assert styled_fig.layout.plot_bgcolor == "#FFFFFF"

def test_smoke_test_mock_provider():
    """Verify mock provider answers analytical questions deterministically."""
    from app.llm.base import LLMMessage

    provider = SmokeTestMockProvider()
    assert provider.get_model_name() == "mock-llama-3.3-70b-analyst"

    # Test question 1
    msgs = [LLMMessage(role="user", content="Which region generated the highest revenue?")]
    resp = provider.generate(msgs)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "execute_sql"
    assert "region" in resp.tool_calls[0].arguments["sql"]
