"""Verification script for sample datasets integrity and constraints."""

import json
from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

def verify_datasets():
    customers_path = DATA_DIR / "customers.csv"
    products_path = DATA_DIR / "products.csv"
    sales_path = DATA_DIR / "sales.csv"
    anomalies_path = DATA_DIR / "anomalies_ground_truth.json"

    assert customers_path.exists(), "customers.csv missing"
    assert products_path.exists(), "products.csv missing"
    assert sales_path.exists(), "sales.csv missing"
    assert anomalies_path.exists(), "anomalies_ground_truth.json missing"

    customers_df = pd.read_csv(customers_path)
    products_df = pd.read_csv(products_path)
    sales_df = pd.read_csv(sales_path)

    with open(anomalies_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # 1. Foreign Keys
    cust_ids = set(customers_df["Customer ID"].dropna())
    prod_ids = set(products_df["Product ID"].dropna())

    sales_cust_ids = set(sales_df["Customer ID"].dropna())
    sales_prod_ids = set(sales_df["Product ID"].dropna())

    missing_custs = sales_cust_ids - cust_ids
    assert not missing_custs, f"Unresolved customer IDs in sales: {missing_custs}"

    missing_prods = sales_prod_ids - prod_ids
    assert not missing_prods, f"Unresolved product IDs in sales: {missing_prods}"

    # 2. Date span and region availability
    dates = pd.to_datetime(sales_df["Order Date"])
    month_span = (dates.max().year - dates.min().year) * 12 + dates.max().month - dates.min().month
    assert month_span >= 12, f"Expected >12 months span, got {month_span}"
    assert "Region" in customers_df.columns, "Customer table missing Region column"

    # 3. Product sales distribution (some products underperforming)
    product_sales_counts = sales_df.groupby("Product ID")["Quantity"].sum()
    all_pids = set(products_df["Product ID"])
    sold_pids = set(product_sales_counts.index)
    unsold_or_low = [pid for pid in all_pids if product_sales_counts.get(pid, 0) <= 2]
    assert len(unsold_or_low) >= 5, f"Expected at least 5 low/zero sales products, found {len(unsold_or_low)}"

    # 4. Revenue & Profit math for normal rows
    anomaly_order_ids = {a["order_id"] for a in ground_truth["anomalies"]}
    normal_sales = sales_df[~sales_df["Order ID"].isin(anomaly_order_ids)]

    for idx, row in normal_sales.head(100).iterrows():
        qty = row["Quantity"]
        price = row["Unit Price"]
        disc = row["Discount"] if pd.notna(row["Discount"]) else 0.0
        expected_rev = round(qty * price * (1.0 - disc), 2)
        assert abs(row["Revenue"] - expected_rev) < 0.05, f"Math discrepancy at row {idx}: rev {row['Revenue']} vs {expected_rev}"

    # 5. Planted anomalies verification
    mean_rev = sales_df["Revenue"].mean()
    std_rev = sales_df["Revenue"].std()

    for anom in ground_truth["anomalies"]:
        order_id = anom["order_id"]
        matched_rows = sales_df[sales_df["Order ID"] == order_id]
        assert len(matched_rows) == 1, f"Anomaly {order_id} not found uniquely in sales.csv"
        row = matched_rows.iloc[0]
        col = anom["column"].title()  # e.g. 'Revenue', 'Quantity', 'Profit'
        val = row[col]
        # Statistical outlier check (> 3 std dev or z-score)
        series = sales_df[col].dropna()
        z_score = abs(val - series.mean()) / series.std()
        assert z_score > 2.5, f"Anomaly {order_id} on {col}={val} has insufficient z-score: {z_score:.2f}"

    print("ALL SAMPLE DATA CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify_datasets()
