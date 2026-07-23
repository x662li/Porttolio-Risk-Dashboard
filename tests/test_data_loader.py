"""Tests for data_loader."""

from unittest.mock import patch

import pandas as pd
import pytest

from risk_platform.config import DECIMAL_PLACES, REQUIRED_SHEETS
from risk_platform.data_loader import (
    _parse_corporate_actions,
    _parse_fx,
    _parse_portfolio_weights,
    _parse_security_master,
    _parse_wide_market_sheet,
    _round_floats,
    load_workbook,
)
from risk_platform.models import LoadedWorkbook


def test_required_sheets_defined():
    assert len(REQUIRED_SHEETS) == 6


def test_round_floats_preserves_nan():
    df = pd.DataFrame({"weight": [0.123456789, None]})
    rounded = _round_floats(df, ["weight"])
    assert rounded.loc[0, "weight"] == round(0.123456789, DECIMAL_PLACES)
    assert pd.isna(rounded.loc[1, "weight"])


def test_parse_security_master_rename_and_dtypes():
    raw = pd.DataFrame(
        {
            "Ticker": ["RISK001"],
            "Asset Type": ["Equity"],
            "Sector": ["Technology"],
            "Country": ["United States"],
            "Currency": ["USD"],
            "Rating": ["NR"],
            "Effective Duration": [None],
            "Convexity": [None],
            "Equity Beta": [0.9096531726419925],
            "Spread Duration": [None],
            "Pricing Frequency": ["Daily"],
        }
    )

    result = _parse_security_master(raw)

    assert list(result.columns) == list(raw.rename(columns={
        "Ticker": "ticker",
        "Asset Type": "asset_type",
        "Sector": "sector",
        "Country": "country",
        "Currency": "currency",
        "Rating": "rating",
        "Effective Duration": "effective_duration",
        "Convexity": "convexity",
        "Equity Beta": "equity_beta",
        "Spread Duration": "spread_duration",
        "Pricing Frequency": "pricing_frequency",
    }).columns)
    assert result.loc[0, "equity_beta"] == round(0.9096531726419925, DECIMAL_PLACES)
    assert pd.isna(result.loc[0, "effective_duration"])


def test_parse_portfolio_weights_and_exposure_check():
    raw = pd.DataFrame(
        {
            "Ticker": ["RISK001", "RISK002", "RISK003"],
            "Weight": [0.0034982433459593517, 0.0027239983119029996, -0.01],
            "Asset Type": ["Equity", "Equity", "Bond"],
            "Sector": ["Technology", "Financials", "Financials"],
            "Country": ["United States", "Germany", "United States"],
            "Rating": ["NR", "NR", "BBB"],
            "Exposure check": ["Net", "Gross", None],
            "Value": [0.9999999999999994, 1.0999999999999996, None],
        }
    )

    weights, exposure_check = _parse_portfolio_weights(raw)

    assert list(weights.columns) == [
        "ticker",
        "weight",
        "asset_type",
        "sector",
        "country",
        "rating",
    ]
    assert len(weights) == 3
    assert weights.loc[0, "weight"] == round(0.0034982433459593517, DECIMAL_PLACES)
    assert exposure_check["net"] == round(0.9999999999999994, DECIMAL_PLACES)
    assert exposure_check["gross"] == round(1.0999999999999996, DECIMAL_PLACES)


def test_parse_wide_market_sheet():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-03", "2024-01-02"],
            "RISK001": [101.23456789, 100.0],
            "RISK002": [200.987654321, 200.0],
        }
    )

    result = _parse_wide_market_sheet(raw)

    assert "date" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result.loc[0, "date"] == pd.Timestamp("2024-01-02")
    assert result.loc[0, "RISK001"] == round(100.0, DECIMAL_PLACES)
    assert result.loc[1, "RISK002"] == round(200.987654321, DECIMAL_PLACES)


def test_parse_fx_lowercase_columns():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-02"],
            "USD": [1.0],
            "EUR": [0.906510003762522],
            "GBP": [0.788005255683879],
            "JPY": [140.30621946753962],
            "CAD": [1.3385144096771124],
            "AUD": [1.4984076746812132],
        }
    )

    result = _parse_fx(raw)

    assert list(result.columns) == ["date", "usd", "eur", "gbp", "jpy", "cad", "aud"]
    assert result.loc[0, "eur"] == round(0.906510003762522, DECIMAL_PLACES)


def test_parse_corporate_actions_ratio_int():
    raw = pd.DataFrame(
        {
            "Effective Date": ["2024-08-15"],
            "Ticker": ["RISK012"],
            "Action": ["Stock split"],
            "Ratio new:old": [2],
        }
    )

    result = _parse_corporate_actions(raw)

    assert result.loc[0, "ratio"] == 2
    assert result["ratio"].dtype == "Int64"


@patch("risk_platform.data_loader.pd.ExcelFile")
@patch("risk_platform.data_loader.pd.read_excel")
def test_load_workbook_integration(mock_read_excel, mock_excel_file, tmp_path):
    workbook_path = tmp_path / "candidate_data.xlsx"
    workbook_path.touch()

    mock_excel_file.return_value.__enter__.return_value = object()
    mock_read_excel.side_effect = lambda xls, sheet_name: {
        "SecurityMaster": pd.DataFrame(
            {
                "Ticker": ["RISK001"],
                "Asset Type": ["Equity"],
                "Sector": ["Technology"],
                "Country": ["United States"],
                "Currency": ["USD"],
                "Rating": ["NR"],
                "Effective Duration": [None],
                "Convexity": [None],
                "Equity Beta": [1.0],
                "Spread Duration": [None],
                "Pricing Frequency": ["Daily"],
            }
        ),
        "PortfolioWeights": pd.DataFrame(
            {
                "Ticker": ["RISK001"],
                "Weight": [1.0],
                "Asset Type": ["Equity"],
                "Sector": ["Technology"],
                "Country": ["United States"],
                "Rating": ["NR"],
                "Exposure check": ["Net"],
                "Value": [1.0],
            }
        ),
        "TotalReturnIndex_Local": pd.DataFrame(
            {"Date": ["2024-01-02"], "RISK001": [100.0]}
        ),
        "RawPrice_Local": pd.DataFrame(
            {"Date": ["2024-01-02"], "RISK001": [100.0]}
        ),
        "FX_Local_per_USD": pd.DataFrame(
            {
                "Date": ["2024-01-02"],
                "USD": [1.0],
                "EUR": [0.9],
                "GBP": [0.8],
                "JPY": [140.0],
                "CAD": [1.3],
                "AUD": [1.5],
            }
        ),
        "CorporateActions": pd.DataFrame(
            {
                "Effective Date": ["2024-08-15"],
                "Ticker": ["RISK012"],
                "Action": ["Stock split"],
                "Ratio new:old": [2],
            }
        ),
    }[sheet_name]

    result = load_workbook(workbook_path)

    assert isinstance(result, LoadedWorkbook)
    assert "ticker" in result.security_master.columns
    assert "net" in result.exposure_check
    assert "date" in result.total_return_index_local.columns
    assert "usd" in result.fx_local_per_usd.columns


@pytest.mark.integration
def test_load_real_workbook():
    result = load_workbook()

    assert len(result.security_master) == 300
    assert len(result.portfolio_weights) == 300
    assert {"net", "gross"}.issubset(result.exposure_check.keys())
    assert result.total_return_index_local.shape[1] == 301
    assert result.fx_local_per_usd.shape[1] == 7
