"""End-to-end quantitative workflow orchestration."""

from __future__ import annotations

from pathlib import Path

from risk_platform.cleaning import clean_workbook
from risk_platform.data_loader import load_workbook
from risk_platform.exposure import calculate_exposure
from risk_platform.models import Metrics, PipelineResult
from risk_platform.performance import calculate_performance
from risk_platform.stress import calculate_stress
from risk_platform.validation import run_validation


def _merge_metrics(*metric_groups: Metrics) -> Metrics:
    merged: Metrics = {}
    for group in metric_groups:
        merged.update(group)
    return merged


def run_pipeline(path: Path | str | None = None) -> PipelineResult:
    """Load, validate, clean, compute metrics, and return one complete result object."""
    loaded = load_workbook(path)
    raw_validation = run_validation(loaded)
    cleaned, cleaning_log = clean_workbook(loaded)
    cleaned_validation = None

    metrics = _merge_metrics(
        calculate_performance(cleaned),
        calculate_exposure(cleaned),
        calculate_stress(cleaned),
    )

    return PipelineResult(
        loaded=loaded,
        cleaned=cleaned,
        raw_validation=raw_validation,
        cleaned_validation=cleaned_validation,
        cleaning_log=cleaning_log,
        metrics=metrics,
    )
