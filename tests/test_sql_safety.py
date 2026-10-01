"""Unit tests for SQL AST validation, injection prevention, auto-limits, and DuckDB security."""

import pandas as pd
import pytest
from app.tools.sql_tool import (
    DuckDBManager,
    QueryResult,
    SQLExecutionError,
    SQLSecurityError,
    validate_sql_security,
)

@pytest.fixture
def db_manager():
    mgr = DuckDBManager()
    sales_df = pd.DataFrame({
        "order_id": [f"ORD-{i}" for i in range(1, 101)],
        "customer_id": [f"CUST-{i % 10}" for i in range(1, 101)],
        "revenue": [float(i * 10) for i in range(1, 101)],
    })
    customers_df = pd.DataFrame({
        "customer_id": [f"CUST-{i}" for i in range(10)],
        "region": ["North", "South", "East", "West", "Central"] * 2,
    })
    mgr.register_dataframe("sales", sales_df)
    mgr.register_dataframe("customers", customers_df)
    return mgr

def test_valid_select_query(db_manager):
    res = db_manager.execute_query("SELECT order_id, revenue FROM sales WHERE revenue > 900")
    assert isinstance(res, QueryResult)
    assert len(res.df) == 10
    assert "LIMIT" in res.sql
    assert res.total_rows == 10

def test_valid_with_cte_query(db_manager):
    query = """
    WITH high_sales AS (
        SELECT customer_id, SUM(revenue) as total_rev
        FROM sales
        GROUP BY customer_id
    )
    SELECT customer_id, total_rev FROM high_sales ORDER BY total_rev DESC
    """
    res = db_manager.execute_query(query)
    assert len(res.df) == 10
    assert "total_rev" in res.df.columns

def test_multi_table_join(db_manager):
    query = """
    SELECT s.order_id, s.revenue, c.region
    FROM sales s
    JOIN customers c ON s.customer_id = c.customer_id
    ORDER BY s.revenue DESC
    """
    res = db_manager.execute_query(query)
    assert len(res.df) == 50
    assert "region" in res.df.columns
    assert res.total_rows == 100
    assert res.truncated is True  # Default max_preview_rows is 50
    assert len(res.llm_preview_df) == 15
    assert len(res.chart_df) == 100

def test_replacement_scan_blocked():
    with pytest.raises(SQLSecurityError, match="Forbidden file replacement scan"):
        validate_sql_security("SELECT * FROM 'sample_data/sales.csv'")

    with pytest.raises(SQLSecurityError, match="Forbidden file replacement scan"):
        validate_sql_security('SELECT * FROM "sample_data/sales.csv"')

def test_file_functions_blocked():
    forbidden_queries = [
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_csv_auto('sales.csv')",
        "SELECT * FROM read_text('/etc/passwd')",
        "SELECT * FROM read_blob('key.bin')",
        "SELECT * FROM parquet_scan('data.parquet')",
        "SELECT * FROM sniff_csv('data.csv')",
    ]
    for q in forbidden_queries:
        with pytest.raises(SQLSecurityError):
            validate_sql_security(q)

def test_quoted_identifier_trick():
    with pytest.raises(SQLSecurityError):
        validate_sql_security('SELECT * FROM "read_csv"(\'/etc/passwd\')')

def test_subquery_forbidden_function():
    subquery = "SELECT * FROM sales WHERE order_id IN (SELECT read_text('/etc/passwd'))"
    with pytest.raises(SQLSecurityError):
        validate_sql_security(subquery)

def test_ast_function_allowlist():
    # Allowed functions pass
    assert validate_sql_security("SELECT ROUND(AVG(revenue), 2), COUNT(*) FROM sales")
    assert validate_sql_security("SELECT UPPER(region), COALESCE(region, 'Unknown') FROM customers")

    # Unapproved function fails
    with pytest.raises(SQLSecurityError, match="Forbidden or unapproved SQL function"):
        validate_sql_security("SELECT current_setting('threads')")

    with pytest.raises(SQLSecurityError, match="Forbidden or unapproved SQL function"):
        validate_sql_security("SELECT getenv('GROQ_API_KEY')")

def test_block_modifying_statements():
    with pytest.raises(SQLSecurityError):
        validate_sql_security("DROP TABLE sales")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("DELETE FROM sales")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("UPDATE sales SET revenue = 0")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("INSERT INTO sales VALUES ('1', '2', 3)")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("ATTACH 'db.db' AS db")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("COPY sales TO 'out.csv'")
    with pytest.raises(SQLSecurityError):
        validate_sql_security("PRAGMA table_info('sales')")

def test_multi_statement_and_comments():
    with pytest.raises(SQLSecurityError, match="Multiple statements"):
        validate_sql_security("SELECT * FROM sales; DROP TABLE sales;")
    with pytest.raises(SQLSecurityError, match="Multiple statements"):
        validate_sql_security("SELECT * FROM sales; -- DROP TABLE sales")

def test_timeout_and_connection_recovery(db_manager):
    # Heavy cross-join query that takes several seconds
    heavy_query = """
    SELECT COUNT(*) FROM sales s1, sales s2, sales s3, sales s4, sales s5, sales s6
    """
    # Test timeout with 0.5s limit
    with pytest.raises(SQLExecutionError, match="timed out"):
        db_manager.execute_query(heavy_query, timeout_seconds=0.5)

    # Verify connection remains completely usable after timeout interrupt
    recovery_res = db_manager.execute_query("SELECT 1 AS alive")
    assert recovery_res.df.iloc[0]["alive"] == 1
