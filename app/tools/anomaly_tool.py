"""Hybrid statistical, machine learning, and domain business rule anomaly detection engine.

### How the Ensemble Combines Methods
The engine employs a 4-pillar ensemble architecture designed for high precision and recall:
1. **Univariate Distribution Extremes (IQR)**:
   Computes Tukey's fences per metric column (Q1 - 1.5*IQR, Q3 + 1.5*IQR). Robust to asymmetric distributions.
2. **Median Absolute Deviation (Modified Z-Score)**:
   Computes Boris Iglewicz and David Hoaglin's Modified Z-Score:
       M_i = 0.6745 * (x_i - Median) / MAD
   where MAD = Median(|x_i - Median|). Points with |M_i| >= 3.5 are flagged. Unlike standard z-scores,
   the median and MAD are unaffected by the presence of extreme outliers in the sample.
3. **Multivariate Outlier Detection (Isolation Forest)**:
   Uses an ensemble of randomized isolation decision trees (scikit-learn) on normalized numeric features.
   Captures complex multi-attribute anomalies (e.g., standard price and standard quantity that in combination
   create an anomalous transaction) that univariate tests miss.
4. **Domain Business Rule (Relative Margin)**:
   Active only when matching 'profit' and 'revenue' (or 'sales') columns exist.
   Evaluates relative margin = (Profit / Revenue). Identifies severe margin erosion (margin < -50%).

### Confidence Classification
- **High Confidence**: At least 2 independent detection methods agreed that the row is anomalous.
- **Possible Anomaly**: Flagged by exactly 1 detector (e.g. slight statistical variance without multivariate confirmation).
"""

from typing import Any, Dict, List, Optional, Tuple, Set
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

def is_id_or_constant_column(series: pd.Series, col_name: str) -> bool:
    """Check if a column is an identifier or has zero variance."""
    name_lower = col_name.lower().replace(" ", "_")
    if (
        name_lower.endswith("_id")
        or name_lower.startswith("id_")
        or name_lower == "id"
        or "order_id" in name_lower
        or "customer_id" in name_lower
        or "product_id" in name_lower
    ):
        return True

    # Check constant / zero variance
    non_null = series.dropna()
    if len(non_null) == 0 or non_null.nunique() <= 1:
        return True

    return False

def calculate_modified_z_score(series: pd.Series) -> pd.Series:
    """
    Compute Boris Iglewicz and David Hoaglin's Modified Z-score using Median and MAD:
    M_i = 0.6745 * (x_i - median) / MAD
    """
    clean = pd.to_numeric(series, errors="coerce")
    median_val = clean.median()
    diff = (clean - median_val).abs()
    mad = diff.median()

    if mad == 0 or pd.isna(mad):
        # Fallback to mean absolute deviation or std dev if MAD is zero
        mad_fallback = diff.mean() * 1.2533
        if mad_fallback > 0:
            return 0.6745 * (clean - median_val) / mad_fallback
        std_val = clean.std()
        if std_val > 0:
            return (clean - median_val) / std_val
        return pd.Series(0.0, index=series.index)

    return 0.6745 * (clean - median_val) / mad

def detect_anomalies_pipeline(
    df: pd.DataFrame,
    target_columns: Optional[List[str]] = None,
    random_state: int = 42,
    min_confidence: str = "possible",  # "possible" (returns all) or "high"
) -> Tuple[pd.DataFrame, str]:
    """
    Run multi-method anomaly detection (IQR, Modified Z-Score, Isolation Forest, Relative Margin).

    Parameters:
        df: Input DataFrame to analyze.
        target_columns: Optional specific column subset to inspect.
        random_state: Fixed seed for Isolation Forest reproducibility.
        min_confidence: 'possible' to return all flagged rows, 'high' for multi-method agreement only.

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

    # 1. Statistical Detection: IQR and Modified Z-Score (Median/MAD) per numeric column
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        clean_s = series.dropna()
        if len(clean_s) < 5:
            continue

        # 1a. Modified Z-Score (Median / MAD)
        med_val = clean_s.median()
        diff = (clean_s - med_val).abs()
        mad_val = diff.median()
        mod_z = calculate_modified_z_score(series)

        for idx, val in series.items():
            if pd.isna(val):
                continue
            z_val = mod_z.get(idx, 0.0)
            if abs(z_val) >= 3.5:
                direction = "above" if z_val > 0 else "below"
                row_reasons[idx].append(
                    f"`{col}`={val:,.2f} has modified z-score {z_val:+.1f} {direction} median ({med_val:,.2f}, MAD: {mad_val:,.2f})"
                )
                row_flags[idx].add("modified_z_score")

        # 1b. IQR Extreme Outlier
        q1 = clean_s.quantile(0.25)
        q3 = clean_s.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lower_iqr = q1 - (1.5 * iqr)
            upper_iqr = q3 + (1.5 * iqr)
            for idx, val in series.items():
                if pd.notna(val) and (val > upper_iqr or val < lower_iqr):
                    direction = "above upper threshold" if val > upper_iqr else "below lower threshold"
                    row_reasons[idx].append(
                        f"`{col}`={val:,.2f} is an IQR outlier ({direction} [{lower_iqr:,.2f}, {upper_iqr:,.2f}])"
                    )
                    row_flags[idx].add("iqr")

    # 2. Relative Margin Rule: (Profit / Revenue) active ONLY when both columns exist
    profit_col = next((c for c in df.columns if c.lower().replace(" ", "_") in {"profit", "net_profit"}), None)
    rev_col = next((c for c in df.columns if c.lower().replace(" ", "_") in {"revenue", "sales", "total_sales", "gross_revenue"}), None)

    if profit_col and rev_col:
        p_series = pd.to_numeric(df[profit_col], errors="coerce")
        r_series = pd.to_numeric(df[rev_col], errors="coerce")

        for idx in df.index:
            p = p_series.get(idx)
            r = r_series.get(idx)
            if pd.notna(p) and pd.notna(r) and r > 0:
                rel_margin = p / r
                # Critical margin anomaly: negative margin worse than -50%
                if rel_margin < -0.50:
                    row_reasons[idx].append(
                        f"Critical relative margin anomaly: margin is {rel_margin*100:.1f}% "
                        f"(loss of -${abs(p):,.2f} on revenue ${r:,.2f})"
                    )
                    row_flags[idx].add("relative_margin_rule")

    # 3. Machine Learning: Isolation Forest (for sample size >= 15)
    clean_numeric_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    clean_numeric_df = clean_numeric_df.fillna(clean_numeric_df.median())

    if len(clean_numeric_df) >= 15:
        try:
            iso = IsolationForest(
                n_estimators=100,
                contamination=0.01,
                random_state=random_state,
            )
            predictions = iso.fit_predict(clean_numeric_df)
            for orig_idx, pred in zip(df.index, predictions):
                if pred == -1:
                    row_reasons[orig_idx].append("Multivariate anomaly confirmed by Isolation Forest")
                    row_flags[orig_idx].add("isolation_forest")
        except Exception:
            pass

    # Determine confidence levels based on ensemble agreement
    flagged_indices = [idx for idx in df.index if row_flags[idx]]

    if not flagged_indices:
        summary = (
            f"Anomaly Detection Audit completed on {len(df):,} rows across {len(numeric_cols)} numeric columns "
            f"({', '.join(numeric_cols)}). No anomalies detected."
        )
        return pd.DataFrame(), summary

    rows_data = []
    for idx in flagged_indices:
        methods = sorted(list(row_flags[idx]))
        methods_count = len(methods)
        confidence = "high" if methods_count >= 2 else "possible"

        if min_confidence == "high" and confidence != "high":
            continue

        label = "[High Confidence]" if confidence == "high" else "[Possible Anomaly]"
        reason_text = f"{label} (Flagged by: {', '.join(methods)}): " + "; ".join(row_reasons[idx])

        row_dict = df.loc[idx].to_dict()
        row_dict["anomaly_confidence"] = confidence
        row_dict["anomaly_methods"] = ", ".join(methods)
        row_dict["methods_agreed"] = methods_count
        row_dict["anomaly_reasons"] = reason_text
        rows_data.append(row_dict)

    if not rows_data:
        return pd.DataFrame(), f"No anomalies met the '{min_confidence}' confidence threshold."

    flagged_df = pd.DataFrame(rows_data)

    high_count = sum(flagged_df["anomaly_confidence"] == "high")
    possible_count = sum(flagged_df["anomaly_confidence"] == "possible")

    summary = (
        f"**Anomaly Detection Report**: Identified **{len(flagged_df)} total anomalies** "
        f"({high_count} High Confidence, {possible_count} Possible) across metrics ({', '.join(numeric_cols)}).\n"
        f"- **High Confidence**: Validated by 2 or more independent methods (IQR, Modified Z-Score, Isolation Forest, Relative Margin).\n"
        f"- **Possible**: Detected by a single method; recommend human analyst review."
    )

    return flagged_df, summary
