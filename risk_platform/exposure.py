"""Portfolio exposure metrics from cleaned inputs."""

from __future__ import annotations

import pandas as pd

from risk_platform.config import (
    DECIMAL_PLACES,
    EXPOSURE_FACT_COLUMNS,
    EXPOSURE_METRIC_KEYS,
)
from risk_platform.models import CleanedWorkbook, Metrics


def _build_exposure_fact_table(cleaned: CleanedWorkbook) -> pd.DataFrame:
    """Build a security-level exposure fact table from cleaned portfolio weights."""
    weights = cleaned.portfolio_weights[
        ["ticker", "asset_type", "sector", "country", "rating", "weight"]
    ].copy()

    w = weights["weight"].fillna(0.0)
    weights["long_contribution"] = w.clip(lower=0.0).round(DECIMAL_PLACES)
    weights["short_contribution"] = w.clip(upper=0.0).round(DECIMAL_PLACES)
    weights["net_contribution"] = weights["weight"].round(DECIMAL_PLACES)
    weights["gross_contribution"] = w.abs().round(DECIMAL_PLACES)
    weights["weight"] = weights["weight"].round(DECIMAL_PLACES)

    fact = weights[list(EXPOSURE_FACT_COLUMNS)].sort_values("ticker").reset_index(drop=True)
    assert list(fact.columns) == list(EXPOSURE_FACT_COLUMNS), "Column mismatch in exposure_fact_table"
    return fact


def calculate_exposure(cleaned: CleanedWorkbook) -> Metrics:
    """Compute exposure fact table for dashboard display."""
    _ = EXPOSURE_METRIC_KEYS
    fact = _build_exposure_fact_table(cleaned)
    return {"exposure_fact_table": fact}
