import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stApp"]', timeout=15000)

    # Scroll down to the Plotly chart
    chart_elem = page.locator('svg.main-svg, [data-testid="stPlotlyChart"], .js-plotly-plot').first
    if chart_elem.count() > 0:
        chart_elem.scroll_into_view_if_needed()
        time.sleep(2)
        page.screenshot(path="docs/screenshots/chart.png")
        print("Updated chart.png with chart scrolled into view.")
    else:
        print("No chart element found.")
    browser.close()
