"""Tests for exposure fact table."""

from __future__ import annotations

import pandas as pd
import pytest

from risk_platform.config import EXPOSURE_FACT_COLUMNS
from risk_platform.exposure import calculate_exposure, _build_exposure_fact_table
from risk_platform.models import CleanedWorkbook


def _make_cleaned(weights: list[tuple]) -> CleanedWorkbook:
    """weights: list of (ticker, asset_type, sector, country, rating, weight)"""
    df = pd.DataFrame(
        weights,
        columns=["ticker", "asset_type", "sector", "country", "rating", "weight"],
    )
    df["ticker"] = df["ticker"].astype("string")
    df["weight"] = df["weight"].astype("float64")
    return CleanedWorkbook(
        security_master=pd.DataFrame(),
        portfolio_weights=df,
        usd_security_returns=pd.DataFrame(),
    )


@pytest.fixture
def mixed_cleaned():
    return _make_cleaned([
        ("AAA", "Equity", "Tech", "US", "NR", 0.5),
        ("BBB", "Bond", "Finance", "UK", "A", -0.1),
        ("CCC", "Loan", "Energy", "DE", "BBB", 0.0),
    ])


def test_contribution_formula(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    row_aaa = fact[fact["ticker"] == "AAA"].iloc[0]
    assert row_aaa["long_contribution"] == pytest.approx(0.5)
    assert row_aaa["short_contribution"] == pytest.approx(0.0)
    assert row_aaa["net_contribution"] == pytest.approx(0.5)
    assert row_aaa["gross_contribution"] == pytest.approx(0.5)

    row_bbb = fact[fact["ticker"] == "BBB"].iloc[0]
    assert row_bbb["long_contribution"] == pytest.approx(0.0)
    assert row_bbb["short_contribution"] == pytest.approx(-0.1)
    assert row_bbb["net_contribution"] == pytest.approx(-0.1)
    assert row_bbb["gross_contribution"] == pytest.approx(0.1)


def test_zero_weight_row(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    row_ccc = fact[fact["ticker"] == "CCC"].iloc[0]
    assert row_ccc["long_contribution"] == pytest.approx(0.0)
    assert row_ccc["short_contribution"] == pytest.approx(0.0)
    assert row_ccc["net_contribution"] == pytest.approx(0.0)
    assert row_ccc["gross_contribution"] == pytest.approx(0.0)


def test_net_equals_signed_weight(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    pd.testing.assert_series_equal(
        fact["net_contribution"],
        fact["weight"],
        check_names=False,
    )


def test_gross_equals_abs_weight(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    pd.testing.assert_series_equal(
        fact["gross_contribution"],
        fact["weight"].abs(),
        check_names=False,
    )


def test_schema_columns_and_dtypes(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    assert list(fact.columns) == list(EXPOSURE_FACT_COLUMNS)
    for col in ("weight", "long_contribution", "short_contribution", "net_contribution", "gross_contribution"):
        assert fact[col].dtype == "float64", f"{col} should be float64"
    for col in ("ticker", "asset_type", "sector", "country", "rating"):
        assert pd.api.types.is_string_dtype(fact[col]), f"{col} should be string dtype"


def test_row_count_matches_input(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    assert len(fact) == 3


def test_nr_rating_preserved():
    cleaned = _make_cleaned([("AAA", "Equity", "Tech", "US", "NR", 0.3)])
    fact = _build_exposure_fact_table(cleaned)
    assert fact.loc[0, "rating"] == "NR"


def test_portfolio_totals(mixed_cleaned):
    fact = _build_exposure_fact_table(mixed_cleaned)
    assert float(fact["net_contribution"].sum()) == pytest.approx(0.4)
    assert float(fact["gross_contribution"].sum()) == pytest.approx(0.6)
    assert float(fact["short_contribution"].sum()) == pytest.approx(-0.1)
    assert float(fact["long_contribution"].sum()) == pytest.approx(0.5)


def test_calculate_exposure_output_keys(mixed_cleaned):
    metrics = calculate_exposure(mixed_cleaned)
    assert "exposure_fact_table" in metrics
    assert isinstance(metrics["exposure_fact_table"], pd.DataFrame)
