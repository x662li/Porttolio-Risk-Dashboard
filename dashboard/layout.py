"""Dash page layout."""

from __future__ import annotations

from dash import dcc, html

from dashboard.figures import (
    build_log_panel_debug,
    build_log_panel_info,
    build_performance_table_figure,
    build_stress_text,
    build_wealth_curve_figure,
)
from risk_platform.models import PipelineResult

_ASSET_TYPES = ["All", "Bond", "Equity", "Loan"]
_SECTORS = [
    "All", "Communication", "Consumer", "Energy", "Financials",
    "Healthcare", "Industrials", "Materials", "Real Estate",
    "Technology", "Utilities",
]
_COUNTRIES = ["All", "Australia", "Canada", "France", "Germany", "Japan", "United Kingdom", "United States"]
_RATINGS = ["All", "A", "AA", "AAA", "B", "BB", "BBB", "CCC", "NR"]

_DROPDOWN_STYLE = {"minWidth": "140px", "fontSize": "13px"}
_CARD_STYLE = {
    "background": "#fff",
    "borderRadius": "8px",
    "padding": "16px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
}


def _dropdown(id_: str, options: list[str], label: str) -> html.Div:
    return html.Div([
        html.Label(label, style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px", "display": "block"}),
        dcc.Dropdown(
            id=id_,
            options=[{"label": o, "value": o} for o in options],
            value="All",
            clearable=False,
            style=_DROPDOWN_STYLE,
        ),
    ], style={"flex": "1", "minWidth": "120px"})


def create_layout(result: PipelineResult) -> html.Div:
    """Build the dashboard layout from pre-computed pipeline results."""
    return html.Div(
        style={"fontFamily": "Arial, sans-serif", "background": "#f5f6fa", "minHeight": "100vh", "padding": "24px"},
        children=[
            html.H2(
                "Mini Portfolio Risk Dashboard",
                style={"textAlign": "center", "marginBottom": "24px", "color": "#2c3e50"},
            ),

            # Row 1: Wealth curve (full width)
            html.Div(
                style={**_CARD_STYLE, "marginBottom": "20px"},
                children=[
                    dcc.Graph(
                        id="wealth-curve-chart",
                        figure=build_wealth_curve_figure(result),
                        config={"scrollZoom": True},
                        style={"height": "420px"},
                    )
                ],
            ),

            # Row 2: three panels
            html.Div(
                style={"display": "flex", "gap": "20px", "alignItems": "stretch"},
                children=[

                    # Panel 2a: Performance metrics table
                    html.Div(
                        style={**_CARD_STYLE, "flex": "1"},
                        children=[
                            dcc.Graph(
                                id="performance-table",
                                figure=build_performance_table_figure(result),
                                config={"displayModeBar": False},
                                style={"height": "340px"},
                            )
                        ],
                    ),

                    # Panel 2b: Exposure filter
                    html.Div(
                        style={**_CARD_STYLE, "flex": "1"},
                        children=[
                            html.H4("Exposure Filter", style={"marginTop": 0, "marginBottom": "12px"}),
                            html.Div(
                                style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "16px"},
                                children=[
                                    _dropdown("filter-asset-type", _ASSET_TYPES, "Asset Type"),
                                    _dropdown("filter-sector", _SECTORS, "Sector"),
                                    _dropdown("filter-country", _COUNTRIES, "Country"),
                                    _dropdown("filter-rating", _RATINGS, "Rating"),
                                ],
                            ),
                            html.Div(id="exposure-output"),
                        ],
                    ),

                    # Panel 2c: Stress test results
                    html.Div(
                        style={**_CARD_STYLE, "flex": "1"},
                        children=[build_stress_text(result)],
                    ),
                ],
            ),

            # Row 3: Validation & Cleaning Logs
            html.Div(
                style={**_CARD_STYLE, "marginTop": "20px"},
                children=[
                    html.H4(
                        "Data Validation & Cleaning Log",
                        style={"marginTop": 0, "marginBottom": "12px", "color": "#2c3e50"},
                    ),
                    dcc.Tabs(
                        id="log-tabs",
                        value="info",
                        children=[
                            dcc.Tab(
                                label="Info  (warnings & errors only)",
                                value="info",
                                children=[
                                    html.Div(
                                        build_log_panel_info(result),
                                        style={"padding": "16px 4px", "maxHeight": "400px", "overflowY": "auto"},
                                    )
                                ],
                            ),
                            dcc.Tab(
                                label="Debug  (all items + context)",
                                value="debug",
                                children=[
                                    html.Div(
                                        build_log_panel_debug(result),
                                        style={"padding": "16px 4px", "maxHeight": "600px", "overflowY": "auto"},
                                    )
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
