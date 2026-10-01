"""DuckDB SQL execution engine with strict AST function allowlists and locked security configuration."""

from dataclasses import dataclass
import re
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Set
import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger()

class SQLSecurityError(Exception):
    """Raised when an SQL query violates security policies."""
    pass

class SQLExecutionError(Exception):
    """Raised when SQL execution fails."""
    pass

@dataclass
class QueryResult:
    """Structured container for SQL query execution output."""
    df: pd.DataFrame
    sql: str
    total_rows: int
    truncated: bool
    llm_preview_df: pd.DataFrame
    chart_df: pd.DataFrame
    execution_time_ms: float = 0.0

# Comprehensive Whitelist of allowed SQL functions (Aggregates, Math, Date/Time, String, Window, Conditionals)
ALLOWED_SQL_FUNCTIONS: Set[str] = {
    # Aggregates & Statistics
    "sum", "avg", "mean", "count", "min", "max", "stddev", "stddev_pop", "stddev_samp",
    "var_pop", "var_samp", "variance", "median", "mode", "quantile_cont", "quantile_disc",
    "approx_count_distinct", "string_agg", "group_concat", "array_agg", "list", "first",
    "last", "any_value", "corr", "covar_pop", "covar_samp", "regr_slope", "regr_r2",
    # Math & Numeric
    "round", "floor", "ceil", "ceiling", "abs", "sign", "sqrt", "power", "pow", "exp",
    "ln", "log", "log10", "log2", "mod", "pi", "degrees", "radians", "cos", "sin", "tan",
    "acos", "asin", "atan", "greatest", "least", "random", "isnan", "isinf",
    # Date & Time
    "date_trunc", "date_part", "date_diff", "date_add", "date_sub", "strftime", "strptime",
    "current_date", "current_time", "current_timestamp", "now", "today", "extract", "epoch",
    "year", "month", "day", "hour", "minute", "second", "quarter", "dayofweek", "dayofyear",
    "week", "monthname", "dayname", "to_timestamp", "make_date", "age",
    # String
    "upper", "lower", "trim", "ltrim", "rtrim", "substr", "substring", "length", "len",
    "concat", "concat_ws", "replace", "regexp_replace", "regexp_extract", "regexp_matches",
    "left", "right", "lpad", "rpad", "reverse", "position", "instr", "split_part",
    "contains", "starts_with", "ends_with", "repeat", "ascii", "chr", "format",
    # Window functions
    "row_number", "rank", "dense_rank", "percent_rank", "cume_dist", "ntile", "lag",
    "lead", "first_value", "last_value", "nth_value",
    # Conditionals & Casting
    "coalesce", "nullif", "ifnull", "nvl", "cast", "try_cast", "typeof", "case", "when",
    "then", "else", "end",
}

# sqlglot typed nodes that are intrinsically safe and standard SQL operations
TYPED_SAFE_NODES = (
    exp.Cast,
    exp.TryCast,
    exp.Case,
    exp.If,
    exp.Coalesce,
    exp.Extract,
    exp.Substring,
    exp.Length,
    exp.Round,
    exp.Floor,
    exp.Ceil,
    exp.Abs,
    exp.Sqrt,
    exp.Ln,
    exp.Exp,
    exp.Pow,
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
    exp.Distinct,
    exp.DateTrunc,
    exp.DateAdd,
    exp.DateDiff,
    exp.Window,
    exp.Corr,
    exp.Star,
    exp.Nullif,
    exp.CurrentDate,
    exp.CurrentTime,
    exp.CurrentTimestamp,
)

FORBIDDEN_AST_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Pragma,
    exp.Transaction,
    exp.Copy,
)

def validate_sql_security(sql: str, allowed_tables: Optional[Set[str]] = None) -> exp.Expression:
    """
    Parse and inspect an SQL query using sqlglot to enforce strict read-only execution.
    Only a single SELECT or WITH CTE statement is permitted.
    All DDL, DML, replacement scans, file access, internal system tables, and non-whitelisted functions are rejected.
    """
    clean_sql = sql.strip()
    if not clean_sql:
        raise SQLSecurityError("Empty SQL query provided.")

    if clean_sql.endswith(";"):
        clean_sql = clean_sql[:-1].strip()

    try:
        parsed_statements = sqlglot.parse(clean_sql, read="duckdb")
    except Exception as exc:
        raise SQLSecurityError(f"Failed to parse SQL query: {str(exc)}") from exc

    if not parsed_statements:
        raise SQLSecurityError("No valid SQL statement detected.")

    if len(parsed_statements) > 1:
        raise SQLSecurityError("Multiple statements are not permitted. Only single SELECT/WITH queries are allowed.")

    stmt = parsed_statements[0]
    if stmt is None:
        raise SQLSecurityError("Invalid SQL statement syntax.")

    # Check root statement type: must be Select or Union
    if not isinstance(stmt, (exp.Select, exp.Union)):
        raise SQLSecurityError(
            f"Unauthorized statement type '{type(stmt).__name__}'. Only SELECT or WITH queries are permitted."
        )

    # Extract CTE aliases
    cte_names: Set[str] = set()
    with_node = stmt.args.get("with")
    if with_node:
        for cte in with_node.expressions:
            if cte.alias:
                cte_names.add(cte.alias.lower())

    # Inspect all child AST nodes (traversing subqueries, CTEs, expressions)
    for node in stmt.walk():
        # Block forbidden statement/command nodes
        if isinstance(node, FORBIDDEN_AST_NODES):
            raise SQLSecurityError(
                f"Forbidden SQL operation detected: '{type(node).__name__}'. Modifying or administrative queries are blocked."
            )

        # Block file-reading specific AST classes
        node_class_name = type(node).__name__.lower()
        if any(cls in node_class_name for cls in ["readcsv", "readparquet", "readjson", "glob", "scan"]):
            raise SQLSecurityError(
                f"Forbidden SQL file operation detected: '{type(node).__name__}'. External file access is disabled."
            )

        # Inspect table targets
        if isinstance(node, exp.Table):
            table_target = str(node.this) if node.this else ""
            table_clean = table_target.strip("`'\" ").lower()

            # Check database catalog name
            db_name = (node.db or "").strip("`'\" ").lower()
            if db_name in {"information_schema", "pg_catalog"} or table_clean.startswith("information_schema"):
                raise SQLSecurityError("Access to information_schema or system catalogs is forbidden.")

            if table_clean.startswith("duckdb_") or table_clean.startswith("pragma_"):
                raise SQLSecurityError(f"Access to internal function/table '{table_clean}' is forbidden.")

            # Detect file extensions or path separators in table name (replacement scan)
            if any(sep in table_target for sep in ["/", "\\", "."]) or table_clean.endswith(".csv") or table_clean.endswith(".parquet"):
                raise SQLSecurityError(
                    f"Forbidden file replacement scan detected: '{table_target}'. Direct file queries are not allowed."
                )

            # Detect file functions disguised as tables
            if any(table_clean.startswith(f) for f in [
                "read_csv", "read_csv_auto", "read_parquet", "parquet_scan", "read_json",
                "read_text", "read_blob", "sniff_csv", "glob"
            ]):
                raise SQLSecurityError(
                    f"Forbidden external file reference detected: '{table_clean}'."
                )

            # Check table against allowed registered tables + CTEs
            if allowed_tables is not None:
                valid_tables = {t.lower() for t in allowed_tables} | cte_names
                if table_clean and table_clean not in valid_tables:
                    raise SQLSecurityError(
                        f"Access to table '{table_clean}' is not permitted. Only uploaded datasets ({', '.join(sorted(allowed_tables))}) are accessible."
                    )

        # Inspect function calls (skip intrinsic typed safe nodes like Cast, Case, Coalesce, Star)
        if isinstance(node, (exp.Anonymous, exp.Func)) and not isinstance(node, TYPED_SAFE_NODES):
            func_name = (node.name or getattr(node, "key", "")).strip("`'\" ").lower()
            if not func_name or func_name == "*":
                continue

            # Check if function is in our allowlist
            if func_name not in ALLOWED_SQL_FUNCTIONS:
                raise SQLSecurityError(
                    f"Forbidden or unapproved SQL function detected: '{func_name}()'. Only standard analytical and aggregate functions are permitted."
                )

    # Secondary text check for semicolon injection tricks outside quotes
    unquoted = re.sub(r"'[^']*'", "", clean_sql)
    unquoted = re.sub(r'"[^"]*"', "", unquoted)
    if ";" in unquoted:
        raise SQLSecurityError("Multiple statements separated by ';' are not permitted.")

    return stmt

def apply_auto_limit(stmt: exp.Expression, max_rows: int) -> str:
    """
    Ensure the query has a LIMIT clause. If no LIMIT exists, append LIMIT max_rows.
    """
    has_limit = stmt.find(exp.Limit) is not None
    sql_str = stmt.sql(dialect="duckdb")

    if not has_limit:
        sql_str = f"{sql_str} LIMIT {max_rows}"

    return sql_str

class DuckDBManager:
    """Manages an in-memory DuckDB connection locked down against external access and bounded in memory/threads."""

    def __init__(self):
        # Configure DuckDB with external access disabled, configuration locked, memory and threads capped
        self._con = duckdb.connect(
            database=":memory:",
            config={
                "enable_external_access": "false",
                "lock_configuration": "true",
                "max_memory": "512MB",
                "threads": "2",
            }
        )
        self._registered_tables: Dict[str, pd.DataFrame] = {}

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    def register_dataframe(self, table_name: str, df: pd.DataFrame) -> None:
        """Register a pandas DataFrame as a queryable DuckDB view."""
        self._registered_tables[table_name] = df
        self._con.register(table_name, df)
        logger.info(f"Registered table '{table_name}' in DuckDB ({len(df):,} rows)")

    def list_tables(self) -> List[str]:
        """List registered table names."""
        return list(self._registered_tables.keys())

    def get_dataframe(self, table_name: str) -> Optional[pd.DataFrame]:
        """Get the underlying pandas DataFrame for a registered table."""
        return self._registered_tables.get(table_name)

    def execute_query(
        self,
        query: str,
        max_rows: Optional[int] = None,
        max_chart_rows: int = 500,
        max_llm_rows: int = 15,
        timeout_seconds: Optional[int] = None,
    ) -> QueryResult:
        """
        Validate, apply safety limits, and execute an SQL query against registered tables.
        """
        if max_rows is None:
            max_rows = settings.max_preview_rows
        if timeout_seconds is None:
            timeout_seconds = settings.query_timeout_seconds

        # 1. Validate AST, safety rules, and registered table access
        allowed_tables = set(self._registered_tables.keys()) if self._registered_tables else None
        stmt = validate_sql_security(query, allowed_tables=allowed_tables)

        # 2. Check if user specified a limit
        user_limit_node = stmt.find(exp.Limit)
        has_user_limit = user_limit_node is not None

        # Apply safe limit for preview
        safe_sql = apply_auto_limit(stmt, max_rows=max(max_rows, max_chart_rows))

        logger.debug(f"Executing safe SQL: {safe_sql}")

        # 3. Execute with timeout
        result_df: List[pd.DataFrame] = []
        exec_error: List[Exception] = []

        def _run():
            try:
                df = self._con.execute(safe_sql).df()
                result_df.append(df)
            except Exception as e:
                exec_error.append(e)

        t0 = time.perf_counter()
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            try:
                self._con.interrupt()
            except Exception:
                pass
            thread.join(timeout=2.0)
            raise SQLExecutionError(f"Query timed out after {timeout_seconds} seconds.")

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        if exec_error:
            err = exec_error[0]
            logger.error(f"SQL execution failed: {err}")
            raise SQLExecutionError(f"SQL Error: {str(err)}") from err

        raw_df = result_df[0] if result_df else pd.DataFrame()
        total_fetched = len(raw_df)

        # Truncation calculations (preview is truncated if fetched rows exceed max_rows)
        truncated = total_fetched > max_rows

        preview_df = raw_df.head(max_rows)
        llm_preview_df = raw_df.head(max_llm_rows)
        chart_df = raw_df.head(max_chart_rows)

        return QueryResult(
            df=preview_df,
            sql=safe_sql,
            total_rows=total_fetched,
            truncated=truncated,
            llm_preview_df=llm_preview_df,
            chart_df=chart_df,
            execution_time_ms=elapsed_ms,
        )
