from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('http://localhost:8501')
    page.wait_for_selector('[data-testid="stApp"]', timeout=20000)
    time.sleep(3)
    print('Title:', page.title())
    print('Text snippet:\n', page.inner_text('body')[:400])
    page.screenshot(path='docs/screenshots/debug_page.png')
    browser.close()
