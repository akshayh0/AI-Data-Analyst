import time
from pathlib import Path
from playwright.sync_api import sync_playwright

UPLOADS_DIR = Path("C:/AI-Data-Analyst/test_user_uploads")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stApp"]', timeout=15000)

    orders_csv = str(UPLOADS_DIR / "ecommerce_orders.csv")

    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(orders_csv)
    print("Uploaded single file...")
    time.sleep(5)
    page.screenshot(path="docs/screenshots/after_upload.png")
    print("Page text:\n", page.locator('[data-testid="stSidebar"]').inner_text())
    browser.close()
