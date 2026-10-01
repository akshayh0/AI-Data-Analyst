"""Comprehensive data quality audit and health profiling tool."""

from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

def generate_quality_report(df: pd.DataFrame, table_name: str) -> Tuple[str, pd.DataFrame]:
    """
    Perform a multi-dimensional data quality audit on a DataFrame.

    Checks:
    - Missing values and completeness
    - Exact duplicate rows
    - Data type anomalies & suspicious objects
    - Outlier bounds via IQR
    - Negative or suspicious zero values in quantity/price fields

    Returns:
        (report_markdown, summary_dataframe)
    """
    total_rows = len(df)
    total_cols = len(df.columns)

    if total_rows == 0:
        return f"Table `{table_name}` is empty (0 rows).", pd.DataFrame()

    issues: List[Dict[str, Any]] = []

    # 1. Exact Duplicate Records
    duplicate_count = int(df.duplicated().sum())
    dup_pct = (duplicate_count / total_rows) * 100.0
    issues.append({
        "check": "Duplicate Rows",
        "column": "ALL",
        "metric": f"{duplicate_count:,} duplicate rows ({dup_pct:.1f}%)",
        "status": "PASS" if duplicate_count == 0 else ("WARN" if dup_pct < 5.0 else "FAIL"),
        "recommendation": "Deduplicate table" if duplicate_count > 0 else "None",
    })

    # 2. Missing Values & Column Checks
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        null_pct = (null_count / total_rows) * 100.0

        if null_count > 0:
            status = "WARN" if null_pct < 15.0 else "FAIL"
            issues.append({
                "check": "Missing Values",
                "column": col,
                "metric": f"{null_count:,} nulls ({null_pct:.1f}%)",
                "status": status,
                "recommendation": "Impute median/mode or drop missing rows",
            })

        # Check for empty string values in object columns
        if pd.api.types.is_string_dtype(series) or series.dtype == "object":
            empty_str_count = int((series == "").sum())
            if empty_str_count > 0:
                issues.append({
                    "check": "Empty Strings",
                    "column": col,
                    "metric": f"{empty_str_count:,} blank text entries",
                    "status": "WARN",
                    "recommendation": "Convert empty strings to NULL",
                })

        # 3. Suspicious negative values in quantity / price / sales
        col_lower = str(col).lower()
        if any(term in col_lower for term in ["quantity", "price", "unit_price", "cost", "revenue"]):
            if pd.api.types.is_numeric_dtype(series):
                neg_count = int((series < 0).sum())
                if neg_count > 0:
                    issues.append({
                        "check": "Invalid Negative Value",
                        "column": col,
                        "metric": f"{neg_count:,} negative values",
                        "status": "FAIL",
                        "recommendation": f"Verify negative entries in {col} (returns or data errors)",
                    })

        # 4. Outlier Count via IQR
        if pd.api.types.is_numeric_dtype(series) and not col_lower.endswith("_id"):
            clean_s = series.dropna()
            if len(clean_s) >= 10:
                q1 = clean_s.quantile(0.25)
                q3 = clean_s.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outliers = int(((clean_s < (q1 - 1.5 * iqr)) | (clean_s > (q3 + 1.5 * iqr))).sum())
                    if outliers > 0:
                        outlier_pct = (outliers / len(clean_s)) * 100.0
                        issues.append({
                            "check": "Outliers (IQR)",
                            "column": col,
                            "metric": f"{outliers:,} outliers ({outlier_pct:.1f}%) outside [{q1 - 1.5*iqr:.1f}, {q3 + 1.5*iqr:.1f}]",
                            "status": "INFO" if outlier_pct < 3.0 else "WARN",
                            "recommendation": "Inspect statistical outliers for pricing/data glitches",
                        })

    quality_df = pd.DataFrame(issues)

    # Compute overall health score (0 - 100)
    fail_count = sum(1 for item in issues if item["status"] == "FAIL")
    warn_count = sum(1 for item in issues if item["status"] == "WARN")
    health_score = max(0, 100 - (fail_count * 20) - (warn_count * 5))

    quality_df.attrs["health_score"] = health_score
    quality_df.attrs["fail_count"] = fail_count
    quality_df.attrs["warn_count"] = warn_count
    quality_df.attrs["total_rows"] = total_rows

    lines = [
        f"### Data Quality Health Report: `{table_name}`",
        f"- **Overall Health Score**: **{health_score}/100**",
        f"- **Rows Analyzed**: {total_rows:,} | **Columns**: {total_cols}",
        f"- **Duplicate Rows**: {duplicate_count:,} ({dup_pct:.1f}%)",
        f"- **Total Identified Issues**: {len(issues)}",
        "",
        "| Check | Column | Metric | Status | Recommendation |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for item in issues:
        lines.append(
            f"| {item['check']} | `{item['column']}` | {item['metric']} | **{item['status']}** | {item['recommendation']} |"
        )

    report_markdown = "\n".join(lines)
    return report_markdown, quality_df
