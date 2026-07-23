"""Clean and normalize workbook data for downstream computation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_platform.config import (
    CLEANING_LOG_PATH,
    DECIMAL_PLACES,
    FX_FLOAT_COLS,
    SECURITY_MASTER_FLOAT_COLS,
    SECURITY_MASTER_STRING_COLS,
    WIDE_DATE_COL,
)
from risk_platform.models import CleanedWorkbook, CleaningLogEntry, LoadedWorkbook


def _log(log: list[CleaningLogEntry], action: str, detail: str) -> None:
    log.append(CleaningLogEntry(action=action, detail=detail))


def _normalize_security_master(
    df: pd.DataFrame, log: list[CleaningLogEntry]
) -> pd.DataFrame:
    frame = df.copy()
    for col in SECURITY_MASTER_STRING_COLS:
        if col in frame.columns:
            frame[col] = frame[col].astype("string").str.strip()
    if "currency" in frame.columns:
        frame["currency"] = frame["currency"].str.upper()
    for col in SECURITY_MASTER_FLOAT_COLS:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float64").round(DECIMAL_PLACES)
    frame = frame.sort_values("ticker").reset_index(drop=True)
    _log(log, "normalize_security_master", f"{len(frame)} rows")
    return frame


def _normalize_portfolio_weights(
    df: pd.DataFrame, log: list[CleaningLogEntry]
) -> pd.DataFrame:
    frame = df.copy()
    for col in ("ticker", "asset_type", "sector", "country", "rating"):
        if col in frame.columns:
            frame[col] = frame[col].astype("string").str.strip()
    if "weight" in frame.columns:
        frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce").astype("float64").round(DECIMAL_PLACES)
    frame = frame.sort_values("ticker").reset_index(drop=True)
    _log(log, "normalize_portfolio_weights", f"{len(frame)} rows")
    return frame


def _normalize_fx(df: pd.DataFrame, log: list[CleaningLogEntry]) -> pd.DataFrame:
    frame = df.copy()
    frame[WIDE_DATE_COL] = pd.to_datetime(frame[WIDE_DATE_COL])
    for col in FX_FLOAT_COLS:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float64").round(DECIMAL_PLACES)
    if "USD" in frame.columns:
        frame["USD"] = 1.0
    frame = frame.sort_values(WIDE_DATE_COL).reset_index(drop=True)
    _log(log, "normalize_fx", f"{len(frame)} dates")
    return frame


def _normalize_tri(df: pd.DataFrame, log: list[CleaningLogEntry]) -> pd.DataFrame:
    frame = df.copy()
    frame[WIDE_DATE_COL] = pd.to_datetime(frame[WIDE_DATE_COL])
    value_cols = [col for col in frame.columns if col != WIDE_DATE_COL]
    for col in value_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float64").round(DECIMAL_PLACES)
    frame = frame.sort_values(WIDE_DATE_COL).reset_index(drop=True)
    _log(log, "normalize_tri", f"{len(frame)} dates x {len(value_cols)} tickers")
    return frame


def _calculate_usd_security_returns(
    tri: pd.DataFrame,
    fx: pd.DataFrame,
    security_master: pd.DataFrame,
    log: list[CleaningLogEntry],
) -> pd.DataFrame:
    """Calculate daily USD returns from local TRI and FX. Preserves NaN; no forward-fill."""
    currencies = security_master.set_index("ticker")["currency"]
    tickers = [col for col in tri.columns if col != WIDE_DATE_COL]
    fx_cols = {col for col in fx.columns if col != WIDE_DATE_COL}
    fx_by_date = fx.set_index(WIDE_DATE_COL)

    return_cols: dict[str, pd.Series] = {}
    for ticker in tickers:
        currency = currencies.get(ticker)
        if pd.isna(currency) or currency not in fx_cols:
            return_cols[ticker] = pd.Series(pd.NA, index=tri.index, dtype="Float64")
            continue
        mapped_fx = fx_by_date[currency].reset_index(drop=True)
        usd_tri = tri[ticker] / mapped_fx
        return_cols[ticker] = usd_tri.pct_change(fill_method=None).round(DECIMAL_PLACES)

    returns = pd.concat(return_cols, axis=1)
    returns.insert(0, WIDE_DATE_COL, tri[WIDE_DATE_COL].values)
    _log(
        log,
        "calculate_usd_security_returns",
        f"{len(returns)} dates x {len(tickers)} tickers",
    )
    return returns


def clean_workbook(data: LoadedWorkbook) -> tuple[CleanedWorkbook, list[CleaningLogEntry]]:
    """Normalize dtypes and compute USD security returns."""
    log: list[CleaningLogEntry] = []

    security_master = _normalize_security_master(data.security_master, log)
    portfolio_weights = _normalize_portfolio_weights(data.portfolio_weights, log)
    fx = _normalize_fx(data.fx_local_per_usd, log)
    tri = _normalize_tri(data.total_return_index_local, log)
    usd_security_returns = _calculate_usd_security_returns(tri, fx, security_master, log)

    return (
        CleanedWorkbook(
            security_master=security_master,
            portfolio_weights=portfolio_weights,
            usd_security_returns=usd_security_returns,
        ),
        log,
    )


def print_cleaning_log(log: list[CleaningLogEntry]) -> None:
    print("=" * 72)
    print("CLEANING LOG")
    print("=" * 72)
    for entry in log:
        print(f"- {entry.action}: {entry.detail}")
    print()


def write_cleaning_log(log: list[CleaningLogEntry], path: Path | str | None = None) -> Path:
    log_path = Path(path) if path is not None else CLEANING_LOG_PATH
    lines = [f"{entry.action}: {entry.detail}" for entry in log]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path
