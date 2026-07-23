"""Validate raw workbook data and emit a validation report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from risk_platform.config import (
    EXPOSURE_KEYS,
    SECURITY_MASTER_BASE_COLS,
    SECURITY_MASTER_REQUIRED_BY_TYPE,
    SECURITY_MASTER_SKIP_MISSING,
    SPLIT_RATIO_TOLERANCE,
    TRI_SPLIT_MAX_ABS_RETURN,
    VALIDATION_LOG_PATH,
    WEIGHT_TOLERANCE,
)
from risk_platform.models import LoadedWorkbook, ValidationIssue, ValidationReport

SECTION_DATE_ALIGNMENT = "1. Date Alignment"
SECTION_MISSING_VALUES = "2. Missing Values"
SECTION_TICKER_COVERAGE = "3. Ticker Coverage"
SECTION_WEIGHT_EXPOSURE = "4. Weight & Exposure Reconciliation"
SECTION_SPLIT_SANITY = "5. Stock Split Sanity Check"

def _add_issue(
    report: ValidationReport,
    section: str,
    severity: str,
    code: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> None:
    report.issues.append(
        ValidationIssue(
            section=section,
            severity=severity,
            code=code,
            message=message,
            context=context or {},
        )
    )


def _wide_value_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if col != "date"]


def _missing_wide_summary(df: pd.DataFrame, name: str) -> dict[str, Any]:
    value_cols = _wide_value_columns(df)
    values = df[value_cols]
    missing_mask = values.isna()
    missing_cells = int(missing_mask.sum().sum())
    total_cells = int(values.size)

    by_column = missing_mask.sum()
    columns_with_missing = int((by_column > 0).sum())
    by_date = missing_mask.any(axis=1)
    dates_with_missing = int(by_date.sum())

    details: list[dict[str, str]] = []
    if missing_cells:
        stacked = missing_mask.stack()
        for (row_idx, col), is_missing in stacked.items():
            if is_missing:
                details.append(
                    {
                        "date": str(df.loc[row_idx, "date"]),
                        "column": str(col),
                    }
                )

    return {
        "dataset": name,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round(100 * missing_cells / total_cells, 4) if total_cells else 0.0,
        "columns_with_missing": columns_with_missing,
        "dates_with_missing": dates_with_missing,
        "details": details,
    }


def _tabular_missing_summary(df: pd.DataFrame, name: str) -> dict[str, Any]:
    id_col = "ticker" if "ticker" in df.columns else ("date" if "date" in df.columns else None)
    columns: dict[str, dict[str, int | str]] = {}
    details: list[dict[str, Any]] = []
    missing_cells = 0

    for col in df.columns:
        if col not in df.columns:
            columns[col] = {"missing_rows": len(df), "status": "missing_column"}
            missing_cells += len(df)
            continue

        missing_mask = df[col].isna()
        missing_rows = int(missing_mask.sum())
        columns[col] = {"missing_rows": missing_rows}
        missing_cells += missing_rows
        if missing_rows:
            if id_col is not None:
                keys = df.loc[missing_mask, id_col].tolist()
                details.extend(
                    {"column": col, id_col: str(key)} for key in keys
                )
            else:
                details.extend(
                    {"column": col, "row_index": int(idx)}
                    for idx in df.index[missing_mask]
                )

    return {
        "dataset": name,
        "missing_cells": missing_cells,
        "columns_with_missing": sum(1 for c in columns.values() if c.get("missing_rows", 0) > 0),
        "columns": columns,
        "details": details,
    }


def _report_dataset_missing(
    report: ValidationReport,
    name: str,
    summary: dict[str, Any],
    *,
    debug: bool,
    message_fn,
) -> None:
    missing_cells = summary.get("missing_cells", 0)
    if missing_cells == 0:
        _add_issue(
            report,
            SECTION_MISSING_VALUES,
            "info",
            f"{name}_missing_ok",
            f"{name}: no missing values.",
            {k: summary[k] for k in summary if k != "details"},
        )
        return

    context = summary if debug else {k: summary[k] for k in summary if k != "details"}
    _add_issue(
        report,
        SECTION_MISSING_VALUES,
        "warning",
        f"{name}_missing_summary",
        message_fn(summary),
        context,
    )


def _check_date_alignment(data: LoadedWorkbook, report: ValidationReport, *, debug: bool) -> None:
    datasets = {
        "total_return_index_local": data.total_return_index_local,
        "raw_price_local": data.raw_price_local,
        "fx_local_per_usd": data.fx_local_per_usd,
    }

    date_sets = {name: set(df["date"]) for name, df in datasets.items()}
    all_equal = len(set(map(frozenset, date_sets.values()))) == 1

    if all_equal:
        count = len(next(iter(date_sets.values())))
        _add_issue(
            report,
            SECTION_DATE_ALIGNMENT,
            "info",
            "date_alignment_ok",
            f"TRI, RawPrice, and FX dates aligned ({count} days).",
            {"date_count": count},
        )
        return

    context = {
        name: {
            "count": len(dates),
            "only_here_count": len(
                dates - set.union(*(s for n, s in date_sets.items() if n != name))
            ),
        }
        for name, dates in date_sets.items()
    }
    if debug:
        for name, dates in date_sets.items():
            others = set.union(*(s for n, s in date_sets.items() if n != name))
            context[name]["only_here_dates"] = [str(d) for d in sorted(dates - others)]

    _add_issue(
        report,
        SECTION_DATE_ALIGNMENT,
        "warning",
        "date_alignment_mismatch",
        "TRI, RawPrice, and FX date sets differ.",
        context,
    )


def _check_security_master_missing(
    data: LoadedWorkbook, report: ValidationReport, *, debug: bool
) -> None:
    sm = data.security_master
    details: list[dict[str, Any]] = []
    unexpected_populated: list[dict[str, Any]] = []
    missing_count = 0

    for asset_type, group in sm.groupby("asset_type", dropna=False):
        asset_type_str = str(asset_type)
        skip_cols = set(SECURITY_MASTER_SKIP_MISSING.get(asset_type_str, ()))
        required_cols = SECURITY_MASTER_REQUIRED_BY_TYPE.get(asset_type_str, ())

        for col in SECURITY_MASTER_BASE_COLS:
            missing_mask = group[col].isna()
            count = int(missing_mask.sum())
            if count:
                missing_count += count
                if debug:
                    for ticker in group.loc[missing_mask, "ticker"]:
                        details.append(
                            {"asset_type": asset_type_str, "ticker": str(ticker), "column": col}
                        )

        for col in required_cols:
            missing_mask = group[col].isna()
            count = int(missing_mask.sum())
            if count:
                missing_count += count
                if debug:
                    for ticker in group.loc[missing_mask, "ticker"]:
                        details.append(
                            {"asset_type": asset_type_str, "ticker": str(ticker), "column": col}
                        )

        for col in skip_cols:
            populated_mask = group[col].notna()
            if populated_mask.any():
                for ticker in group.loc[populated_mask, "ticker"]:
                    unexpected_populated.append(
                        {"asset_type": asset_type_str, "ticker": str(ticker), "column": col}
                    )

    context: dict[str, Any] = {
        "missing_count": missing_count,
        "unexpected_populated_count": len(unexpected_populated),
    }
    if debug:
        context["details"] = details
        context["unexpected_populated"] = unexpected_populated

    if missing_count == 0 and not unexpected_populated:
        _add_issue(
            report,
            SECTION_MISSING_VALUES,
            "info",
            "security_master_missing_ok",
            "security_master: 0 unexpected missing values after asset-type filters.",
            context,
        )
        return

    if missing_count:
        _add_issue(
            report,
            SECTION_MISSING_VALUES,
            "warning",
            "security_master_unexpected_missing",
            f"security_master: {missing_count} unexpected missing values after asset-type filters.",
            context,
        )

    if unexpected_populated:
        _add_issue(
            report,
            SECTION_MISSING_VALUES,
            "warning",
            "security_master_unexpected_populated",
            (
                "security_master: "
                f"{len(unexpected_populated)} values populated in asset-type optional fields."
            ),
            context,
        )


def _check_missing_values(data: LoadedWorkbook, report: ValidationReport, *, debug: bool) -> None:
    _check_security_master_missing(data, report, debug=debug)

    tabular_datasets = {
        "portfolio_weights": data.portfolio_weights,
        "corporate_actions": data.corporate_actions,
    }
    for name, df in tabular_datasets.items():
        summary = _tabular_missing_summary(df, name)
        _report_dataset_missing(
            report,
            name,
            summary,
            debug=debug,
            message_fn=lambda s, n=name: (
                f"{n}: {s['missing_cells']} missing cells, "
                f"{s['columns_with_missing']} columns affected."
            ),
        )

    wide_datasets = {
        "total_return_index_local": data.total_return_index_local,
        "raw_price_local": data.raw_price_local,
        "fx_local_per_usd": data.fx_local_per_usd,
    }
    for name, df in wide_datasets.items():
        summary = _missing_wide_summary(df, name)
        _report_dataset_missing(
            report,
            name,
            summary,
            debug=debug,
            message_fn=lambda s, n=name: (
                f"{n}: {s['missing_cells']} missing cells "
                f"({s['missing_pct']}%), "
                f"{s['dates_with_missing']} dates affected, "
                f"{s['columns_with_missing']} columns affected."
            ),
        )


def _check_weight_exposure(data: LoadedWorkbook, report: ValidationReport) -> None:
    weights = data.portfolio_weights["weight"]
    computed = {
        "net": float(weights.sum()),
        "gross": float(weights.abs().sum()),
        "short": float(weights[weights < 0].sum()) if (weights < 0).any() else 0.0,
    }

    if not (weights < 0).any():
        _add_issue(
            report,
            SECTION_WEIGHT_EXPOSURE,
            "warning",
            "signed_weights_missing",
            "No negative weights found; signed short exposure may be missing.",
            {"negative_count": 0},
        )
    else:
        _add_issue(
            report,
            SECTION_WEIGHT_EXPOSURE,
            "info",
            "signed_weights_present",
            f"Signed weights preserved ({int((weights < 0).sum())} short positions).",
            {"negative_count": int((weights < 0).sum())},
        )

    for key in EXPOSURE_KEYS:
        expected = float(data.exposure_check.get(key, computed[key]))
        actual = computed[key]
        diff = abs(actual - expected)
        passed = diff < WEIGHT_TOLERANCE
        _add_issue(
            report,
            SECTION_WEIGHT_EXPOSURE,
            "info" if passed else "warning",
            f"exposure_{key}_{'ok' if passed else 'mismatch'}",
            (
                f"Exposure {key}: computed={actual:.4f}, expected={expected:.4f}, "
                f"diff={diff:.4f} (tolerance={WEIGHT_TOLERANCE})."
            ),
            {"computed": actual, "expected": expected, "diff": diff, "passed": passed},
        )


def _price_on_date(df: pd.DataFrame, ticker: str, date: pd.Timestamp) -> tuple[int | None, float | None]:
    matches = df.index[df["date"] == date].tolist()
    if not matches:
        return None, None
    row_idx = matches[0]
    value = df.loc[row_idx, ticker]
    return row_idx, None if pd.isna(value) else float(value)


def _check_split_sanity(data: LoadedWorkbook, report: ValidationReport) -> None:
    raw = data.raw_price_local
    tri = data.total_return_index_local

    for _, action in data.corporate_actions.iterrows():
        ticker = action["ticker"]
        split_date = action["date"]
        ratio = float(action["ratio"])
        context: dict[str, Any] = {
            "ticker": str(ticker),
            "date": str(split_date),
            "ratio": ratio,
        }

        raw_idx, raw_after = _price_on_date(raw, ticker, split_date)
        tri_idx, tri_after = _price_on_date(tri, ticker, split_date)

        if raw_idx is None or raw_idx == 0:
            _add_issue(
                report,
                SECTION_SPLIT_SANITY,
                "warning",
                "split_no_prior_date",
                f"Split check skipped for {ticker} on {split_date.date()}: no prior raw price row.",
                context,
            )
            continue

        raw_before = raw.loc[raw_idx - 1, ticker]
        tri_before = tri.loc[tri_idx - 1, ticker] if tri_idx is not None else pd.NA

        if pd.isna(raw_before) or raw_after is None:
            _add_issue(
                report,
                SECTION_SPLIT_SANITY,
                "warning",
                "split_missing_price",
                f"Split check skipped for {ticker} on {split_date.date()}: missing raw prices.",
                context,
            )
            continue

        implied_ratio = float(raw_before) / raw_after
        ratio_error = abs(implied_ratio - ratio) / ratio
        raw_pass = ratio_error <= SPLIT_RATIO_TOLERANCE
        context.update(
            {
                "raw_before": float(raw_before),
                "raw_after": raw_after,
                "implied_ratio": round(implied_ratio, 4),
                "ratio_error_pct": round(100 * ratio_error, 4),
            }
        )
        _add_issue(
            report,
            SECTION_SPLIT_SANITY,
            "info" if raw_pass else "warning",
            f"split_raw_{'ok' if raw_pass else 'mismatch'}",
            (
                f"{ticker} split raw ratio check: implied={implied_ratio:.4f}, "
                f"stated={ratio:.4f}, error={100 * ratio_error:.2f}%."
            ),
            context,
        )

        if tri_idx is None or pd.isna(tri_before) or tri_after is None:
            _add_issue(
                report,
                SECTION_SPLIT_SANITY,
                "warning",
                "split_tri_missing_price",
                f"Split TRI check skipped for {ticker} on {split_date.date()}: missing TRI prices.",
                context,
            )
            continue

        tri_return = float(tri_after) / float(tri_before) - 1
        tri_pass = abs(tri_return) <= TRI_SPLIT_MAX_ABS_RETURN
        context["tri_return_pct"] = round(100 * tri_return, 4)
        _add_issue(
            report,
            SECTION_SPLIT_SANITY,
            "info" if tri_pass else "warning",
            f"split_tri_{'ok' if tri_pass else 'discontinuity'}",
            (
                f"{ticker} split TRI check: daily return={100 * tri_return:.2f}% "
                f"(limit={100 * TRI_SPLIT_MAX_ABS_RETURN:.0f}%)."
            ),
            context,
        )


def _check_ticker_coverage(data: LoadedWorkbook, report: ValidationReport, *, debug: bool) -> None:
    """Check that every portfolio_weights ticker exists in security_master, TRI, and raw_price."""
    weight_tickers = set(data.portfolio_weights["ticker"].dropna().astype(str))
    sm_tickers = set(data.security_master["ticker"].dropna().astype(str))
    tri_tickers = set(data.total_return_index_local.columns) - {"date"}
    raw_tickers = set(data.raw_price_local.columns) - {"date"}

    missing_in_sm = sorted(weight_tickers - sm_tickers)
    missing_in_tri = sorted(weight_tickers - tri_tickers)
    missing_in_raw = sorted(weight_tickers - raw_tickers)

    if not missing_in_sm and not missing_in_tri and not missing_in_raw:
        _add_issue(
            report,
            SECTION_TICKER_COVERAGE,
            "info",
            "portfolio_weights_ticker_coverage_ok",
            f"All {len(weight_tickers)} portfolio_weights tickers found in security_master, TRI, and raw_price.",
            {"ticker_count": len(weight_tickers)},
        )
        return

    context: dict[str, Any] = {
        "missing_in_security_master_count": len(missing_in_sm),
        "missing_in_tri_count": len(missing_in_tri),
        "missing_in_raw_price_count": len(missing_in_raw),
    }
    if debug:
        context["missing_in_security_master"] = missing_in_sm
        context["missing_in_tri"] = missing_in_tri
        context["missing_in_raw_price"] = missing_in_raw

    parts = []
    if missing_in_sm:
        parts.append(f"{len(missing_in_sm)} not in security_master")
    if missing_in_tri:
        parts.append(f"{len(missing_in_tri)} not in TRI")
    if missing_in_raw:
        parts.append(f"{len(missing_in_raw)} not in raw_price")

    _add_issue(
        report,
        SECTION_TICKER_COVERAGE,
        "warning",
        "portfolio_weights_ticker_coverage_mismatch",
        f"portfolio_weights ticker coverage: {'; '.join(parts)}.",
        context,
    )


def validate_raw(data: LoadedWorkbook, *, debug: bool = False) -> ValidationReport:
    """Run raw-input validation checks after loading."""
    report = ValidationReport()
    _check_date_alignment(data, report, debug=debug)
    _check_missing_values(data, report, debug=debug)
    _check_ticker_coverage(data, report, debug=debug)
    _check_weight_exposure(data, report)
    _check_split_sanity(data, report)
    return report


def validate_cleaned(data: LoadedWorkbook) -> ValidationReport:
    """Reserved for post-cleaning validation; not used in current workflow."""
    raise NotImplementedError("Post-cleaning validation is not implemented.")


def _section_status(issues: list[ValidationIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if "error" in severities:
        return "FAIL"
    if "warning" in severities:
        return "WARN"
    return "PASS"


def _format_context_lines(context: dict[str, Any], *, debug: bool, indent: str = "    ") -> list[str]:
    if not context:
        return []

    lines: list[str] = []
    for key, value in context.items():
        if key == "details" and not debug:
            continue
        if isinstance(value, dict):
            lines.append(f"{indent}{key}:")
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, dict):
                    lines.append(f"{indent}  {sub_key}: {sub_value}")
                elif isinstance(sub_value, list) and sub_value and isinstance(sub_value[0], dict):
                    lines.append(f"{indent}  {sub_key}: {len(sub_value)} item(s)")
                    if debug:
                        for item in sub_value:
                            lines.append(f"{indent}    - {item}")
                else:
                    lines.append(f"{indent}  {sub_key}: {sub_value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{indent}{key}: []")
            elif debug or all(not isinstance(item, dict) for item in value):
                lines.append(f"{indent}{key}:")
                for item in value:
                    lines.append(f"{indent}  - {item}")
            else:
                lines.append(f"{indent}{key}: {len(value)} item(s)")
        else:
            lines.append(f"{indent}{key}: {value}")
    return lines


def _report_lines(report: ValidationReport, *, debug: bool = False) -> list[str]:
    lines = [
        "=" * 72,
        "VALIDATION REPORT",
        "=" * 72,
        "",
    ]

    sections: list[str] = []
    seen: set[str] = set()
    for issue in report.issues:
        if issue.section not in seen:
            sections.append(issue.section)
            seen.add(issue.section)

    for section in sections:
        section_issues = [issue for issue in report.issues if issue.section == section]
        status = _section_status(section_issues)
        info_count = sum(1 for issue in section_issues if issue.severity == "info")
        warn_count = sum(1 for issue in section_issues if issue.severity == "warning")
        error_count = sum(1 for issue in section_issues if issue.severity == "error")

        lines.extend(
            [
                "-" * 72,
                f"{section}",
                f"RESULT: {status}  |  info: {info_count}, warnings: {warn_count}, errors: {error_count}",
                "-" * 72,
                "",
            ]
        )

        for issue in section_issues:
            lines.append(f"  [{issue.severity.upper()}] {issue.code}")
            lines.append(f"    {issue.message}")
            context_lines = _format_context_lines(issue.context, debug=debug, indent="      ")
            if context_lines:
                lines.append("    details:")
                lines.extend(context_lines)
            lines.append("")

    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in report.issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1

    lines.extend(
        [
            "=" * 72,
            "OVERALL SUMMARY",
            f"  errors:   {counts.get('error', 0)}",
            f"  warnings: {counts.get('warning', 0)}",
            f"  info:     {counts.get('info', 0)}",
            "=" * 72,
        ]
    )
    return lines


def print_report(report: ValidationReport, *, debug: bool = False) -> None:
    """Print validation report to stdout."""
    for line in _report_lines(report, debug=debug):
        print(line)


def write_report(
    report: ValidationReport,
    path: Path | str | None = None,
    *,
    debug: bool = False,
) -> Path:
    """Write validation report to a log file."""
    log_path = Path(path) if path is not None else VALIDATION_LOG_PATH
    log_path.write_text("\n".join(_report_lines(report, debug=debug)) + "\n", encoding="utf-8")
    return log_path


def run_validation(data: LoadedWorkbook, *, debug: bool = False) -> ValidationReport:
    """Validate, print, and write the report log."""
    report = validate_raw(data, debug=debug)
    print_report(report, debug=debug)
    log_path = write_report(report, debug=debug)
    print(f"Validation log written to: {log_path}")
    return report
