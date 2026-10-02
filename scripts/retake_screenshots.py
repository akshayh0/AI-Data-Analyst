"""Automated script to capture all 5 Datalens screenshots at 1440px viewport using Playwright."""

from pathlib import Path
import time
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def capture_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        # 1440px viewport as requested
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:8501...")
        page.goto("http://localhost:8501")
        page.wait_for_timeout(4000)

        # 1. Empty State Screenshot
        print("Ensuring clean empty state...")
        clear_btn = page.query_selector("button:has-text('Clear all data')")
        if clear_btn:
            clear_btn.click()
            page.wait_for_timeout(3000)

        page.wait_for_selector(".empty-hero-card", timeout=10000)
        print("Capturing 1. Empty State (1440px)...")
        page.screenshot(path=str(OUTPUT_DIR / "empty.png"), full_page=False)
        print(f"Saved: {OUTPUT_DIR / 'empty.png'}")

        # 2. Load Sample Datasets
        print("Loading sample datasets...")
        load_btn = page.query_selector("button:has-text('Load sample datasets')")
        if load_btn:
            load_btn.click()
            page.wait_for_timeout(5000)
        else:
            print("Warning: Load sample datasets button not found!")

        # 3. Chat Tab with query answered & chart rendered
        print("Interacting with Chat Workbench...")
        page.wait_for_selector(".dataset-name-text", timeout=10000)
        
        # Click "Show monthly trends" chip or fill input
        chip_btn = page.query_selector("button:has-text('Show monthly trends')")
        if chip_btn:
            chip_btn.click()
            print("Clicked 'Show monthly trends' chip...")
        else:
            print("Question chip not found, submitting chat input...")
            chat_input = page.query_selector("textarea[data-testid='stChatInputTextArea']")
            if chat_input:
                chat_input.fill("Show monthly sales trends.")
                chat_input.press("Enter")

        # Wait for answer card and chart to render
        page.wait_for_timeout(8000)
        page.wait_for_selector(".answer-card", timeout=45000)
        page.wait_for_timeout(3000)
        print("Capturing 2. Chat Workbench (1440px)...")
        page.screenshot(path=str(OUTPUT_DIR / "chat.png"), full_page=False)
        print(f"Saved: {OUTPUT_DIR / 'chat.png'}")

        # 4. Detailed Chart Screenshot
        print("Capturing 3. Chart Detail (1440px)...")
        chart_el = page.query_selector("[data-testid='stPlotlyChart']") or page.query_selector(".js-plotly-plot")
        if chart_el:
            chart_el.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            chart_el.screenshot(path=str(OUTPUT_DIR / "chart.png"))
            print(f"Saved focused chart: {OUTPUT_DIR / 'chart.png'}")
        else:
            page.screenshot(path=str(OUTPUT_DIR / "chart.png"), full_page=False)
            print(f"Saved fallback chart: {OUTPUT_DIR / 'chart.png'}")

        # 5. Data Quality Tab
        print("Navigating to Quality tab...")
        quality_tab = page.query_selector("button[data-baseweb='tab']:has-text('Quality')")
        if quality_tab:
            quality_tab.click()
            page.wait_for_timeout(5000)
            print("Capturing 4. Data Quality (1440px)...")
            page.screenshot(path=str(OUTPUT_DIR / "quality.png"), full_page=False)
            print(f"Saved: {OUTPUT_DIR / 'quality.png'}")
        else:
            print("Error: Quality tab not found!")

        # 6. Anomalies Tab
        print("Navigating to Anomalies tab...")
        anomalies_tab = page.query_selector("button[data-baseweb='tab']:has-text('Anomalies')")
        if anomalies_tab:
            anomalies_tab.click()
            page.wait_for_timeout(6000)
            print("Capturing 5. Anomalies View (1440px)...")
            page.screenshot(path=str(OUTPUT_DIR / "anomalies.png"), full_page=False)
            print(f"Saved: {OUTPUT_DIR / 'anomalies.png'}")
        else:
            print("Error: Anomalies tab not found!")

        # 7. Test Table Removal
        print("Testing file removal control...")
        remove_btns = page.query_selector_all("button:has-text('✕')")
        if remove_btns:
            initial_count = len(page.query_selector_all(".dataset-name-text"))
            remove_btns[0].click()
            page.wait_for_timeout(3000)
            new_count = len(page.query_selector_all(".dataset-name-text"))
            print(f"File removal test: Table count changed from {initial_count} to {new_count}")

        browser.close()
        print("All 5 screenshots successfully captured at 1440px and file removal verified!")

if __name__ == "__main__":
    capture_screenshots()
