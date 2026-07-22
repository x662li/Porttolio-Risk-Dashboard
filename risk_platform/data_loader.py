"""Read candidate_data.xlsx into structured workbook objects."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_platform.config import (
    CORPORATE_ACTIONS_RENAME,
    DATA_PATH,
    DECIMAL_PLACES,
    FX_FLOAT_COLS,
    FX_RENAME,
    PORTFOLIO_WEIGHTS_COLS,
    PORTFOLIO_WEIGHTS_RENAME,
    REQUIRED_SHEETS,
    SECURITY_MASTER_FLOAT_COLS,
    SECURITY_MASTER_RENAME,
    SECURITY_MASTER_STRING_COLS,
)
from risk_platform.models import LoadedWorkbook


def _round_floats(df: pd.DataFrame, cols: list[str] | tuple[str, ...]) -> pd.DataFrame:
    result = df.copy()
    present = [col for col in cols if col in result.columns]
    if present:
        result[present] = result[present].round(DECIMAL_PLACES)
    return result


def _round_value(value: float) -> float:
    return round(float(value), DECIMAL_PLACES)


def _parse_security_master(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.rename(columns=SECURITY_MASTER_RENAME)
    missing = set(SECURITY_MASTER_RENAME.values()) - set(frame.columns)
    if missing:
        raise ValueError(f"SecurityMaster missing columns: {sorted(missing)}")

    for col in SECURITY_MASTER_STRING_COLS:
        frame[col] = frame[col].astype("string")

    for col in SECURITY_MASTER_FLOAT_COLS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    return _round_floats(frame, SECURITY_MASTER_FLOAT_COLS)


def _parse_exposure_check(df: pd.DataFrame) -> dict[str, float]:
    if "Exposure check" not in df.columns or "Value" not in df.columns:
        return {}

    checks = df[["Exposure check", "Value"]].dropna(subset=["Exposure check", "Value"])
    return {
        str(row["Exposure check"]).strip().lower(): _round_value(row["Value"])
        for _, row in checks.iterrows()
    }


def _parse_portfolio_weights(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    exposure_check = _parse_exposure_check(df)
    frame = df.rename(columns=PORTFOLIO_WEIGHTS_RENAME)
    missing = set(PORTFOLIO_WEIGHTS_COLS) - set(frame.columns)
    if missing:
        raise ValueError(f"PortfolioWeights missing columns: {sorted(missing)}")

    frame = frame[list(PORTFOLIO_WEIGHTS_COLS)].copy()
    frame = frame.dropna(subset=["ticker"])
    frame["ticker"] = frame["ticker"].astype("string")

    for col in ("asset_type", "sector", "country", "rating"):
        frame[col] = frame[col].astype("string")

    frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
    frame = _round_floats(frame, ("weight",))

    return frame.reset_index(drop=True), exposure_check


def _parse_wide_market_sheet(df: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in df.columns:
        raise ValueError("Wide market sheet missing Date column")

    frame = df.rename(columns={"Date": "date"}).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    ticker_cols = [col for col in frame.columns if col != "date"]

    for col in ticker_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = _round_floats(frame, ticker_cols)
    return frame.sort_values("date").reset_index(drop=True)


def _parse_fx(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.rename(columns=FX_RENAME)
    missing = set(FX_RENAME.values()) - set(frame.columns)
    if missing:
        raise ValueError(f"FX_Local_per_USD missing columns: {sorted(missing)}")

    frame["date"] = pd.to_datetime(frame["date"])
    for col in FX_FLOAT_COLS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = _round_floats(frame, FX_FLOAT_COLS)
    return frame.sort_values("date").reset_index(drop=True)


def _parse_corporate_actions(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.rename(columns=CORPORATE_ACTIONS_RENAME)
    missing = set(CORPORATE_ACTIONS_RENAME.values()) - set(frame.columns)
    if missing:
        raise ValueError(f"CorporateActions missing columns: {sorted(missing)}")

    frame["date"] = pd.to_datetime(frame["date"])
    frame["ticker"] = frame["ticker"].astype("string")
    frame["action"] = frame["action"].astype("string")
    frame["ratio"] = pd.to_numeric(frame["ratio"], errors="coerce").astype("Int64")
    return frame.reset_index(drop=True)


def load_workbook(path: Path | str | None = None) -> LoadedWorkbook:
    """Load required workbook sheets into a LoadedWorkbook."""
    workbook_path = Path(path) if path is not None else DATA_PATH
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    with pd.ExcelFile(workbook_path, engine="openpyxl") as workbook:
        sheets = {
            name: pd.read_excel(workbook, sheet_name=name)
            for name in REQUIRED_SHEETS
        }

    portfolio_weights, exposure_check = _parse_portfolio_weights(
        sheets["PortfolioWeights"]
    )

    return LoadedWorkbook(
        security_master=_parse_security_master(sheets["SecurityMaster"]),
        portfolio_weights=portfolio_weights,
        exposure_check=exposure_check,
        total_return_index_local=_parse_wide_market_sheet(
            sheets["TotalReturnIndex_Local"]
        ),
        raw_price_local=_parse_wide_market_sheet(sheets["RawPrice_Local"]),
        fx_local_per_usd=_parse_fx(sheets["FX_Local_per_USD"]),
        corporate_actions=_parse_corporate_actions(sheets["CorporateActions"]),
    )
