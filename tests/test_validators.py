"""Unit tests for file validation, encoding detection, column sanitization, and fixture loading."""

from pathlib import Path
import pytest
import pandas as pd
from app.data.loader import load_csv_file
from app.data.validators import (
    ValidationError,
    clean_column_names,
    detect_delimiter,
    detect_encoding,
    sanitize_column_name,
    sanitize_table_name,
    validate_file_metadata,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def test_detect_encoding_utf8():
    raw = "header1,header2\nvalue1,value2".encode("utf-8")
    assert "utf-8" in detect_encoding(raw).lower()

def test_detect_encoding_latin1():
    raw = b"id,name\n1,Caf\xe9"
    detected = detect_encoding(raw)
    assert detected.lower() in ["latin-1", "iso-8859-1", "windows-1252", "cp1252"]

def test_detect_delimiter():
    assert detect_delimiter("a,b,c\n1,2,3") == ","
    assert detect_delimiter("a;b;c\n1;2;3") == ";"
    assert detect_delimiter("a\tb\tc\n1\t2\t3") == "\t"
    assert detect_delimiter("a|b|c\n1|2|3") == "|"

def test_sanitize_column_name():
    assert sanitize_column_name("Customer ID", 0) == "customer_id"
    assert sanitize_column_name("Sales ($)", 1) == "sales_usd"
    assert sanitize_column_name("Profit %", 2) == "profit_pct"
    assert sanitize_column_name("2024_Revenue", 3) == "col_2024_revenue"
    assert sanitize_column_name("", 4) == "col_5"
    assert sanitize_column_name("   ", 5) == "col_6"
    assert sanitize_column_name(None, 6) == "col_7"
    # Reserved SQL keywords
    assert sanitize_column_name("SELECT", 7) == "select_col"
    assert sanitize_column_name("ORDER", 8) == "order_col"

def test_clean_column_names_case_duplicates():
    # Tests Sales, sales, SALES
    raw_cols = ["Sales", "sales", "SALES"]
    cleaned, mapping = clean_column_names(raw_cols)

    assert cleaned == ["sales", "sales_1", "sales_2"]
    assert mapping["Sales"] == "sales"
    assert mapping["sales"] == "sales_1"
    assert mapping["SALES"] == "sales_2"
    assert len(cleaned) == len(set(cleaned))

def test_validate_file_metadata():
    # Valid file
    validate_file_metadata("sales.csv", 1024, max_size_mb=10)

    # Invalid extension
    with pytest.raises(ValidationError, match="not a CSV file"):
        validate_file_metadata("sales.xlsx", 1024)

    # Empty file
    with pytest.raises(ValidationError, match="is empty"):
        validate_file_metadata("empty.csv", 0)

    # File too large
    with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
        validate_file_metadata("large.csv", 20 * 1024 * 1024, max_size_mb=10)

def test_sanitize_table_name():
    assert sanitize_table_name("sales_data.csv") == "sales_data"
    assert sanitize_table_name("2024 Customer Report (v2).csv") == "t_2024_customer_report_v2"
    assert sanitize_table_name("!@#.csv") == "uploaded_table"
    # Reserved SQL keyword filenames
    assert sanitize_table_name("select.csv") == "select_table"
    assert sanitize_table_name("table.csv") == "table_table"
    assert sanitize_table_name("order.csv") == "order_table"

def test_fixture_utf8_bom():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "utf8_bom.csv")
    assert table_name == "utf8_bom"
    assert "product" in df.columns
    assert "price" in df.columns
    assert len(df) == 2

def test_fixture_semicolon_delimited():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "semicolon.csv")
    assert table_name == "semicolon"
    assert list(df.columns) == ["name", "department", "salary"]
    assert len(df) == 2

def test_fixture_latin1_encoding():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "latin1.csv")
    assert table_name == "latin1"
    assert len(df) == 1
    assert "Montréal" in str(df.iloc[0]["city"])

def test_fixture_header_only_csv():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "header_only.csv")
    assert table_name == "header_only"
    assert list(df.columns) == ["id", "customer_name", "email"]
    assert len(df) == 0
    assert profile.row_count == 0

def test_fixture_malformed_csv_skips_bad_line():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "malformed.csv")
    assert table_name == "malformed"
    # Row with extra columns is skipped gracefully via on_bad_lines='skip'
    assert len(df) == 2
    assert list(df.columns) == ["col1", "col2", "col3"]

def test_fixture_case_duplicates_file():
    df, profile, table_name, mapping = load_csv_file(FIXTURES_DIR / "case_duplicates.csv")
    assert list(df.columns) == ["sales", "sales_1", "sales_2"]
    assert len(df) == 2
