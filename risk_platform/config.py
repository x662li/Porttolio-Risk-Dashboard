"""Constants, file paths, and configurable assumptions."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "candidate_data.xlsx"

DECIMAL_PLACES = 4
ANNUALIZATION_FACTOR = 252
VAR_CONFIDENCE_LEVELS = (0.95, 0.99)
EXPOSURE_DIMENSIONS = ("asset_type", "sector", "country", "rating")

# Validation
VALIDATION_LOG_PATH = PROJECT_ROOT / "validation_report.log"
WEIGHT_TOLERANCE = 0.01
SPLIT_RATIO_TOLERANCE = 0.05
TRI_SPLIT_MAX_ABS_RETURN = 0.10
EXPOSURE_KEYS = ("net", "gross", "short")

SECURITY_MASTER_BASE_COLS = (
    "ticker",
    "asset_type",
    "sector",
    "country",
    "currency",
    "rating",
    "pricing_frequency",
)

# Missing values in these columns are expected empty for the given asset type.
SECURITY_MASTER_SKIP_MISSING = {
    "Equity": ("effective_duration", "convexity", "spread_duration"),
    "Bond": ("equity_beta",),
    "Loan": ("equity_beta",),
}

# These columns must be present for the given asset type.
SECURITY_MASTER_REQUIRED_BY_TYPE = {
    "Equity": ("equity_beta",),
    "Bond": ("effective_duration", "convexity", "spread_duration"),
    "Loan": ("effective_duration", "convexity", "spread_duration"),
}

REQUIRED_SHEETS = (
    "SecurityMaster",
    "PortfolioWeights",
    "TotalReturnIndex_Local",
    "RawPrice_Local",
    "FX_Local_per_USD",
    "CorporateActions",
)

SECURITY_MASTER_RENAME = {
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
}

SECURITY_MASTER_STRING_COLS = (
    "ticker",
    "asset_type",
    "sector",
    "country",
    "currency",
    "rating",
    "pricing_frequency",
)

SECURITY_MASTER_FLOAT_COLS = (
    "effective_duration",
    "convexity",
    "equity_beta",
    "spread_duration",
)

PORTFOLIO_WEIGHTS_RENAME = {
    "Ticker": "ticker",
    "Weight": "weight",
    "Asset Type": "asset_type",
    "Sector": "sector",
    "Country": "country",
    "Rating": "rating",
}

PORTFOLIO_WEIGHTS_COLS = (
    "ticker",
    "weight",
    "asset_type",
    "sector",
    "country",
    "rating",
)

FX_RENAME = {
    "Date": "date",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
    "CAD": "CAD",
    "AUD": "AUD",
}

FX_FLOAT_COLS = ("USD", "EUR", "GBP", "JPY", "CAD", "AUD")

# Cleaning
WEIGHT_NONZERO_THRESHOLD = 1e-12
CLEANING_LOG_PATH = PROJECT_ROOT / "cleaning_log.log"
WIDE_DATE_COL = "date"
WEALTH_CURVE_PLOT_PATH = PROJECT_ROOT / "portfolio_wealth_curve.png"

# Metrics (computed after cleaning; consumed by dashboard)
PERFORMANCE_METRIC_KEYS = (
    "wealth_curve",
    "top5_wealth_curves",
    "performance_table",
    "annualized_volatility",
    "var_95",
    "var_99",
    "es_95",
    "es_99",
    "max_drawdown",
)

EXPOSURE_FACT_COLUMNS = (
    "ticker",
    "asset_type",
    "sector",
    "country",
    "rating",
    "weight",
    "long_contribution",
    "short_contribution",
    "net_contribution",
    "gross_contribution",
)

EXPOSURE_METRIC_KEYS = ("exposure_fact_table",)

EQUITY_SELLOFF_MARKET_RETURN = 0.15   # 15% equity market drop
RATE_SHOCK_DELTA_Y = 0.01             # 100 bps parallel rate rise

STRESS_METRIC_KEYS = (
    "equity_selloff_impact",
    "rate_shock_impact",
    "combined_scenario_impact",
)

METRIC_KEYS = PERFORMANCE_METRIC_KEYS + EXPOSURE_METRIC_KEYS + STRESS_METRIC_KEYS

CORPORATE_ACTIONS_RENAME = {
    "Effective Date": "date",
    "Ticker": "ticker",
    "Action": "action",
    "Ratio new:old": "ratio",
}
