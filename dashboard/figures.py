"""Plotly figure builders (presentation only)."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

from risk_platform.models import PipelineResult, ValidationIssue

_PORTFOLIO_COLOR = "#1f77b4"
_TOP5_COLORS = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

_METRIC_LABELS = {
    "annualized_volatility": "Annualized Volatility",
    "max_drawdown": "Max Drawdown (MDD)",
    "var_95": "VaR 95%",
    "var_99": "VaR 99%",
    "es_95": "ES 95%",
    "es_99": "ES 99%",
}
_METRIC_ORDER = ["var_95", "var_99", "es_95", "es_99", "max_drawdown", "annualized_volatility"]


def _fmt(value: object) -> str:
    """Format a decimal metric as a percentage string with 4 decimal places."""
    if value == "-":
        return "-"
    try:
        return f"{float(value) * 100:.4f}"
    except (TypeError, ValueError):
        return str(value)


def build_wealth_curve_figure(result: PipelineResult) -> go.Figure:
    """Portfolio + top-5 wealth curves with toggle button."""
    wealth_curve = result.metrics["wealth_curve"]
    top5 = result.metrics["top5_wealth_curves"]

    fig = go.Figure()

    top5_tickers = [c for c in top5.columns if c != "date"]
    for i, ticker in enumerate(top5_tickers):
        fig.add_trace(go.Scatter(
            x=top5["date"],
            y=top5[ticker] * 100,
            name=ticker,
            mode="lines",
            line=dict(width=1.5, color=_TOP5_COLORS[i % len(_TOP5_COLORS)]),
            visible=True,
        ))

    fig.add_trace(go.Scatter(
        x=wealth_curve["date"],
        y=wealth_curve["wealth"] * 100,
        name="Portfolio",
        mode="lines",
        line=dict(width=3, color=_PORTFOLIO_COLOR),
        visible=True,
    ))

    n_top5 = len(top5_tickers)

    fig.update_layout(
        title="Portfolio Wealth Curve vs Top-5 Securities",
        xaxis_title="Date",
        yaxis_title="Wealth (% of NAV)",
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                buttons=[
                    dict(
                        label="Show Top 5",
                        method="update",
                        args=[
                            {"visible": [True] * n_top5 + [True]},
                            {"yaxis.autorange": True},
                        ],
                    ),
                    dict(
                        label="Portfolio Only",
                        method="update",
                        args=[
                            {"visible": [False] * n_top5 + [True]},
                            {"yaxis.autorange": True},
                        ],
                    ),
                ],
                x=0.0,
                xanchor="left",
                y=1.12,
                yanchor="top",
            )
        ],
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
        margin=dict(t=80, b=80),
    )
    return fig


def build_performance_table_figure(result: PipelineResult) -> go.Figure:
    """Performance metrics table: rows = metrics, columns = 2024 / 2025 / Total."""
    table_data = result.metrics["performance_table"]

    labels = [_METRIC_LABELS[k] for k in _METRIC_ORDER]
    col_2024 = [_fmt(table_data[k].get("2024", "-")) for k in _METRIC_ORDER]
    col_2025 = [_fmt(table_data[k].get("2025", "-")) for k in _METRIC_ORDER]
    col_total = [_fmt(table_data[k].get("Total", "-")) for k in _METRIC_ORDER]

    fig = go.Figure(go.Table(
        header=dict(
            values=["<b>Metric</b>", "<b>2024 (% of NAV)</b>", "<b>2025 (% of NAV)</b>", "<b>Total (% of NAV)</b>"],
            align="center",
            font=dict(size=13),
        ),
        cells=dict(
            values=[labels, col_2024, col_2025, col_total],
            align=["left", "center", "center", "center"],
            font=dict(size=12),
            height=32,
        ),
    ))
    fig.update_layout(
        title="Performance Metrics",
        margin=dict(t=50, b=10, l=10, r=10),
    )
    return fig


def build_stress_text(result: PipelineResult) -> html.Div:
    """Static stress scenario results display."""
    m = result.metrics
    equity = m.get("equity_selloff_impact", float("nan"))
    rate = m.get("rate_shock_impact", float("nan"))
    combined = m.get("combined_scenario_impact", float("nan"))

    rows = [
        ("Equity Selloff", "beta × −15% × weight", equity),
        ("Rate Shock", "−dur×Δy + ½×cvx×Δy²", rate),
        ("Combined", "equity + rate", combined),
    ]

    table_rows = []
    for label, formula, value in rows:
        try:
            display = f"{float(value) * 100:+.4f}"
        except (TypeError, ValueError):
            display = str(value)
        table_rows.append(html.Tr([
            html.Td(label, style={"fontWeight": "bold", "paddingRight": "16px"}),
            html.Td(formula, style={"color": "#888", "paddingRight": "16px", "fontStyle": "italic"}),
            html.Td(display, style={"textAlign": "right", "fontFamily": "monospace"}),
        ]))

    return html.Div([
        html.H4("Stress Scenario Results", style={"marginBottom": "4px"}),
        html.P("(% of NAV)", style={"fontSize": "11px", "color": "#888", "margin": "0 0 8px 0"}),
        html.Table(
            table_rows,
            style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"},
        ),
    ])


# ---------------------------------------------------------------------------
# Log panel helpers
# ---------------------------------------------------------------------------

_SEVERITY_COLOR = {"ERROR": "#c0392b", "WARN": "#e67e22", "INFO": "#27ae60"}
_SEVERITY_BG = {"ERROR": "#fdf0f0", "WARN": "#fdf6ec", "INFO": "#f0fdf4"}


def _severity_badge(severity: str) -> html.Span:
    color = _SEVERITY_COLOR.get(severity, "#888")
    return html.Span(
        severity,
        style={
            "background": color,
            "color": "#fff",
            "borderRadius": "4px",
            "padding": "2px 7px",
            "fontSize": "11px",
            "fontWeight": "bold",
            "marginRight": "8px",
            "letterSpacing": "0.5px",
        },
    )


def _validation_row(issue: ValidationIssue, show_context: bool) -> html.Div:
    bg = _SEVERITY_BG.get(issue.severity, "#fafafa")
    children: list = [
        html.Div([
            _severity_badge(issue.severity),
            html.Span(
                issue.section,
                style={"fontSize": "11px", "color": "#888", "marginRight": "10px"},
            ),
            html.Span(issue.message, style={"fontSize": "13px"}),
        ], style={"marginBottom": "4px"}),
    ]
    if show_context and issue.context:
        ctx_lines = []
        for k, v in issue.context.items():
            ctx_lines.append(f"  {k}: {v}")
        children.append(html.Pre(
            "\n".join(ctx_lines),
            style={
                "fontSize": "11px",
                "color": "#555",
                "background": "#f8f8f8",
                "border": "1px solid #e0e0e0",
                "borderRadius": "4px",
                "padding": "6px 10px",
                "margin": "4px 0 0 0",
                "whiteSpace": "pre-wrap",
                "overflowX": "auto",
            },
        ))
    return html.Div(
        children,
        style={
            "background": bg,
            "borderLeft": f"4px solid {_SEVERITY_COLOR.get(issue.severity, '#ccc')}",
            "borderRadius": "4px",
            "padding": "8px 12px",
            "marginBottom": "6px",
        },
    )


def _cleaning_row(action: str, detail: str, show_detail: bool) -> html.Div:
    children: list = [
        html.Div([
            html.Span(
                "CLEAN",
                style={
                    "background": "#2980b9",
                    "color": "#fff",
                    "borderRadius": "4px",
                    "padding": "2px 7px",
                    "fontSize": "11px",
                    "fontWeight": "bold",
                    "marginRight": "8px",
                },
            ),
            html.Span(action, style={"fontSize": "13px", "fontWeight": "600"}),
        ], style={"marginBottom": "4px"}),
    ]
    if show_detail and detail:
        children.append(html.P(
            detail,
            style={"fontSize": "12px", "color": "#555", "margin": "2px 0 0 28px"},
        ))
    return html.Div(
        children,
        style={
            "background": "#eaf4fb",
            "borderLeft": "4px solid #2980b9",
            "borderRadius": "4px",
            "padding": "8px 12px",
            "marginBottom": "6px",
        },
    )


def build_log_panel_info(result: PipelineResult) -> html.Div:
    """Info-level log: validation warnings/errors + cleaning action summary.

    Designed for fund managers — highlights only items that require attention.
    """
    issues = result.raw_validation.issues if result.raw_validation else []
    attention = [i for i in issues if i.severity in ("WARN", "ERROR")]

    validation_section = html.Div([
        html.H5(
            f"Validation — {len(attention)} item(s) requiring attention",
            style={"marginBottom": "8px", "color": "#2c3e50"},
        ),
        html.Div(
            [_validation_row(i, show_context=False) for i in attention]
            if attention
            else [html.P("No warnings or errors.", style={"color": "#27ae60", "fontSize": "13px"})],
        ),
    ])

    cleaning_entries = result.cleaning_log or []
    action_summary: dict[str, int] = {}
    for entry in cleaning_entries:
        action_summary[entry.action] = action_summary.get(entry.action, 0) + 1

    cleaning_section = html.Div([
        html.H5(
            f"Cleaning — {len(cleaning_entries)} action(s)",
            style={"marginBottom": "8px", "color": "#2c3e50", "marginTop": "16px"},
        ),
        html.Div(
            [
                html.Div(
                    f"{action}  ×{count}",
                    style={
                        "display": "inline-block",
                        "background": "#2980b9",
                        "color": "#fff",
                        "borderRadius": "12px",
                        "padding": "3px 12px",
                        "fontSize": "12px",
                        "marginRight": "8px",
                        "marginBottom": "6px",
                    },
                )
                for action, count in sorted(action_summary.items())
            ]
        ) if action_summary else html.P("No cleaning actions.", style={"color": "#888", "fontSize": "13px"}),
    ])

    return html.Div([validation_section, cleaning_section])


def build_log_panel_debug(result: PipelineResult) -> html.Div:
    """Debug-level log: all validation items with context + full cleaning log."""
    issues = result.raw_validation.issues if result.raw_validation else []

    by_section: dict[str, list] = {}
    for issue in issues:
        by_section.setdefault(issue.section, []).append(issue)

    section_divs = []
    for section, section_issues in by_section.items():
        section_divs.append(html.Div([
            html.H6(section, style={"color": "#555", "marginBottom": "6px", "marginTop": "12px"}),
            html.Div([_validation_row(i, show_context=True) for i in section_issues]),
        ]))

    validation_block = html.Div([
        html.H5("Validation (all items)", style={"marginBottom": "4px", "color": "#2c3e50"}),
        html.Div(section_divs) if section_divs else html.P("No validation data.", style={"color": "#888"}),
    ])

    cleaning_entries = result.cleaning_log or []
    cleaning_block = html.Div([
        html.H5(
            f"Cleaning Log ({len(cleaning_entries)} entries)",
            style={"marginBottom": "8px", "color": "#2c3e50", "marginTop": "20px"},
        ),
        html.Div(
            [_cleaning_row(e.action, e.detail, show_detail=True) for e in cleaning_entries]
            if cleaning_entries
            else [html.P("No cleaning actions.", style={"color": "#888", "fontSize": "13px"})],
        ),
    ])

    return html.Div([validation_block, cleaning_block])

