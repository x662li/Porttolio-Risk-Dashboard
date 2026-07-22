"""Stress scenario impact metrics from cleaned inputs."""

from __future__ import annotations

import pandas as pd

from risk_platform.config import (
    DECIMAL_PLACES,
    EQUITY_SELLOFF_MARKET_RETURN,
    RATE_SHOCK_DELTA_Y,
    STRESS_METRIC_KEYS,
)
from risk_platform.models import CleanedWorkbook, Metrics

_EQUITY_TYPES = {"Equity"}
_RATE_TYPES = {"Bond", "Loan"}


def _build_stress_snapshot(cleaned: CleanedWorkbook) -> pd.DataFrame:
    """Merge weights and security master; compute per-security weighted contributions."""
    weights = cleaned.portfolio_weights[["ticker", "weight", "asset_type"]].copy()
    master = cleaned.security_master[
        ["ticker", "equity_beta", "effective_duration", "convexity"]
    ].copy()

    snap = weights.merge(master, on="ticker", how="left")

    # Fill missing risk parameters with 0 (non-applicable asset types)
    snap["equity_beta"] = snap["equity_beta"].fillna(0.0)
    snap["effective_duration"] = snap["effective_duration"].fillna(0.0)
    snap["convexity"] = snap["convexity"].fillna(0.0)

    w = snap["weight"]
    is_equity = snap["asset_type"].isin(_EQUITY_TYPES)
    is_rate = snap["asset_type"].isin(_RATE_TYPES)

    dy = RATE_SHOCK_DELTA_Y
    r_equity = snap["equity_beta"] * (-EQUITY_SELLOFF_MARKET_RETURN)
    r_rate = -snap["effective_duration"] * dy + 0.5 * snap["convexity"] * dy**2

    snap["equity_contribution"] = w * r_equity.where(is_equity, other=0.0)
    snap["rate_contribution"] = w * r_rate.where(is_rate, other=0.0)
    snap["combined_contribution"] = snap["equity_contribution"] + snap["rate_contribution"]

    return snap[["ticker", "weight", "equity_contribution", "rate_contribution", "combined_contribution"]]


def calculate_stress(cleaned: CleanedWorkbook) -> Metrics:
    """Compute portfolio-level stress scenario impacts.

    Returns scalar impacts for each scenario (see ``STRESS_METRIC_KEYS``).
    """
    _ = STRESS_METRIC_KEYS
    snap = _build_stress_snapshot(cleaned)
    return {
        "equity_selloff_impact": round(float(snap["equity_contribution"].sum()), DECIMAL_PLACES),
        "rate_shock_impact": round(float(snap["rate_contribution"].sum()), DECIMAL_PLACES),
        "combined_scenario_impact": round(float(snap["combined_contribution"].sum()), DECIMAL_PLACES),
    }
