"""Unit tests for data quality audit tool and health score computation."""

import pandas as pd
import pytest
from app.tools.quality_tool import generate_quality_report

def test_generate_quality_report_clean_data():
    df = pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "sales": [100.0, 150.0, 200.0, 120.0, 180.0],
    })
    report_md, quality_df = generate_quality_report(df, "clean_table")

    assert isinstance(quality_df, pd.DataFrame)
    assert "Overall Health Score" in report_md
    assert "clean_table" in report_md
    assert (quality_df["status"] == "PASS").any()

def test_generate_quality_report_with_nulls_and_duplicates():
    df = pd.DataFrame({
        "item": ["A", "B", "A", None, None],
        "quantity": [10, -5, 10, 20, 30],  # Negative quantity planted + duplicate row
    })
    report_md, quality_df = generate_quality_report(df, "dirty_table")

    # Check duplicate detection
    dup_row = quality_df[quality_df["check"] == "Duplicate Rows"]
    assert not dup_row.empty

    # Check null detection
    null_row = quality_df[quality_df["check"] == "Missing Values"]
    assert not null_row.empty

    # Check negative value detection
    neg_row = quality_df[quality_df["check"] == "Invalid Negative Value"]
    assert not neg_row.empty
    assert neg_row.iloc[0]["status"] == "FAIL"

def test_empty_dataframe_quality_report():
    empty_df = pd.DataFrame()
    report_md, quality_df = generate_quality_report(empty_df, "empty_table")
    assert "empty" in report_md.lower()
    assert quality_df.empty
