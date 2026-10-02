import time
from pathlib import Path
from playwright.sync_api import sync_playwright

UPLOADS_DIR = Path("C:/AI-Data-Analyst/test_user_uploads")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stApp"]', timeout=15000)

    # Upload
    orders_csv = str(UPLOADS_DIR / "ecommerce_orders.csv")
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(orders_csv)
    page.wait_for_selector(".dataset-name-text", timeout=25000)
    time.sleep(2)
    print("Dataset uploaded.")

    # Check chat input
    chat_box = page.locator('textarea[data-testid="stChatInputTextArea"]')
    print("Chat box visible:", chat_box.is_visible())
    chat_box.click()
    chat_box.fill("How many rows are in the dataset?")
    time.sleep(1)

    # Click the send button or press enter
    send_btn = page.locator('[data-testid="stChatInputSubmitButton"]')
    print("Send button visible:", send_btn.is_visible())
    if send_btn.is_visible():
        send_btn.click()
        print("Clicked send button.")
    else:
        chat_box.press("Enter")
        print("Pressed Enter.")

    # Wait 10s and inspect
    time.sleep(10)
    page.screenshot(path="docs/screenshots/test_chat_progress.png")
    print("Body text snippet:\n", page.locator('[data-testid="stMain"]').inner_text()[:400])

    browser.close()
