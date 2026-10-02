import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

UPLOADS_DIR = Path("C:/AI-Data-Analyst/test_user_uploads")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stApp"]', timeout=15000)
    print("App loaded.")

    orders_csv = str(UPLOADS_DIR / "ecommerce_orders.csv")
    inventory_csv = str(UPLOADS_DIR / "vendor_inventory.csv")

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files([orders_csv, inventory_csv])
    print("Files submitted to file input.")

    # Wait for tables to appear in sidebar
    page.wait_for_selector('.loaded-table-card', timeout=25000)
    time.sleep(2)
    sidebar_text = page.locator('[data-testid="stSidebar"]').inner_text()
    print("Sidebar text after upload:\n", sidebar_text)

    browser.close()
