import os
import csv

OUT_DIR = "c:/AI-Data-Analyst/test_user_uploads"
os.makedirs(OUT_DIR, exist_ok=True)

# 1. ecommerce_orders.csv (25 realistic transactions)
orders_data = [
    ["order_id", "customer_region", "product_category", "order_value", "quantity", "discount_pct", "return_status"],
    ["ORD-1001", "North America", "Electronics", 1250.00, 2, 0.05, "Kept"],
    ["ORD-1002", "Europe", "Furniture", 850.50, 1, 0.10, "Kept"],
    ["ORD-1003", "Asia Pacific", "Office Supplies", 120.00, 5, 0.00, "Kept"],
    ["ORD-1004", "North America", "Clothing", 230.25, 3, 0.15, "Returned"],
    ["ORD-1005", "Europe", "Electronics", 3100.00, 4, 0.08, "Kept"],
    ["ORD-1006", "Latin America", "Furniture", 450.00, 1, 0.00, "Kept"],
    ["ORD-1007", "Asia Pacific", "Electronics", 2100.50, 3, 0.05, "Kept"],
    ["ORD-1008", "North America", "Books", 85.00, 4, 0.00, "Kept"],
    ["ORD-1009", "Europe", "Office Supplies", 310.00, 8, 0.20, "Kept"],
    ["ORD-1010", "North America", "Furniture", 1450.00, 2, 0.12, "Returned"],
    ["ORD-1011", "Asia Pacific", "Clothing", 195.00, 2, 0.05, "Kept"],
    ["ORD-1012", "Europe", "Books", 65.50, 3, 0.00, "Kept"],
    ["ORD-1013", "North America", "Electronics", 4200.00, 5, 0.10, "Kept"],
    ["ORD-1014", "Latin America", "Office Supplies", 140.00, 4, 0.00, "Kept"],
    ["ORD-1015", "Asia Pacific", "Furniture", 920.00, 1, 0.05, "Kept"],
    ["ORD-1016", "North America", "Clothing", 410.00, 6, 0.20, "Kept"],
    ["ORD-1017", "Europe", "Electronics", 1850.00, 2, 0.00, "Kept"],
    ["ORD-1018", "Asia Pacific", "Books", 110.00, 5, 0.10, "Kept"],
    ["ORD-1019", "North America", "Furniture", 2200.00, 3, 0.15, "Kept"],
    ["ORD-1020", "Europe", "Clothing", 320.00, 4, 0.05, "Returned"],
    ["ORD-1021", "Latin America", "Electronics", 1600.00, 2, 0.05, "Kept"],
    ["ORD-1022", "North America", "Office Supplies", 95.00, 3, 0.00, "Kept"],
    ["ORD-1023", "Asia Pacific", "Furniture", 1150.00, 2, 0.10, "Kept"],
    ["ORD-1024", "Europe", "Electronics", 2750.00, 3, 0.08, "Kept"],
    ["ORD-1025", "North America", "Books", 145.00, 6, 0.15, "Kept"],
]

with open(f"{OUT_DIR}/ecommerce_orders.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(orders_data)

# 2. vendor_inventory.csv (15 realistic warehouse items)
inventory_data = [
    ["item_sku", "vendor_name", "product_category", "stock_on_hand", "reorder_level", "unit_cost"],
    ["SKU-E101", "Apex Tech", "Electronics", 45, 15, 320.00],
    ["SKU-E102", "Apex Tech", "Electronics", 12, 20, 680.00],
    ["SKU-E103", "Silicon Global", "Electronics", 80, 25, 110.00],
    ["SKU-F201", "Nordic Woods", "Furniture", 18, 10, 290.00],
    ["SKU-F202", "Nordic Woods", "Furniture", 5, 8, 540.00],
    ["SKU-F203", "Comfort Living", "Furniture", 30, 15, 175.00],
    ["SKU-O301", "PaperCraft Co", "Office Supplies", 250, 50, 12.50],
    ["SKU-O302", "PaperCraft Co", "Office Supplies", 140, 40, 28.00],
    ["SKU-C401", "Urban Trend", "Clothing", 95, 30, 35.00],
    ["SKU-C402", "Urban Trend", "Clothing", 22, 25, 65.00],
    ["SKU-B501", "Lexicon Press", "Books", 180, 40, 14.00],
    ["SKU-B502", "Lexicon Press", "Books", 65, 20, 22.00],
    ["SKU-E104", "Silicon Global", "Electronics", 8, 15, 950.00],
    ["SKU-O303", "Metro Supply", "Office Supplies", 310, 60, 8.50],
    ["SKU-C403", "Pure Cotton", "Clothing", 115, 35, 42.00],
]

with open(f"{OUT_DIR}/vendor_inventory.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(inventory_data)

# 3. Duplicate test file
with open(f"{OUT_DIR}/duplicate_test.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows([["id", "val"], ["1", "alpha"], ["2", "beta"]])

with open(f"{OUT_DIR}/DUPLICATE_TEST.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows([["id", "val"], ["3", "gamma"], ["4", "delta"]])

# 4. Invalid file format
with open(f"{OUT_DIR}/corrupted_binary.bin", "wb") as f:
    f.write(b"\x00\xff\xfe\x00\x12\x34\x56\x78\x00\x00\x01\x02\x03\x04")

print("Created test files successfully.")
