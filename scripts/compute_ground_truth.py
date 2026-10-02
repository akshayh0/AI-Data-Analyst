"""Direct computation script for the 6 assignment questions against sample_data."""

from pathlib import Path
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import duckdb
import pandas as pd
from app.data.loader import load_csv_file
from app.tools.anomaly_tool import detect_anomalies_pipeline
from app.tools.sql_tool import DuckDBManager

db = DuckDBManager()

# Ingest sample data using the app loader (handles column cleaning)
data_dir = BASE_DIR / "sample_data"
for fname in ["customers.csv", "products.csv", "sales.csv"]:
    df, prof, tname, mapping = load_csv_file(data_dir / fname)
    db.register_dataframe(tname, df)

con = db._con

print("=" * 70)
print("GROUND TRUTH COMPUTATION FOR 6 QUESTIONS")
print("=" * 70)

# Question 1: Which region generated the highest revenue?
print("\n[Q1] Which region generated the highest revenue?")
q1_df = con.execute("""
    SELECT c.region, ROUND(SUM(s.revenue), 2) as total_revenue, COUNT(*) as order_count
    FROM sales s
    JOIN customers c ON s.customer_id = c.customer_id
    GROUP BY c.region
    ORDER BY total_revenue DESC
""").df()
print(q1_df)

# Question 2: Show monthly sales trends
print("\n[Q2] Show monthly sales trends")
q2_df = con.execute("""
    SELECT strftime(TRY_CAST(order_date AS DATE), '%Y-%m') as sales_month, ROUND(SUM(revenue), 2) as total_revenue, COUNT(*) as order_count
    FROM sales
    GROUP BY sales_month
    ORDER BY sales_month
""").df()
print(q2_df)

# Question 3: Which products are underperforming?
print("\n[Q3] Which products are underperforming? (lowest 5 by revenue)")
q3_df = con.execute("""
    SELECT p.product_id, p.product_name, p.category, ROUND(COALESCE(SUM(s.revenue), 0), 2) as total_revenue, COALESCE(SUM(s.quantity), 0) as units_sold
    FROM products p
    LEFT JOIN sales s ON p.product_id = s.product_id
    GROUP BY p.product_id, p.product_name, p.category
    ORDER BY total_revenue ASC
    LIMIT 5
""").df()
print(q3_df)

# Question 4: What are the top five customers?
print("\n[Q4] What are the top five customers? (by total spend)")
q4_df = con.execute("""
    SELECT c.customer_id, c.customer_name, c.region, ROUND(SUM(s.revenue), 2) as total_spend
    FROM sales s
    JOIN customers c ON s.customer_id = c.customer_id
    GROUP BY c.customer_id, c.customer_name, c.region
    ORDER BY total_spend DESC
    LIMIT 5
""").df()
print(q4_df)

# Question 5: Generate SQL for this analysis
print("\n[Q5] Generate SQL for this analysis")
print("SQL to generate customer revenue by region and profit margins:")
q5_sql = """
SELECT 
    c.region,
    COUNT(DISTINCT s.order_id) as total_orders,
    ROUND(SUM(s.revenue), 2) as total_revenue,
    ROUND(SUM(s.profit), 2) as total_profit,
    ROUND(SUM(s.profit) / NULLIF(SUM(s.revenue), 0) * 100, 2) as profit_margin_pct
FROM sales s
JOIN customers c ON s.customer_id = c.customer_id
GROUP BY c.region
ORDER BY total_revenue DESC;
"""
print(con.execute(q5_sql).df())

# Question 6: Detect anomalies in the dataset
print("\n[Q6] Detect anomalies in the dataset")
sales_df = db.get_dataframe("sales")
flagged_sales, summary_sales = detect_anomalies_pipeline(sales_df, random_state=42)
print(f"Total flagged sales rows: {len(flagged_sales)}")
high_conf = flagged_sales[flagged_sales["anomaly_confidence"] == "high"]
print(f"High confidence anomalies: {len(high_conf)}")
print("Sample high confidence anomalies:")
print(high_conf[["order_id", "revenue", "profit", "discount", "quantity", "anomaly_methods"]].head())
