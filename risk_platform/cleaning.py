"""Clean and normalize workbook data according to explicit policies."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from risk_platform.config import (
    CLEANING_LOG_PATH,
    DECIMAL_PLACES,
    FX_FLOAT_COLS,
    WEIGHT_NONZERO_THRESHOLD,
    WIDE_DATE_COL,
)
from risk_platform.models import CleanedWorkbook, CleaningLogEntry, LoadedWorkbook


def _log(log: list[CleaningLogEntry], action: str, detail: str) -> None:
    log.append(CleaningLogEntry(action=action, detail=detail))


def _deep_copy_workbook(data: LoadedWorkbook) -> LoadedWorkbook:
    return LoadedWorkbook(
        security_master=data.security_master.copy(deep=True),
        portfolio_weights=data.portfolio_weights.copy(deep=True),
        exposure_check=deepcopy(data.exposure_check),
        total_return_index_local=data.total_return_index_local.copy(deep=True),
        raw_price_local=data.raw_price_local.copy(deep=True),
        fx_local_per_usd=data.fx_local_per_usd.copy(deep=True),
        corporate_actions=data.corporate_actions.copy(deep=True),
    )


def _clean_security_master(df: pd.DataFrame, log: list[CleaningLogEntry]) -> pd.DataFrame:
    frame = df.copy()
    for col in ("ticker", "asset_type", "sector", "country", "currency", "rating", "pricing_frequency"):
        frame[col] = frame[col].astype("string").str.strip()
    frame["currency"] = frame["currency"].str.upper()
    frame = frame.sort_values("ticker").reset_index(drop=True)
    _log(log, "clean_security_master", f"normalized {len(frame)} securities; currency uppercased")
    return frame


def _clean_portfolio_weights(df: pd.DataFrame, log: list[CleaningLogEntry]) -> pd.DataFrame:
    frame = df.copy()
    frame["ticker"] = frame["ticker"].astype("string").str.strip()
    nonzero = int((frame["weight"].abs() > WEIGHT_NONZERO_THRESHOLD).sum())
    frame = frame.sort_values("ticker").reset_index(drop=True)
    _log(log, "clean_portfolio_weights", f"preserved signed weights; non-zero positions={nonzero}")
    return frame


def _sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame[WIDE_DATE_COL] = pd.to_datetime(frame[WIDE_DATE_COL])
    return frame.sort_values(WIDE_DATE_COL).reset_index(drop=True)


def _align_market_tables(
    tri: pd.DataFrame,
    raw: pd.DataFrame,
    fx: pd.DataFrame,
    log: list[CleaningLogEntry],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tri = _sort_by_date(tri)
    raw = _sort_by_date(raw)
    fx = _sort_by_date(fx)

    common_dates = sorted(set(tri[WIDE_DATE_COL]) & set(raw[WIDE_DATE_COL]) & set(fx[WIDE_DATE_COL]))
    tri = tri[tri[WIDE_DATE_COL].isin(common_dates)].reset_index(drop=True)
    raw = raw[raw[WIDE_DATE_COL].isin(common_dates)].reset_index(drop=True)
    fx = fx[fx[WIDE_DATE_COL].isin(common_dates)].reset_index(drop=True)

    for col in FX_FLOAT_COLS:
        if col in fx.columns:
            fx[col] = pd.to_numeric(fx[col], errors="coerce").astype("float64")
    if "USD" in fx.columns:
        fx["USD"] = 1.0
    fx[list(FX_FLOAT_COLS)] = fx[list(FX_FLOAT_COLS)].round(DECIMAL_PLACES)

    _log(
        log,
        "align_market_tables",
        f"aligned TRI/RawPrice/FX to {len(common_dates)} common dates; USD FX set to 1.0",
    )
    return tri, raw, fx


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
        f"computed USD returns for {len(tickers)} tickers over {len(returns)} dates",
    )
    return returns


def _log_tri_missing(tri: pd.DataFrame, log: list[CleaningLogEntry]) -> None:
    tickers = [col for col in tri.columns if col != WIDE_DATE_COL]
    missing = tri[tickers].isna()
    missing_cells = int(missing.sum().sum())
    if missing_cells == 0:
        _log(log, "tri_missing", "no missing TRI cells")
        return

    details = []
    for (row_idx, ticker), is_missing in missing.stack().items():
        if is_missing:
            details.append(f"{tri.loc[row_idx, WIDE_DATE_COL].date()} / {ticker}")
    _log(
        log,
        "tri_missing",
        f"{missing_cells} missing TRI cells preserved (not forward-filled): {', '.join(details)}",
    )


def _log_loan_convention(security_master: pd.DataFrame, log: list[CleaningLogEntry]) -> None:
    loan_count = int((security_master["asset_type"] == "Loan").sum())
    _log(
        log,
        "loan_convention",
        f"{loan_count} loans kept unchanged; weekly stale marks not smoothed",
    )


def _log_currency_coverage(
    security_master: pd.DataFrame,
    portfolio_weights: pd.DataFrame,
    fx: pd.DataFrame,
    log: list[CleaningLogEntry],
) -> None:
    nonzero = portfolio_weights[portfolio_weights["weight"].abs() > WEIGHT_NONZERO_THRESHOLD].copy()
    currencies = (
        nonzero.merge(security_master[["ticker", "currency"]], on="ticker", how="left")["currency"]
        .dropna()
        .unique()
        .tolist()
    )
    fx_cols = {col for col in fx.columns if col != WIDE_DATE_COL}
    missing = sorted(set(currencies) - fx_cols)
    if missing:
        _log(
            log,
            "currency_coverage",
            f"missing FX mapping for non-zero-weight currencies {missing}; USD returns will be NaN",
        )
    else:
        _log(log, "currency_coverage", f"FX mapping available for all non-zero-weight currencies: {sorted(currencies)}")


def _clean_corporate_actions(df: pd.DataFrame, log: list[CleaningLogEntry]) -> pd.DataFrame:
    frame = df.copy()
    frame["ticker"] = frame["ticker"].astype("string").str.strip()
    frame[WIDE_DATE_COL] = pd.to_datetime(frame[WIDE_DATE_COL])
    frame = frame.sort_values([WIDE_DATE_COL, "ticker"]).reset_index(drop=True)
    _log(log, "clean_corporate_actions", f"normalized {len(frame)} corporate action rows")
    return frame


def clean_workbook(data: LoadedWorkbook) -> tuple[CleanedWorkbook, list[CleaningLogEntry]]:
    """Return cleaned tables (security master, weights, USD returns) and a log of applied actions."""
    log: list[CleaningLogEntry] = []
    work = _deep_copy_workbook(data)
    _log(log, "copy", "created deep copy of raw workbook")

    security_master = _clean_security_master(work.security_master, log)
    portfolio_weights = _clean_portfolio_weights(work.portfolio_weights, log)
    tri, _raw, fx = _align_market_tables(
        work.total_return_index_local,
        work.raw_price_local,
        work.fx_local_per_usd,
        log,
    )
    _clean_corporate_actions(work.corporate_actions, log)
    _log_tri_missing(tri, log)
    _log_loan_convention(security_master, log)
    _log_currency_coverage(security_master, portfolio_weights, fx, log)
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
