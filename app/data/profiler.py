"""Dataset profiling and LLM schema summary generator."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

@dataclass
class ColumnProfile:
    """Detailed profile metrics for a single column."""
    name: str
    original_name: str
    dtype: str
    null_count: int
    null_percentage: float
    unique_count: int
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    mean_value: Optional[float] = None
    sample_values: List[Any] = field(default_factory=list)

@dataclass
class TableProfile:
    """Aggregated profile metrics for a table."""
    table_name: str
    filename: str
    row_count: int
    column_count: int
    columns: Dict[str, ColumnProfile]
    sample_rows: List[Dict[str, Any]]
    column_mapping: Dict[str, str] = field(default_factory=dict)

    def to_llm_schema_prompt(self, max_sample_rows: int = 3) -> str:
        """
        Generate a concise, token-efficient schema representation for the LLM.
        Sends ONLY column names, types, null %, min/max, and a few sample rows.
        Never sends the full dataset.
        """
        lines = [
            f"Table: `{self.table_name}` ({self.row_count:,} rows, {self.column_count} columns)",
            "Columns:",
        ]

        for col_name, prof in self.columns.items():
            col_info = f"  - `{col_name}` ({prof.dtype})"
            stats = []
            if prof.null_count > 0:
                stats.append(f"nulls: {prof.null_percentage:.1f}%")
            stats.append(f"distinct: {prof.unique_count}")
            if prof.min_value is not None and prof.max_value is not None:
                stats.append(f"range: [{prof.min_value} to {prof.max_value}]")
            if prof.mean_value is not None:
                stats.append(f"avg: {prof.mean_value:.2f}")

            if stats:
                col_info += f" -> {', '.join(stats)}"
            lines.append(col_info)

        # Include sample rows
        lines.append(f"Sample data ({min(len(self.sample_rows), max_sample_rows)} rows):")
        samples = self.sample_rows[:max_sample_rows]
        if samples:
            sample_df = pd.DataFrame(samples)
            lines.append(sample_df.to_string(index=False))

        return "\n".join(lines)

def profile_dataframe(
    df: pd.DataFrame,
    table_name: str,
    filename: str,
    column_mapping: Optional[Dict[str, str]] = None,
    sample_size: int = 3
) -> TableProfile:
    """
    Compute statistical profile and sample rows for a pandas DataFrame.
    """
    row_count, col_count = df.shape
    columns_profile: Dict[str, ColumnProfile] = {}
    col_map = column_mapping or {c: c for c in df.columns}

    # Invert mapping for quick lookup: clean -> original
    clean_to_orig = {v: k for k, v in col_map.items()}

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        null_pct = (null_count / row_count * 100.0) if row_count > 0 else 0.0
        unique_cnt = int(series.nunique(dropna=True))
        dtype_str = str(series.dtype)

        min_val, max_val, mean_val = None, None, None
        non_null_series = series.dropna()

        if not non_null_series.empty:
            if pd.api.types.is_numeric_dtype(series):
                try:
                    min_val = round(float(non_null_series.min()), 2)
                    max_val = round(float(non_null_series.max()), 2)
                    mean_val = round(float(non_null_series.mean()), 2)
                except Exception:
                    pass
            elif pd.api.types.is_datetime64_any_dtype(series):
                min_val = str(non_null_series.min())
                max_val = str(non_null_series.max())
            else:
                # String / object / categorical
                try:
                    vals = non_null_series.astype(str)
                    min_val = vals.min()
                    max_val = vals.max()
                except Exception:
                    pass

        sample_vals = non_null_series.head(3).tolist()

        columns_profile[col] = ColumnProfile(
            name=col,
            original_name=clean_to_orig.get(col, col),
            dtype=dtype_str,
            null_count=null_count,
            null_percentage=round(null_pct, 2),
            unique_count=unique_cnt,
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            sample_values=sample_vals,
        )

    # Convert preview rows to serializable records
    sample_df = df.head(sample_size).copy()
    sample_rows = sample_df.to_dict(orient="records")

    return TableProfile(
        table_name=table_name,
        filename=filename,
        row_count=row_count,
        column_count=col_count,
        columns=columns_profile,
        sample_rows=sample_rows,
        column_mapping=col_map,
    )
