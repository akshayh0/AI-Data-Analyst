"""Unit tests for hybrid anomaly detection engine using ground-truth benchmarks and synthetic datasets."""

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

    # Verify each planted anomaly has high confidence and shows which methods agreed
    for item in ground_truth["anomalies"]:
        order_id = item["order_id"]
        row = flagged_df[flagged_df["Order ID"] == order_id].iloc[0]
        assert row["anomaly_confidence"] == "high", f"Planted anomaly {order_id} should have high confidence"
        assert row["methods_agreed"] >= 2, f"Planted anomaly {order_id} should have >= 2 methods agreeing"
        assert "Flagged by:" in row["anomaly_reasons"]
        assert len(row["anomaly_reasons"]) > 20

    # Calculate false-positive candidates
    non_planted_flagged = flagged_order_ids - planted_order_ids
    false_positive_count = len(non_planted_flagged)

    print(f"\n[Anomaly Benchmark] Caught {len(planted_order_ids)}/{len(planted_order_ids)} planted anomalies.")
    print(f"[Anomaly Benchmark] Total flagged: {len(flagged_df)}/{len(sales_df)} ({len(flagged_df)/len(sales_df)*100:.1f}%).")
    print(f"[Anomaly Benchmark] High confidence flags: {sum(flagged_df['anomaly_confidence'] == 'high')}.")
    print(f"[Anomaly Benchmark] Candidates beyond planted: {false_positive_count}.")

def test_anomaly_tool_generalization_on_synthetic_dataset():
    """Verify anomaly tool generalizes to completely different domain data with a planted spike."""
    # Synthetic IoT sensor dataset
    sensor_df = pd.DataFrame({
        "device_id": [f"DEV-{i:03d}" for i in range(1, 31)],
        "temperature_c": [
            21.2, 21.5, 21.0, 21.8, 22.0, 21.4, 21.6, 21.3, 21.9, 21.1,
            21.7, 21.4, 21.2, 21.5, 22.1, 21.3, 21.6, 21.8, 21.0, 21.5,
            21.4, 21.2, 21.7, 21.9, 21.3, 21.6, 21.1, 21.5, 21.4,
            88.5,  # Row 29: Planted extreme overheating spike
        ],
        "humidity_pct": [
            45.0, 46.2, 44.8, 45.5, 46.0, 45.1, 45.8, 44.9, 45.3, 46.1,
            45.2, 45.7, 44.6, 45.9, 46.3, 45.0, 45.4, 45.8, 44.7, 45.3,
            45.5, 45.1, 46.0, 45.2, 44.8, 45.6, 45.4, 45.0, 45.3,
            45.2,  # Normal humidity
        ],
    })

    flagged_df, summary = detect_anomalies_pipeline(sensor_df, random_state=42)

    assert not flagged_df.empty, "Expected planted spike to be detected"
    spike_row = flagged_df[flagged_df["device_id"] == "DEV-030"]
    assert not spike_row.empty, "DEV-030 overheating spike was not caught"

    spike_data = spike_row.iloc[0]
    assert spike_data["anomaly_confidence"] == "high"
    assert "temperature_c" in spike_data["anomaly_reasons"]
    assert "modified_z_score" in spike_data["anomaly_methods"]
    assert "iqr" in spike_data["anomaly_methods"]

def test_relative_margin_rule_only_active_when_both_columns_exist():
    """Verify relative margin rule triggers on negative margins and does not crash if only revenue exists."""
    df_with_both = pd.DataFrame({
        "revenue": [100.0, 200.0, 150.0, 120.0, 180.0, 110.0, 130.0, 140.0, 160.0, 50.0],
        "profit": [20.0, 40.0, 30.0, 25.0, 35.0, 22.0, 26.0, 28.0, 32.0, -100.0], # -200% margin on last row
    })
    flagged, _ = detect_anomalies_pipeline(df_with_both)
    last_row = flagged[flagged["revenue"] == 50.0].iloc[0]
    assert "relative_margin_rule" in last_row["anomaly_methods"]

    df_rev_only = pd.DataFrame({
        "revenue": [100.0, 200.0, 150.0, 120.0, 180.0, 110.0, 130.0, 140.0, 160.0, 1000.0],
    })
    flagged_rev, _ = detect_anomalies_pipeline(df_rev_only)
    assert not flagged_rev.empty
    assert "relative_margin_rule" not in flagged_rev.iloc[0]["anomaly_reasons"]

def test_skip_id_and_constant_columns():
    df = pd.DataFrame({
        "order_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "constant_col": [42.0] * 10,
        "revenue": [10.0, 12.0, 11.0, 9.0, 10.5, 11.2, 9.8, 10.1, 10.3, 1000.0],
    })

    flagged_df, summary = detect_anomalies_pipeline(df)
    assert len(flagged_df) == 1
    assert "revenue" in flagged_df.iloc[0]["anomaly_reasons"]
    assert "order_id" not in flagged_df.iloc[0]["anomaly_methods"]
    assert "constant_col" not in flagged_df.iloc[0]["anomaly_methods"]

def test_small_sample_size_handling():
    small_df = pd.DataFrame({
        "metric": [10.0, 11.0, 12.0, 10.5],
    })
    flagged_df, summary = detect_anomalies_pipeline(small_df)
    assert isinstance(flagged_df, pd.DataFrame)
