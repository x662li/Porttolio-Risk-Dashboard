"""Lightweight Dash callbacks (filter only, no recalculation)."""

from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, html, no_update

from risk_platform.models import PipelineResult

_TABLE_CELL = {"padding": "8px 12px", "border": "1px solid #ddd", "textAlign": "right", "fontFamily": "monospace"}
_TABLE_HEADER = {**_TABLE_CELL, "background": "#f0f0f0", "fontWeight": "bold", "textAlign": "center"}
_TABLE_LABEL = {**_TABLE_CELL, "textAlign": "left", "fontFamily": "Arial, sans-serif", "fontWeight": "600"}


def register_callbacks(app, result: PipelineResult) -> None:
    """Register minimal callbacks that filter pre-computed results."""

    @app.callback(
        Output("wealth-curve-chart", "figure"),
        Input("wealth-curve-chart", "relayoutData"),
        State("wealth-curve-chart", "figure"),
        prevent_initial_call=True,
    )
    def rescale_y_on_xzoom(relayout_data: dict | None, current_figure: dict):
        """Auto-scale y-axis to visible data whenever the x-axis range changes."""
        if not relayout_data or not current_figure:
            return no_update

        # Zoom reset (double-click or home button): restore full autorange
        if relayout_data.get("xaxis.autorange") or relayout_data.get("autosize"):
            current_figure["layout"]["yaxis"] = {"autorange": True}
            return current_figure

        x_min = relayout_data.get("xaxis.range[0]")
        x_max = relayout_data.get("xaxis.range[1]")
        if x_min is None or x_max is None:
            return no_update

        x_min_ts = pd.Timestamp(x_min)
        x_max_ts = pd.Timestamp(x_max)

        y_vals: list[float] = []
        for trace in current_figure.get("data", []):
            if trace.get("visible") is False:
                continue
            xs = trace.get("x", [])
            ys = trace.get("y", [])
            for x, y in zip(xs, ys):
                if y is None:
                    continue
                try:
                    if x_min_ts <= pd.Timestamp(x) <= x_max_ts:
                        y_vals.append(float(y))
                except Exception:
                    continue

        if not y_vals:
            return no_update

        pad = (max(y_vals) - min(y_vals)) * 0.05 or 0.01
        current_figure["layout"]["yaxis"] = {
            "autorange": False,
            "range": [min(y_vals) - pad, max(y_vals) + pad],
        }
        return current_figure

    @app.callback(
        Output("exposure-output", "children"),
        Input("filter-asset-type", "value"),
        Input("filter-sector", "value"),
        Input("filter-country", "value"),
        Input("filter-rating", "value"),
    )
    def update_exposure(asset_type: str, sector: str, country: str, rating: str):
        fact = result.metrics["exposure_fact_table"].copy()

        if asset_type != "All":
            fact = fact[fact["asset_type"] == asset_type]
        if sector != "All":
            fact = fact[fact["sector"] == sector]
        if country != "All":
            fact = fact[fact["country"] == country]
        if rating != "All":
            fact = fact[fact["rating"] == rating]

        net = float(fact["net_contribution"].sum())
        gross = float(fact["gross_contribution"].sum())

        n_securities = len(fact[fact["weight"] != 0.0])

        return html.Div([
            html.P(
                f"{n_securities} securities matched",
                style={"fontSize": "12px", "color": "#888", "marginBottom": "8px"},
            ),
            html.Table(
                style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"},
                children=[
                    html.Thead(html.Tr([
                        html.Th("Metric", style=_TABLE_HEADER),
                        html.Th("Value", style=_TABLE_HEADER),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td("Net Exposure", style=_TABLE_LABEL),
                            html.Td(f"{net:+.4f}", style=_TABLE_CELL),
                        ]),
                        html.Tr([
                            html.Td("Gross Exposure", style=_TABLE_LABEL),
                            html.Td(f"{gross:.4f}", style=_TABLE_CELL),
                        ]),
                    ]),
                ],
            ),
        ])
