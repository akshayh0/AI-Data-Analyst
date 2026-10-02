"""End-to-end integration test verifying Streamlit app, Dashboard tab, KPIs, charts, and existing tabs."""

import io
import pandas as pd
from streamlit.testing.v1 import AppTest

from app.data.loader import load_csv_file


def test_app_dashboard_with_uploaded_csv():
    """Verify that uploading a dynamic CSV properly displays in Dashboard tab with KPIs and charts."""
    # 1. Create a dynamic CSV with custom un-hardcoded column names
    csv_data = io.StringIO(
        "transaction_code,recorded_at,vendor_category,unit_price,quantity_ordered\n"
        "TX101,2024-03-01,Electronics,299.99,2\n"
        "TX102,2024-03-02,Supplies,45.50,10\n"
        "TX103,2024-03-03,Electronics,120.00,4\n"
        "TX104,2024-03-04,Furniture,780.00,1\n"
        "TX105,2024-03-05,Supplies,30.00,15\n"
        "TX106,2024-03-06,Electronics,650.00,3\n"
        "TX107,2024-03-07,Furniture,420.00,2\n"
        "TX108,2024-03-08,Supplies,18.50,25\n"
    )

    # 2. Initialize AppTest from app/main.py
    at = AppTest.from_file("app/main.py", default_timeout=30)
    at.run()
    assert not at.exception, f"App initialization threw exception: {at.exception}"

    # Verify tabs exist
    tab_labels = [t.label for t in at.tabs]
    assert tab_labels == ["Chat", "Data", "Quality", "Anomalies", "Dashboard"], f"Unexpected tabs: {tab_labels}"

    # 3. Simulate CSV loading into session state directly as the loader does
    df, profile, table_name, mapping = load_csv_file(
        io.BytesIO(csv_data.getvalue().encode("utf-8")),
        filename="custom_vendor_data.csv",
    )
    at.session_state.db_manager.register_dataframe(table_name, df)
    at.session_state.table_profiles[table_name] = profile
    at.session_state.dataframes[table_name] = df

    # 4. Run app with loaded dataset
    at.run()
    assert not at.exception, f"App run with loaded dataset failed: {at.exception}"

    # Verify Markdown elements contain Dashboard info
    markdown_texts = [m.value for m in at.markdown]
    combined_md = "\n".join(markdown_texts)

    # Description requirement:
    assert "Automatically generated insights from your uploaded dataset." in combined_md
    assert "Analytics Dashboard" in combined_md
    assert "TOTAL RECORDS" in combined_md.upper()
    assert "UNIQUE" in combined_md.upper()

    # Verify buttons
    button_labels = [b.label for b in at.button]
    assert "Refresh Dashboard" in button_labels

    # 5. Verify Plotly charts rendered in the app
    plotly_charts = at.get("plotly_chart")
    assert len(plotly_charts) >= 3, f"Expected at least 3 charts, found {len(plotly_charts)}"

    # 6. Verify existing tabs still function:
    # Data tab dataframes
    dataframes = at.dataframe
    assert len(dataframes) >= 2, f"Expected data preview dataframes in Data tab, found {len(dataframes)}"

    print(f"Verified {len(tab_labels)} tabs: {tab_labels}")
    print(f"Verified {len(plotly_charts)} Plotly charts rendered on Dashboard.")
    print("All checks passed successfully!")


if __name__ == "__main__":
    test_app_dashboard_with_uploaded_csv()
