"""Datalens Plotly visual theme and color palette definitions."""

import plotly.graph_objects as go
import plotly.io as pio

# Curated Teal & Slate design palette
TEAL_PRIMARY = "#0F766E"
TEAL_HOVER = "#115E59"
TEAL_LIGHT = "#14B8A6"
TEAL_PALE = "#5EEAD4"
TEAL_MINT = "#CCFBF1"

COLOR_PALETTE = [
    "#0F766E",  # Primary Teal
    "#14B8A6",  # Light Teal
    "#0D9488",  # Medium Teal
    "#047857",  # Emerald Deep
    "#0284C7",  # Blue Accent
    "#4F46E5",  # Indigo Accent
    "#D97706",  # Amber Accent
    "#78716C",  # Stone Neutral
]

def get_datalens_plotly_template() -> go.layout.Template:
    """Create a minimal, flat Plotly template matching Datalens UI standards."""
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=12, color="#1C1917"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=40, b=40),
        colorway=COLOR_PALETTE,
        xaxis=dict(
            gridcolor="#E7E5E4",
            gridwidth=1,
            zerolinecolor="#E7E5E4",
            showline=True,
            linecolor="#E7E5E4",
            tickfont=dict(size=11, color="#57534E"),
            title=dict(font=dict(size=12, color="#1C1917")),
        ),
        yaxis=dict(
            gridcolor="#E7E5E4",
            gridwidth=1,
            zerolinecolor="#E7E5E4",
            showline=True,
            linecolor="#E7E5E4",
            tickfont=dict(size=11, color="#57534E"),
            title=dict(font=dict(size=12, color="#1C1917")),
        ),
        hoverlabel=dict(
            bgcolor="#1C1917",
            font=dict(family="JetBrains Mono, monospace", size=12, color="#FFFFFF"),
            bordercolor="#1C1917",
        ),
    )
    return template

# Register the template globally
DATALENS_TEMPLATE = get_datalens_plotly_template()
pio.templates["datalens"] = DATALENS_TEMPLATE
pio.templates.default = "datalens"

def apply_datalens_chart_styling(fig: go.Figure) -> go.Figure:
    """Apply Datalens aesthetic rules to an existing figure."""
    fig.update_layout(
        template="datalens",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", color="#1C1917"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E7E5E4", linecolor="#E7E5E4")
    fig.update_yaxes(showgrid=True, gridcolor="#E7E5E4", linecolor="#E7E5E4")
    return fig
