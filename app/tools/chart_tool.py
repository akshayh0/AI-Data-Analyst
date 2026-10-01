"""Plotly chart generation and validation tool."""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

class ChartValidationError(Exception):
    """Raised when a chart specification is invalid."""
    pass

ALLOWED_CHART_TYPES = {"bar", "line", "pie", "scatter", "histogram"}

def build_plotly_chart(spec: Dict[str, Any], df: pd.DataFrame) -> go.Figure:
    """
    Validate chart specification against DataFrame and generate a styled Plotly figure.

    Parameters:
        spec: Dictionary with keys: chart_type, x, y, title, color (optional)
        df: Input DataFrame containing the query/aggregation result.

    Returns:
        plotly.graph_objects.Figure
    """
    chart_type = str(spec.get("chart_type", "")).strip().lower()
    x = spec.get("x")
    y = spec.get("y")
    color = spec.get("color")
    title = spec.get("title", f"{chart_type.title()} Chart")

    # 1. Validate chart type
    if chart_type not in ALLOWED_CHART_TYPES:
        raise ChartValidationError(
            f"Unsupported chart type '{chart_type}'. Allowed types: {', '.join(sorted(ALLOWED_CHART_TYPES))}."
        )

    # 2. Handle empty data
    if df.empty or len(df.columns) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for visualization",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#888888"),
        )
        fig.update_layout(title=title, template="plotly_white")
        return fig

    # 3. Validate columns
    df_cols = [str(c) for c in df.columns]

    if not x or x not in df_cols:
        raise ChartValidationError(f"X-axis column '{x}' not found in data columns: {df_cols}")

    if chart_type != "histogram":
        if not y or y not in df_cols:
            raise ChartValidationError(f"Y-axis column '{y}' not found in data columns: {df_cols}")

    if color and color not in df_cols:
        color = None  # Gracefully ignore invalid color column

    plot_df = df.copy()

    # 4. Handle too many data points (downsample for performance and readability)
    max_scatter_points = 500
    if len(plot_df) > max_scatter_points and chart_type in ["scatter", "line"]:
        plot_df = plot_df.sample(n=max_scatter_points, random_state=42).sort_values(by=x)
        title = f"{title} (Sample of {max_scatter_points} points)"

    # 5. Build chart by type
    if chart_type == "pie":
        # Aggregate and group small categories into "Other"
        agg_df = plot_df.groupby(x, as_index=False)[y].sum().sort_values(by=y, ascending=False)
        top_n = 6
        if len(agg_df) > top_n:
            top_part = agg_df.iloc[:top_n].copy()
            other_val = agg_df.iloc[top_n:][y].sum()
            other_row = pd.DataFrame([{x: "Other", y: other_val}])
            agg_df = pd.concat([top_part, other_row], ignore_index=True)

        fig = px.pie(
            agg_df,
            names=x,
            values=y,
            title=title,
            hole=0.35,  # Donut style
            color_discrete_sequence=px.colors.qualitative.Prism,
        )

    elif chart_type == "bar":
        fig = px.bar(
            plot_df,
            x=x,
            y=y,
            color=color,
            title=title,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Vivid,
        )

    elif chart_type == "line":
        # Sort by x if x resembles dates or numbers
        try:
            plot_df = plot_df.sort_values(by=x)
        except Exception:
            pass

        fig = px.line(
            plot_df,
            x=x,
            y=y,
            color=color,
            title=title,
            markers=True,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Vivid,
        )

    elif chart_type == "scatter":
        fig = px.scatter(
            plot_df,
            x=x,
            y=y,
            color=color,
            title=title,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )

    elif chart_type == "histogram":
        fig = px.histogram(
            plot_df,
            x=x,
            y=y,
            color=color,
            title=title,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )

    # Clean layout styling
    fig.update_layout(
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(family="Inter, sans-serif", size=12),
    )

    return fig
