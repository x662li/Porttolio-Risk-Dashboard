"""Tests for performance."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from risk_platform.config import PERFORMANCE_METRIC_KEYS
from risk_platform.models import CleanedWorkbook
from risk_platform.performance import calculate_performance


def _make_cleaned(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
) -> CleanedWorkbook:
    return CleanedWorkbook(
        security_master=pd.DataFrame({"ticker": weights["ticker"], "currency": ["USD"] * len(weights)}),
        portfolio_weights=weights,
        usd_security_returns=returns,
    )


def test_scheme_b_nonzero_nan_makes_portfolio_nan():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "AAA": [float("nan"), 0.10],
            "BBB": [0.02, 0.04],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA", "BBB"], "weight": [0.5, 0.5]})
    metrics = calculate_performance(_make_cleaned(returns, weights))
    wealth = metrics["wealth_curve"]["wealth"].tolist()
    assert pd.isna(wealth[0])
    assert wealth[1] == pytest.approx(1.07)


def test_zero_weight_nan_is_ignored():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "AAA": [float("nan"), 0.10],
            "BBB": [0.02, 0.04],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA", "BBB"], "weight": [0.0, 1.0]})
    metrics = calculate_performance(_make_cleaned(returns, weights))
    wealth = metrics["wealth_curve"]["wealth"].tolist()
    assert wealth[0] == pytest.approx(1.02)
    assert wealth[1] == pytest.approx(1.0608)


def test_nan_breakpoint_compound_continues_from_last_wealth():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "AAA": [0.10, float("nan"), 0.10],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA"], "weight": [1.0]})
    metrics = calculate_performance(_make_cleaned(returns, weights))
    wealth = metrics["wealth_curve"]["wealth"].tolist()
    assert wealth[0] == pytest.approx(1.10)
    assert pd.isna(wealth[1])
    assert wealth[2] == pytest.approx(1.21)


def test_var_es_and_volatility_on_small_sample():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
            ),
            "AAA": [-0.10, -0.05, 0.02, 0.03, -0.08],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA"], "weight": [1.0]})
    metrics = calculate_performance(_make_cleaned(returns, weights))

    daily_std = pd.Series([-0.10, -0.05, 0.02, 0.03, -0.08]).std(ddof=1)
    assert metrics["annualized_volatility"] == pytest.approx(round(daily_std * math.sqrt(252), 4))

    losses = pd.Series([0.10, 0.05, -0.02, -0.03, 0.08])
    assert metrics["var_95"] == pytest.approx(round(float(losses.quantile(0.95)), 4))
    assert metrics["es_95"] == pytest.approx(round(float(losses[losses >= losses.quantile(0.95)].mean()), 4))


def test_max_drawdown_from_wealth_curve():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
            "AAA": [0.10, -0.20, 0.05, 0.05],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA"], "weight": [1.0]})
    metrics = calculate_performance(_make_cleaned(returns, weights))
    assert metrics["max_drawdown"] == pytest.approx(0.20)


def test_output_keys_match_config():
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "AAA": [0.01],
        }
    )
    weights = pd.DataFrame({"ticker": ["AAA"], "weight": [1.0]})
    metrics = calculate_performance(_make_cleaned(returns, weights))
    assert set(metrics) == set(PERFORMANCE_METRIC_KEYS)
