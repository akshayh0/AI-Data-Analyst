"""Regression test for smoke test independent ground-truth calculation."""

from pathlib import Path
import pytest
from app.data.loader import load_csv_file
from app.tools.sql_tool import DuckDBManager
from scripts.live_smoke_test import compute_independent_ground_truth

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

def test_compute_independent_ground_truth_regression():
    """Verify compute_independent_ground_truth works with DuckDBManager.execute_query API."""
    db = DuckDBManager()
    sales_df = None

    for fname in ["customers.csv", "products.csv", "sales.csv"]:
        fpath = SAMPLE_DATA_DIR / fname
        assert fpath.exists(), f"Sample dataset {fname} must exist"
        df, _, tname, _ = load_csv_file(fpath)
        db.register_dataframe(tname, df)
        if tname == "sales":
            sales_df = df

    assert sales_df is not None, "sales dataframe must be loaded"

    # Compute ground truth using the real DuckDBManager API
    gt = compute_independent_ground_truth(db, sales_df)

    # Q1: Region with highest revenue
    assert "q1" in gt
    assert gt["q1"]["top_region"] == "West"
    assert round(gt["q1"]["top_revenue"], 2) == 674429.67

    # Q2: Monthly sales trends
    assert "q2" in gt
    assert gt["q2"]["total_months"] == 24
    assert gt["q2"]["peak_month"] == "2023-11"
    assert round(gt["q2"]["peak_revenue"], 2) == 730918.48

    # Q3: Underperforming products
    assert "q3" in gt
    assert len(gt["q3"]["underperforming_products"]) == 5
    assert len(gt["q3"]["underperforming_names"]) == 5

    # Q4: Top 5 customers
    assert "q4" in gt
    assert len(gt["q4"]["top_5_names"]) == 5
    assert gt["q4"]["top_1_name"] == "Karen Harris"
    assert round(gt["q4"]["top_1_spent"], 2) == 394688.75

    # Q6: Anomaly detection ground truth
    assert "q6" in gt
    assert gt["q6"]["total_anomalies"] > 0
