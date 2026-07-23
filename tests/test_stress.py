"""Tests for stress scenario calculations."""

from __future__ import annotations

import pandas as pd
import pytest

from risk_platform.config import (
    EQUITY_SELLOFF_MARKET_RETURN,
    RATE_SHOCK_DELTA_Y,
    STRESS_METRIC_KEYS,
)
from risk_platform.models import CleanedWorkbook
from risk_platform.stress import _build_stress_snapshot, calculate_stress


def _make_cleaned(
    weights: list[tuple],
    master: list[tuple],
) -> CleanedWorkbook:
    """
    weights: (ticker, weight, asset_type)
    master:  (ticker, equity_beta, effective_duration, convexity)
    """
    pw = pd.DataFrame(weights, columns=["ticker", "weight", "asset_type"])
    pw["ticker"] = pw["ticker"].astype("string")
    pw["weight"] = pw["weight"].astype("float64")

    sm = pd.DataFrame(master, columns=["ticker", "equity_beta", "effective_duration", "convexity"])
    sm["ticker"] = sm["ticker"].astype("string")

    return CleanedWorkbook(
        security_master=sm,
        portfolio_weights=pw,
        usd_security_returns=pd.DataFrame(),
    )


# --- Equity selloff ---

def test_equity_selloff_formula():
    beta = 1.2
    weight = 0.4
    cleaned = _make_cleaned(
        weights=[("EQ1", weight, "Equity")],
        master=[("EQ1", beta, float("nan"), float("nan"))],
    )
    metrics = calculate_stress(cleaned)
    expected = weight * beta * (-EQUITY_SELLOFF_MARKET_RETURN)
    assert metrics["equity_selloff_impact"] == pytest.approx(expected, abs=1e-6)


def test_equity_only_portfolio_rate_shock_is_zero():
    cleaned = _make_cleaned(
        weights=[("EQ1", 0.5, "Equity"), ("EQ2", 0.5, "Equity")],
        master=[
            ("EQ1", 1.0, float("nan"), float("nan")),
            ("EQ2", 0.8, float("nan"), float("nan")),
        ],
    )
    metrics = calculate_stress(cleaned)
    assert metrics["rate_shock_impact"] == pytest.approx(0.0, abs=1e-6)


# --- Rate shock ---

def test_rate_shock_formula_bond():
    duration = 5.0
    convexity = 0.3
    weight = 0.6
    dy = RATE_SHOCK_DELTA_Y
    cleaned = _make_cleaned(
        weights=[("BD1", weight, "Bond")],
        master=[("BD1", float("nan"), duration, convexity)],
    )
    metrics = calculate_stress(cleaned)
    r_rate = -duration * dy + 0.5 * convexity * dy**2
    expected = weight * r_rate
    # Tolerance reflects DECIMAL_PLACES=4 rounding; convexity term (~1.5e-5) is within rounding
    assert metrics["rate_shock_impact"] == pytest.approx(expected, abs=5e-5)


def test_rate_shock_formula_loan():
    duration = 3.0
    convexity = 0.1
    weight = 0.3
    dy = RATE_SHOCK_DELTA_Y
    cleaned = _make_cleaned(
        weights=[("LN1", weight, "Loan")],
        master=[("LN1", float("nan"), duration, convexity)],
    )
    metrics = calculate_stress(cleaned)
    r_rate = -duration * dy + 0.5 * convexity * dy**2
    expected = weight * r_rate
    # Tolerance reflects DECIMAL_PLACES=4 rounding; convexity term (~1.5e-6) is within rounding
    assert metrics["rate_shock_impact"] == pytest.approx(expected, abs=5e-5)


def test_bond_only_portfolio_equity_selloff_is_zero():
    cleaned = _make_cleaned(
        weights=[("BD1", 1.0, "Bond")],
        master=[("BD1", float("nan"), 4.0, 0.2)],
    )
    metrics = calculate_stress(cleaned)
    assert metrics["equity_selloff_impact"] == pytest.approx(0.0, abs=1e-6)


# --- Mixed portfolio ---

def test_mixed_portfolio_combined_equals_sum():
    cleaned = _make_cleaned(
        weights=[
            ("EQ1", 0.4, "Equity"),
            ("BD1", 0.6, "Bond"),
        ],
        master=[
            ("EQ1", 1.0, float("nan"), float("nan")),
            ("BD1", float("nan"), 5.0, 0.25),
        ],
    )
    metrics = calculate_stress(cleaned)
    assert metrics["combined_scenario_impact"] == pytest.approx(
        metrics["equity_selloff_impact"] + metrics["rate_shock_impact"], abs=1e-6
    )


def test_zero_weight_contributes_nothing():
    cleaned = _make_cleaned(
        weights=[("EQ1", 0.0, "Equity")],
        master=[("EQ1", 2.0, float("nan"), float("nan"))],
    )
    metrics = calculate_stress(cleaned)
    assert metrics["equity_selloff_impact"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["combined_scenario_impact"] == pytest.approx(0.0, abs=1e-6)


# --- Output key validation ---

def test_output_keys_present():
    cleaned = _make_cleaned(
        weights=[("EQ1", 0.5, "Equity"), ("BD1", 0.5, "Bond")],
        master=[
            ("EQ1", 1.0, float("nan"), float("nan")),
            ("BD1", float("nan"), 4.0, 0.2),
        ],
    )
    metrics = calculate_stress(cleaned)
    for key in STRESS_METRIC_KEYS:
        assert key in metrics
        assert isinstance(metrics[key], float)
