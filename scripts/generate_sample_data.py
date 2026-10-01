"""Generator script for realistic sample datasets with planted anomalies and nulls."""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sample_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Customers Dataset (~500 rows)
first_names = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle"
]
last_names = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker"
]
regions = ["North", "South", "East", "West", "Central"]
tiers = ["Bronze", "Silver", "Gold", "Platinum"]

customers = []
num_customers = 500
start_signup = datetime(2021, 1, 1)

for cid in range(1, num_customers + 1):
    c_id = f"CUST-{cid:04d}"
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    email = f"{fname.lower()}.{lname.lower()}{cid}@example.com"
    region = random.choice(regions)
    tier = random.choices(tiers, weights=[0.45, 0.30, 0.18, 0.07])[0]
    signup_days = random.randint(0, 1000)
    signup_date = (start_signup + timedelta(days=signup_days)).strftime("%Y-%m-%d")
    credit_score = int(np.clip(np.random.normal(680, 75), 450, 850))

    # A few null regions/credit scores
    if cid in [12, 85, 230]:
        region = None
    if cid in [45, 160]:
        credit_score = None

    customers.append({
        "Customer ID": c_id,
        "Customer Name": f"{fname} {lname}",
        "Email": email,
        "Region": region,
        "Tier": tier,
        "Signup Date": signup_date,
        "Credit Score": credit_score,
    })

customers_df = pd.DataFrame(customers)
customers_df.to_csv(OUTPUT_DIR / "customers.csv", index=False)
print(f"Generated {len(customers_df)} customers in customers.csv")

# 2. Products Dataset (~250-500 products)
categories = {
    "Electronics": ["Pro Laptop 15", "Wireless Headphones", "Ultra HD Monitor 27", "Mechanical Keyboard", "Ergonomic Mouse", "Smart Watch v3", "Noise-Cancelling Earbuds", "USB-C Docking Hub"],
    "Office Supplies": ["Executive Standing Desk", "Mesh Ergonomic Chair", "Gel Pen Pack (12x)", "Heavy-duty Stapler", "Recycled Copy Paper (A4)", "Notebook Leather Journal", "Desk Organizer Wire"],
    "Software": ["Cloud Analytics Suite", "Security Antivirus Pro", "CRM Starter License", "DevOps Pipeline Tool", "Team Chat Enterprise"],
    "Furniture": ["Conference Table Wood", "Filing Cabinet Metal", "Bookshelf Modern", "Lounge Chair Fabric", "Whiteboard 6x4ft"]
}

products = []
pid_counter = 1
for cat, items in categories.items():
    for item in items:
        # Create 10 variations per item to reach ~300 products
        for var_idx in range(1, 11):
            prod_id = f"PROD-{pid_counter:04d}"
            name = f"{item} (Model {var_idx})"
            base_price = {
                "Electronics": random.uniform(80.0, 1500.0),
                "Office Supplies": random.uniform(10.0, 250.0),
                "Software": random.uniform(50.0, 800.0),
                "Furniture": random.uniform(120.0, 1800.0),
            }[cat]
            price = round(base_price, 2)
            cost = round(price * random.uniform(0.40, 0.75), 2)
            stock = random.randint(10, 500)

            # Plant deliberate nulls
            if pid_counter in [15, 62]:
                cost = None

            products.append({
                "Product ID": prod_id,
                "Product Name": name,
                "Category": cat,
                "Unit Price": price,
                "Unit Cost": cost,
                "Stock Quantity": stock,
            })
            pid_counter += 1

products_df = pd.DataFrame(products)
products_df.to_csv(OUTPUT_DIR / "products.csv", index=False)
print(f"Generated {len(products_df)} products in products.csv")

# 3. Sales Dataset (~1000 rows) with deliberate planted anomalies
sales = []
num_sales = 1000
start_date = datetime(2023, 1, 1)

# Pick specific known IDs for anomalies
planted_anomalies = []

for order_id in range(1, num_sales + 1):
    tx_id = f"ORD-{order_id:05d}"
    cust = random.choice(customers)
    prod = random.choice(products)
    
    order_days = random.randint(0, 720) # 2023 to end of 2024
    order_date = (start_date + timedelta(days=order_days)).strftime("%Y-%m-%d")
    
    # Standard quantity distribution (1 to 8)
    quantity = random.choices([1, 2, 3, 4, 5, 6, 8], weights=[0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02])[0]
    unit_price = prod["Unit Price"]
    unit_cost = prod["Unit Cost"] or (unit_price * 0.6)
    
    discount = random.choices([0.0, 0.05, 0.10, 0.15, 0.20], weights=[0.6, 0.2, 0.1, 0.07, 0.03])[0]
    revenue = round(quantity * unit_price * (1.0 - discount), 2)
    profit = round(revenue - (quantity * unit_cost), 2)
    channel = random.choices(["Online", "Retail Store", "Direct Sales", "Partner"], weights=[0.45, 0.25, 0.20, 0.10])[0]

    # Plant deliberate anomalies
    if order_id == 142:
        # Massive quantity / revenue spike anomaly
        quantity = 500
        revenue = round(quantity * unit_price, 2)
        profit = round(revenue * 0.45, 2)
        planted_anomalies.append({
            "order_id": tx_id,
            "row_index": order_id - 1,
            "type": "extreme_high_revenue_and_quantity",
            "column": "revenue",
            "value": revenue,
            "reason": f"Extreme bulk purchase: quantity={quantity}, revenue=${revenue:,.2f} is far above normal range"
        })
    elif order_id == 389:
        # Extreme negative profit anomaly (pricing/discount glitch)
        discount = 0.90
        revenue = round(quantity * unit_price * 0.10, 2)
        profit = -25000.00
        planted_anomalies.append({
            "order_id": tx_id,
            "row_index": order_id - 1,
            "type": "extreme_negative_profit",
            "column": "profit",
            "value": profit,
            "reason": f"Severely abnormal loss of -${abs(profit):,.2f} due to 90% discount pricing error"
        })
    elif order_id == 615:
        # Extreme revenue outlier on standard item
        revenue = 98500.00
        profit = 45000.00
        planted_anomalies.append({
            "order_id": tx_id,
            "row_index": order_id - 1,
            "type": "extreme_single_transaction_revenue",
            "column": "revenue",
            "value": revenue,
            "reason": f"Unusually large single transaction revenue of ${revenue:,.2f}"
        })
    elif order_id == 804:
        # Quantity anomaly with normal unit price
        quantity = 650
        revenue = round(quantity * unit_price * 0.8, 2)
        profit = round(revenue * 0.35, 2)
        planted_anomalies.append({
            "order_id": tx_id,
            "row_index": order_id - 1,
            "type": "extreme_quantity_spike",
            "column": "quantity",
            "value": quantity,
            "reason": f"Unusually massive volume quantity of {quantity} units"
        })

    # Plant a few nulls in optional columns
    if order_id in [50, 210, 780]:
        channel = None
    if order_id in [105, 540]:
        discount = None

    sales.append({
        "Order ID": tx_id,
        "Customer ID": cust["Customer ID"],
        "Product ID": prod["Product ID"],
        "Order Date": order_date,
        "Quantity": quantity,
        "Unit Price": unit_price,
        "Discount": discount,
        "Revenue": revenue,
        "Profit": profit,
        "Channel": channel,
    })

sales_df = pd.DataFrame(sales)
sales_df.to_csv(OUTPUT_DIR / "sales.csv", index=False)
print(f"Generated {len(sales_df)} orders in sales.csv")

# Save ground truth anomalies
with open(OUTPUT_DIR / "anomalies_ground_truth.json", "w", encoding="utf-8") as f:
    json.dump({
        "dataset": "sales.csv",
        "description": "Planted deliberate statistical and behavioral anomalies in sales dataset",
        "anomalies": planted_anomalies
    }, f, indent=2)

print("Saved anomalies ground truth in anomalies_ground_truth.json")
