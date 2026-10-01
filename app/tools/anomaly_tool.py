"""Hybrid statistical and machine learning anomaly detection engine."""

from typing import Any, Dict, List, Optional, Tuple, Set
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

def is_id_or_constant_column(series: pd.Series, col_name: str) -> bool:
    """Check if a column is an identifier or has zero variance."""
    name_lower = col_name.lower()
    if name_lower.endswith("_id") or name_lower.startswith("id_") or name_lower == "id" or "order_id" in name_lower or "customer_id" in name_lower:
        return True

    # Check constant / zero variance
    non_null = series.dropna()
    if len(non_null) == 0 or non_null.nunique() <= 1:
        return True

    return False

def detect_anomalies_pipeline(
    df: pd.DataFrame,
    target_columns: Optional[List[str]] = None,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, str]:
    """
    Run multi-method anomaly detection (IQR, Z-Score, Isolation Forest, Business Rules).

    Parameters:
        df: Input DataFrame to analyze.
        target_columns: Optional specific column subset to inspect.
        random_state: Fixed seed for Isolation Forest reproducibility.

    Returns:
        (flagged_df, summary_markdown_text)
    """
    if df.empty:
        return pd.DataFrame(), "No data available for anomaly detection."

    # Identify numeric candidate columns
    numeric_cols = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_constant_column(df[c], str(c))
    ]

    if target_columns:
        valid_targets = [c for c in target_columns if c in df.columns and c in numeric_cols]
        if valid_targets:
            numeric_cols = valid_targets

    if not numeric_cols:
        return pd.DataFrame(), "No suitable numeric metrics found for anomaly detection (ID and constant columns skipped)."

    row_reasons: Dict[int, List[str]] = {idx: [] for idx in df.index}
    row_flags: Dict[int, Set[str]] = {idx: set() for idx in df.index}

    # 1. Statistical Detection: IQR & Z-score per column
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        clean_s = series.dropna()
        if len(clean_s) < 5:
            continue

        q1 = clean_s.quantile(0.25)
        q3 = clean_s.quantile(0.75)
        iqr = q3 - q1
        lower_iqr = q1 - (1.5 * iqr)
        upper_iqr = q3 + (1.5 * iqr)

        mean_val = clean_s.mean()
        std_val = clean_s.std()

        for idx, val in series.items():
            if pd.isna(val):
                continue

            # Z-score outlier (|z| >= 3.5)
            if std_val > 0:
                z_score = (val - mean_val) / std_val
                if abs(z_score) >= 3.5:
                    direction = "above" if z_score > 0 else "below"
                    row_reasons[idx].append(
                        f"`{col}`={val:,.2f} is {abs(z_score):.1f} std deviations {direction} mean ({mean_val:,.2f})"
                    )
                    row_flags[idx].add("z_score")

            # Extreme IQR outlier
            if iqr > 0:
                if val > (q3 + 3.5 * iqr) or val < (q1 - 3.5 * iqr):
                    row_reasons[idx].append(
                        f"`{col}`={val:,.2f} is an extreme IQR outlier outside [{lower_iqr:,.2f}, {upper_iqr:,.2f}]"
                    )
                    row_flags[idx].add("iqr")

    # 2. Domain Business Rules: Negative Profit & Extreme Margin Losses
    profit_col = next((c for c in df.columns if c.lower() == "profit"), None)
    rev_col = next((c for c in df.columns if c.lower() == "revenue"), None)

    if profit_col:
        profits = pd.to_numeric(df[profit_col], errors="coerce")
        for idx, p in profits.items():
            if pd.notna(p) and p < -500.0:
                row_reasons[idx].append(
                    f"Severe negative profit of -${abs(p):,.2f} indicates critical margin or pricing anomaly"
                )
                row_flags[idx].add("negative_profit_rule")

    # 3. Machine Learning: Isolation Forest (for sample size >= 15)
    clean_numeric_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(df[numeric_cols].median())
    if len(clean_numeric_df) >= 15:
        try:
            iso = IsolationForest(
                n_estimators=100,
                contamination=0.01,
                random_state=random_state,
            )
            predictions = iso.fit_predict(clean_numeric_df)
            for idx_pos, (orig_idx, pred) in enumerate(zip(df.index, predictions)):
                if pred == -1 and (row_flags[orig_idx] or len(row_reasons[orig_idx]) > 0):
                    row_reasons[orig_idx].append("Confirmed multivariate behavioral outlier by Isolation Forest")
                    row_flags[orig_idx].add("isolation_forest")
        except Exception:
            pass

    # Assemble flagged rows
    flagged_indices = [idx for idx in df.index if row_reasons[idx]]

    if not flagged_indices:
        summary = (
            f"Anomaly Detection Audit completed on {len(df):,} rows across {len(numeric_cols)} numeric columns "
            f"({', '.join(numeric_cols)}). No statistically significant or business rule anomalies detected."
        )
        return pd.DataFrame(), summary

    flagged_df = df.loc[flagged_indices].copy()
    flagged_df["anomaly_reasons"] = ["; ".join(row_reasons[idx]) for idx in flagged_indices]
    flagged_df["detection_methods"] = [", ".join(sorted(row_flags[idx])) for idx in flagged_indices]

    summary = (
        f"**Anomaly Detection Report**: Detected **{len(flagged_df)} anomalous records** ({len(flagged_df)/len(df)*100:.1f}% of total) "
        f"across metrics ({', '.join(numeric_cols)}). Each flagged record has been tagged with plain-language explanations."
    )

    return flagged_df, summary
