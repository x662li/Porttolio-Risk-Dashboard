"""Smoke test: load, validate, clean, compute performance and exposure, and save wealth curve plot."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd

from risk_platform.cleaning import clean_workbook, print_cleaning_log, write_cleaning_log
from risk_platform.config import EXPOSURE_DIMENSIONS, PERFORMANCE_METRIC_KEYS, WEALTH_CURVE_PLOT_PATH
from risk_platform.data_loader import load_workbook
from risk_platform.exposure import calculate_exposure
from risk_platform.performance import calculate_performance
from risk_platform.stress import calculate_stress
from risk_platform.validation import run_validation


def _print_performance_scalars(metrics: dict) -> None:
    print("=" * 72)
    print("Performance scalars")
    print("=" * 72)
    for key in PERFORMANCE_METRIC_KEYS:
        if key == "wealth_curve":
            continue
        value = metrics[key]
        print(f"{key}: {value}")
    print()


def _plot_wealth_curve(metrics: dict, output_path: Path) -> None:
    wealth_curve = metrics["wealth_curve"]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(wealth_curve["date"], wealth_curve["wealth"], linewidth=1.2)
    ax.set_title("Portfolio Wealth Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Wealth")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _print_exposure_by_dimension(fact: pd.DataFrame) -> None:
    for dim in EXPOSURE_DIMENSIONS:
        agg = (
            fact.groupby(dim, sort=True)[["net_contribution", "gross_contribution"]]
            .sum()
            .round(4)
        )
        print("=" * 72)
        print(f"Exposure by {dim}")
        print("=" * 72)
        print(agg.to_string())
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load workbook, validate, clean, compute performance.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print full validation details.",
    )
    parser.add_argument(
        "--plot-path",
        type=Path,
        default=WEALTH_CURVE_PLOT_PATH,
        help="Output path for wealth curve PNG.",
    )
    args = parser.parse_args()

    print("Loading workbook...")
    loaded = load_workbook()
    print("Running validation...")
    run_validation(loaded, debug=args.debug)

    print("\nRunning cleaning...")
    cleaned, cleaning_log = clean_workbook(loaded)
    print_cleaning_log(cleaning_log)
    log_path = write_cleaning_log(cleaning_log)
    print(f"Cleaning log written to: {log_path}\n")

    print("Calculating performance metrics...")
    metrics = calculate_performance(cleaned)
    _print_performance_scalars(metrics)

    print("=" * 72)
    print("wealth_curve.info()")
    print("=" * 72)
    metrics["wealth_curve"].info()
    print()

    print(f"Saving wealth curve plot to: {args.plot_path}")
    _plot_wealth_curve(metrics, args.plot_path)

    print("\nCalculating exposure metrics...")
    exposure_metrics = calculate_exposure(cleaned)
    fact = exposure_metrics["exposure_fact_table"]
    print("=" * 72)
    print("exposure_fact_table.head(10)")
    print("=" * 72)
    print(fact.head(10).to_string(index=False))
    print()
    print("=" * 72)
    print("exposure_fact_table.info()")
    print("=" * 72)
    fact.info()
    print()
    print("Portfolio totals:")
    print(f"  net   = {fact['net_contribution'].sum():.4f}")
    print(f"  gross = {fact['gross_contribution'].sum():.4f}")
    print(f"  short = {fact['short_contribution'].sum():.4f}")
    print(f"  long  = {fact['long_contribution'].sum():.4f}")

    _print_exposure_by_dimension(fact)

    print("\nCalculating stress scenarios...")
    stress_metrics = calculate_stress(cleaned)
    print("=" * 72)
    print("Stress scenario results")
    print("=" * 72)
    print(f"  equity_selloff_impact    (beta × −15% × weight): {stress_metrics['equity_selloff_impact']:+.4f}")
    print(f"  rate_shock_impact        (−dur×Δy + ½×cvx×Δy²): {stress_metrics['rate_shock_impact']:+.4f}")
    print(f"  combined_scenario_impact (equity + rate):         {stress_metrics['combined_scenario_impact']:+.4f}")
    print()

    print("Done.")


if __name__ == "__main__":
    main()
