"""Dataclasses and typed containers shared across the project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

MetricValue = pd.DataFrame | pd.Series | float | int | None
Metrics = dict[str, MetricValue]


@dataclass
class LoadedWorkbook:
    """Structured workbook data after loading (pre-cleaning)."""

    security_master: pd.DataFrame
    portfolio_weights: pd.DataFrame
    exposure_check: dict[str, float]
    total_return_index_local: pd.DataFrame
    raw_price_local: pd.DataFrame
    fx_local_per_usd: pd.DataFrame
    corporate_actions: pd.DataFrame


@dataclass
class ValidationIssue:
    section: str
    severity: str
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class CleaningLogEntry:
    action: str
    detail: str


@dataclass
class CleanedWorkbook:
    """Normalized portfolio inputs produced by cleaning."""

    security_master: pd.DataFrame
    portfolio_weights: pd.DataFrame
    usd_security_returns: pd.DataFrame


@dataclass
class PipelineResult:
    """Complete output from the quantitative pipeline."""

    loaded: LoadedWorkbook | None = None
    cleaned: CleanedWorkbook | None = None
    raw_validation: ValidationReport | None = None
    cleaned_validation: ValidationReport | None = None
    cleaning_log: list[CleaningLogEntry] = field(default_factory=list)
    metrics: Metrics = field(default_factory=dict)
