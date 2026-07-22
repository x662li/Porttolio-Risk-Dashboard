"""Portfolio performance metrics from cleaned inputs."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from risk_platform.config import (
    ANNUALIZATION_FACTOR,
    DECIMAL_PLACES,
    PERFORMANCE_METRIC_KEYS,
    WEIGHT_NONZERO_THRESHOLD,
    WIDE_DATE_COL,
)
from risk_platform.models import CleanedWorkbook, Metrics

_DASH = "-"
_YEAR_COL = "year"


def _round_scalar(value: float) -> float:
    return round(float(value), DECIMAL_PLACES)


def _compute_portfolio_return(cleaned: CleanedWorkbook) -> pd.DataFrame:
    """Scheme B: portfolio return is NaN if any non-zero-weight security return is NaN."""
    returns = cleaned.usd_security_returns.copy()
    weights = cleaned.portfolio_weights.set_index("ticker")["weight"]

    tickers = [col for col in returns.columns if col != WIDE_DATE_COL]
    active_tickers = [
        ticker
        for ticker in tickers
        if ticker in weights.index and abs(weights[ticker]) > WEIGHT_NONZERO_THRESHOLD
    ]

    if not active_tickers:
        frame = returns[[WIDE_DATE_COL]].copy()
        frame["return"] = np.nan
        return frame

    aligned_weights = weights[active_tickers]
    security_returns = returns[active_tickers]
    invalid = security_returns.isna().any(axis=1)
    portfolio_return = security_returns.mul(aligned_weights, axis=1).sum(axis=1)
    portfolio_return[invalid] = np.nan

    return pd.DataFrame(
        {
            WIDE_DATE_COL: returns[WIDE_DATE_COL].values,
            "return": portfolio_return.round(DECIMAL_PLACES).astype("float64"),
        }
    )


def _compute_portfolio_loss(portfolio_return: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            WIDE_DATE_COL: portfolio_return[WIDE_DATE_COL],
            "loss": (-portfolio_return["return"]).astype("float64"),
        }
    )


def _compute_wealth_curve(portfolio_return: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """NaN breakpoint compound: skip invalid days but continue from last valid wealth."""
    wealth_prev = 1.0
    cumulative: list[float] = []
    wealth: list[float] = []

    for daily_return in portfolio_return["return"]:
        if pd.isna(daily_return):
            cumulative.append(np.nan)
            wealth.append(np.nan)
            continue

        wealth_t = wealth_prev * (1.0 + daily_return)
        cumulative.append(wealth_t - 1.0)
        wealth.append(wealth_t)
        wealth_prev = wealth_t

    return (
        pd.Series(cumulative, dtype="float64"),
        pd.Series(wealth, dtype="float64"),
    )


def _compound_series(daily_returns: pd.Series) -> pd.Series:
    """Compound a series of daily returns from wealth=1.0, NaN breakpoint logic."""
    wealth_prev = 1.0
    wealth: list[float] = []
    for r in daily_returns:
        if pd.isna(r):
            wealth.append(np.nan)
            continue
        wealth_t = wealth_prev * (1.0 + r)
        wealth.append(wealth_t)
        wealth_prev = wealth_t
    return pd.Series(wealth, index=daily_returns.index, dtype="float64")


def _compute_top5_wealth_curves(cleaned: CleanedWorkbook) -> pd.DataFrame:
    """Compute wealth curves for the top-5 abs(weight) securities.

    Short positions have their daily returns sign-flipped before compounding.
    Returns a wide DataFrame: columns = [date, ticker1, ..., ticker5].
    """
    returns = cleaned.usd_security_returns.copy()
    weights = cleaned.portfolio_weights.set_index("ticker")["weight"]

    tickers = [col for col in returns.columns if col != WIDE_DATE_COL]
    # filter to tickers that exist in both returns and weights
    tickers = [t for t in tickers if t in weights.index]

    top5 = (
        weights[tickers]
        .abs()
        .nlargest(5)
        .index.tolist()
    )

    result = returns[[WIDE_DATE_COL]].copy()
    for ticker in top5:
        sign = 1.0 if weights[ticker] >= 0 else -1.0
        adjusted = returns[ticker] * sign
        result[ticker] = _compound_series(adjusted).round(DECIMAL_PLACES).values

    return result


def _compute_drawdown(wealth: pd.Series) -> pd.Series:
    peak = np.nan
    drawdowns: list[float] = []

    for wealth_t in wealth:
        if pd.isna(wealth_t):
            drawdowns.append(np.nan)
            continue
        if pd.isna(peak) or wealth_t > peak:
            peak = wealth_t
        drawdowns.append(wealth_t / peak - 1.0)

    return pd.Series(drawdowns, dtype="float64")


def _compute_max_drawdown(drawdown: pd.Series) -> float:
    valid = drawdown.dropna()
    if valid.empty:
        return float("nan")
    return _round_scalar(-float(valid.min()))


def _compute_annualized_volatility(portfolio_return: pd.DataFrame) -> float:
    valid = portfolio_return["return"].dropna()
    if len(valid) < 2:
        return float("nan")
    daily_std = float(valid.std(ddof=1))
    return _round_scalar(daily_std * math.sqrt(ANNUALIZATION_FACTOR))


def _compute_var_es(portfolio_loss: pd.DataFrame) -> dict[str, float]:
    losses = portfolio_loss["loss"].dropna().sort_values()
    if losses.empty:
        return {
            "var_95": float("nan"),
            "var_99": float("nan"),
            "es_95": float("nan"),
            "es_99": float("nan"),
        }

    var_95 = float(losses.quantile(0.95))
    var_99 = float(losses.quantile(0.99))
    tail_95 = losses[losses >= var_95]
    tail_99 = losses[losses >= var_99]

    return {
        "var_95": _round_scalar(var_95),
        "var_99": _round_scalar(var_99),
        "es_95": _round_scalar(float(tail_95.mean())) if not tail_95.empty else float("nan"),
        "es_99": _round_scalar(float(tail_99.mean())) if not tail_99.empty else float("nan"),
    }


def _compute_annual_metrics(
    portfolio_return: pd.DataFrame,
    portfolio_loss: pd.DataFrame,
    total_risk: dict[str, float],
) -> dict[str, dict]:
    """Build the performance_table dict.

    Annual columns: annualized_volatility, max_drawdown.
    VaR/ES: Total only; 2024/2025 show '-'.
    """
    rows: dict[str, dict] = {
        "annualized_volatility": {},
        "max_drawdown": {},
        "var_95": {},
        "var_99": {},
        "es_95": {},
        "es_99": {},
    }

    # Compute per-year vol and MDD
    dates = pd.to_datetime(portfolio_return[WIDE_DATE_COL])
    for year in (2024, 2025):
        mask = dates.dt.year == year
        yr_ret = portfolio_return[mask].copy()
        if yr_ret.empty or yr_ret["return"].dropna().empty:
            rows["annualized_volatility"][str(year)] = _DASH
            rows["max_drawdown"][str(year)] = _DASH
        else:
            _, yr_wealth = _compute_wealth_curve(yr_ret)
            yr_dd = _compute_drawdown(yr_wealth)
            rows["annualized_volatility"][str(year)] = _compute_annualized_volatility(yr_ret)
            rows["max_drawdown"][str(year)] = _compute_max_drawdown(yr_dd)

    # Total
    _, wealth_all = _compute_wealth_curve(portfolio_return)
    dd_all = _compute_drawdown(wealth_all)
    rows["annualized_volatility"]["Total"] = _compute_annualized_volatility(portfolio_return)
    rows["max_drawdown"]["Total"] = _compute_max_drawdown(dd_all)

    # VaR/ES: total only
    for key in ("var_95", "var_99", "es_95", "es_99"):
        rows[key]["2024"] = _DASH
        rows[key]["2025"] = _DASH
        rows[key]["Total"] = total_risk[key]

    return rows


def calculate_performance(cleaned: CleanedWorkbook) -> Metrics:
    """Compute performance metrics for dashboard display."""
    portfolio_return = _compute_portfolio_return(cleaned)
    portfolio_loss = _compute_portfolio_loss(portfolio_return)
    _cumulative_return, wealth = _compute_wealth_curve(portfolio_return)
    drawdown = _compute_drawdown(wealth)
    risk = _compute_var_es(portfolio_loss)

    wealth_curve = pd.DataFrame(
        {
            WIDE_DATE_COL: portfolio_return[WIDE_DATE_COL],
            "wealth": wealth.round(DECIMAL_PLACES).astype("float64"),
        }
    )

    metrics: Metrics = {
        "wealth_curve": wealth_curve,
        "top5_wealth_curves": _compute_top5_wealth_curves(cleaned),
        "performance_table": _compute_annual_metrics(portfolio_return, portfolio_loss, risk),
        "annualized_volatility": _compute_annualized_volatility(portfolio_return),
        "max_drawdown": _compute_max_drawdown(drawdown),
        **risk,
    }

    if set(metrics) != set(PERFORMANCE_METRIC_KEYS):
        missing = set(PERFORMANCE_METRIC_KEYS) - set(metrics)
        extra = set(metrics) - set(PERFORMANCE_METRIC_KEYS)
        raise RuntimeError(f"Performance metrics key mismatch. missing={missing}, extra={extra}")

    return metrics
