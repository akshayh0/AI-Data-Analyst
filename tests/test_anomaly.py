"""Unit tests for hybrid anomaly detection engine using ground-truth benchmarks."""

import json
from pathlib import Path
import pandas as pd
import pytest

from app.tools.anomaly_tool import detect_anomalies_pipeline

DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

def test_planted_anomalies_detection_from_ground_truth():
    sales_path = DATA_DIR / "sales.csv"
    gt_path = DATA_DIR / "anomalies_ground_truth.json"

    assert sales_path.exists(), "sales.csv missing"
    assert gt_path.exists(), "anomalies_ground_truth.json missing"

    sales_df = pd.read_csv(sales_path)
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Run anomaly pipeline on sales dataset
    flagged_df, summary = detect_anomalies_pipeline(sales_df, random_state=42)

    assert not flagged_df.empty, "Expected anomalies to be detected"
    flagged_order_ids = set(flagged_df["Order ID"])

    planted_order_ids = {item["order_id"] for item in ground_truth["anomalies"]}

    # Assert 100% of planted anomalies are caught
    missing_anomalies = planted_order_ids - flagged_order_ids
    assert not missing_anomalies, f"Failed to detect planted anomalies: {missing_anomalies}"

    # Verify each planted anomaly has a clear human reason
    for item in ground_truth["anomalies"]:
        order_id = item["order_id"]
        row = flagged_df[flagged_df["Order ID"] == order_id].iloc[0]
        reason = row["anomaly_reasons"]
        assert len(reason) > 10, f"Reason too brief for {order_id}: {reason}"

    # Calculate and report false-positive count
    non_planted_flagged = flagged_order_ids - planted_order_ids
    false_positive_count = len(non_planted_flagged)
    total_rows = len(sales_df)

    # Print for test output report
    print(f"\n[Anomaly Benchmark] Caught {len(planted_order_ids)}/{len(planted_order_ids)} planted anomalies.")
    print(f"[Anomaly Benchmark] Total flagged: {len(flagged_df)}/{total_rows} ({len(flagged_df)/total_rows*100:.1f}%).")
    print(f"[Anomaly Benchmark] False-positive candidates (natural data variance): {false_positive_count}.")

    # False positive rate should be conservative (< 3% of dataset)
    assert false_positive_count < 30, f"Too many false positives: {false_positive_count}"

def test_skip_id_and_constant_columns():
    df = pd.DataFrame({
        "order_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "constant_col": [42.0] * 10,
        "revenue": [10.0, 12.0, 11.0, 9.0, 10.5, 11.2, 9.8, 10.1, 10.3, 1000.0],
    })

    flagged_df, summary = detect_anomalies_pipeline(df)
    assert len(flagged_df) == 1
    # Check that anomaly reason is on revenue, not order_id or constant_col
    assert "revenue" in flagged_df.iloc[0]["anomaly_reasons"]
    assert "order_id" not in flagged_df.iloc[0]["anomaly_reasons"]
    assert "constant_col" not in flagged_df.iloc[0]["anomaly_reasons"]

def test_small_sample_size_handling():
    small_df = pd.DataFrame({
        "metric": [10.0, 11.0, 12.0, 10.5],
    })
    # Should handle gracefully without crashing Isolation Forest
    flagged_df, summary = detect_anomalies_pipeline(small_df)
    assert isinstance(flagged_df, pd.DataFrame)
