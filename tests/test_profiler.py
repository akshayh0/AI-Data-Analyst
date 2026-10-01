"""Unit tests for dataset profiling and token-efficient schema representation."""

import io
import pandas as pd
import pytest
from app.data.loader import load_csv_file
from app.data.profiler import profile_dataframe

def test_profile_dataframe_metrics():
    df = pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5],
        "category": ["A", "B", "A", None, "B"],
        "revenue": [100.5, 200.0, 50.25, 400.0, 150.0],
    })

    profile = profile_dataframe(df, table_name="test_sales", filename="test_sales.csv")

    assert profile.table_name == "test_sales"
    assert profile.row_count == 5
    assert profile.column_count == 3

    # Check null calculation
    assert profile.columns["category"].null_count == 1
    assert profile.columns["category"].null_percentage == 20.0
    assert profile.columns["category"].unique_count == 2

    # Check numeric stats
    assert profile.columns["revenue"].null_count == 0
    assert profile.columns["revenue"].min_value == 50.25
    assert profile.columns["revenue"].max_value == 400.0
    assert profile.columns["revenue"].mean_value == pytest.approx(180.15, 0.01)

def test_profile_to_llm_schema_prompt():
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "name": [f"item_{i}" for i in range(1, 11)],
    })

    profile = profile_dataframe(df, table_name="large_data", filename="large.csv")
    prompt_str = profile.to_llm_schema_prompt(max_sample_rows=3)

    assert "Table: `large_data`" in prompt_str
    assert "Columns:" in prompt_str
    assert "- `id`" in prompt_str
    assert "- `name`" in prompt_str
    assert "Sample data (3 rows):" in prompt_str

    # Verify that only first 3 rows are printed in the sample table section
    sample_section = prompt_str.split("Sample data (3 rows):\n")[1]
    assert "item_1" in sample_section
    assert "item_3" in sample_section
    assert "item_4" not in sample_section
    assert "item_10" not in sample_section

def test_load_csv_file_integration():
    csv_content = b"User ID,Total Spend ($),Signup\n101,250.50,2023-01-01\n102,120.00,2023-01-05\n"
    df, profile, table_name, mapping = load_csv_file(csv_content, filename="users_spend.csv")

    assert table_name == "users_spend"
    assert list(df.columns) == ["user_id", "total_spend_usd", "signup"]
    assert profile.row_count == 2
    assert profile.column_count == 3
    assert mapping["Total Spend ($)"] == "total_spend_usd"
