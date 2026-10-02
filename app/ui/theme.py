"""Datalens Plotly visual theme and color palette definitions matching Precision Analytical System."""

import plotly.graph_objects as go
import plotly.io as pio

# Modern SaaS Analytical palette
PRIMARY_TEAL = "#0D9488"      # Primary
ACCENT_TEAL = "#0F766E"       # Primary Hover / Accent
TEAL_HOVER = "#0F766E"        # Primary Hover
TEAL_ACTIVE = "#115E59"       # Primary Active
TEAL_TINT = "#F0FDFA"         # Accent Tint
TINT_BORDER = "#CCFBF1"       # Accent Border
CANVAS_BG = "#F8FAFC"         # Canvas Ground
SURFACE_BG = "#FFFFFF"        # Surface Base
SUBTLE_SURFACE = "#F1F5F9"    # Subtle Surface
BORDER_COLOR = "#E2E8F0"      # Structural Border
SUBTLE_BORDER = "#F8FAFC"     # Subtle Border
TEXT_PRIMARY = "#0F172A"      # Text Primary
TEXT_SECONDARY = "#64748B"    # Text Secondary
TEXT_MUTED = "#94A3B8"        # Text Muted

COLOR_PALETTE = [
    "#0D9488",  # Primary Teal
    "#0284C7",  # Sky Blue
    "#6366F1",  # Indigo
    "#F59E0B",  # Amber
    "#10B981",  # Emerald
    "#8B5CF6",  # Violet
    "#EC4899",  # Pink
    "#64748B",  # Slate
]

def get_datalens_plotly_template() -> go.layout.Template:
    """Create a minimal, flat Plotly template matching Modern SaaS standards."""
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family="Hanken Grotesk, sans-serif", size=12, color=TEXT_PRIMARY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SURFACE_BG,
        margin=dict(l=40, r=20, t=40, b=40),
        colorway=COLOR_PALETTE,
        xaxis=dict(
            gridcolor=BORDER_COLOR,
            gridwidth=1,
            zerolinecolor=BORDER_COLOR,
            showline=True,
            linecolor=BORDER_COLOR,
            tickfont=dict(family="Hanken Grotesk, sans-serif", size=11, color=TEXT_SECONDARY),
            title=dict(font=dict(family="Hanken Grotesk, sans-serif", size=12, color=TEXT_PRIMARY)),
        ),
        yaxis=dict(
            gridcolor=BORDER_COLOR,
            gridwidth=1,
            zerolinecolor=BORDER_COLOR,
            showline=True,
            linecolor=BORDER_COLOR,
            tickfont=dict(family="JetBrains Mono, monospace", size=11, color=TEXT_SECONDARY),
            title=dict(font=dict(family="Hanken Grotesk, sans-serif", size=12, color=TEXT_PRIMARY)),
        ),
        hoverlabel=dict(
            bgcolor=TEXT_PRIMARY,
            font=dict(family="JetBrains Mono, monospace", size=12, color=SURFACE_BG),
            bordercolor=TEXT_PRIMARY,
        ),
    )
    return template

# Register the template globally
DATALENS_TEMPLATE = get_datalens_plotly_template()
pio.templates["datalens"] = DATALENS_TEMPLATE
pio.templates.default = "datalens"

def apply_datalens_chart_styling(fig: go.Figure) -> go.Figure:
    """Apply Modern SaaS aesthetic rules to an existing figure."""
    fig.update_layout(
        template="datalens",
        paper_bgcolor=SURFACE_BG,
        plot_bgcolor=SURFACE_BG,
        font=dict(family="Hanken Grotesk, sans-serif", color=TEXT_PRIMARY),
    )
    fig.update_xaxes(showgrid=True, gridcolor=BORDER_COLOR, linecolor=BORDER_COLOR)
    fig.update_yaxes(showgrid=True, gridcolor=BORDER_COLOR, linecolor=BORDER_COLOR)
    return fig
