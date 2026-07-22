# Methodology

## Data choices

- Use `TotalReturnIndex_Local` for historical performance
- Use `RawPrice_Local` and `CorporateActions` for validation only
- Convert local values to USD by dividing by `FX_Local_per_USD`

## Missing data

- Do not silently forward-fill TRI or FX observations
- Report final valid observation count

## Portfolio return (Scheme B)

- Apply signed portfolio weights to USD security returns
- Non-zero weight set: `|weight| > 1e-12`
- If any non-zero-weight security return is NaN on a date, portfolio return is NaN
- Zero-weight securities are ignored and do not trigger NaN
- Weights are not renormalized on missing days

## Wealth curve

- Start from wealth = 1.0
- On valid return days: `wealth_t = wealth_{t-1} * (1 + r_t)`
- On NaN return days: wealth is NaN for that date, but compounding resumes from the last valid wealth on the next valid day

## Risk metrics

- VaR and Expected Shortfall are reported as positive loss percentages (`loss = -return`)
- VaR uses empirical quantiles with pandas linear interpolation
- ES is the mean of losses in the tail at or above the VaR threshold
- Annualized volatility uses sample standard deviation (`ddof=1`) scaled by `sqrt(252)`
- Maximum drawdown is computed from compounded wealth peaks, not summed returns

## Exposure and stress

- Preserve signed weights; reconcile net, gross, long, and short exposure
- Preserve equity ratings marked `NR`
- Use supplied equity, rate, and combined stress scenarios

### Exposure fact table

The canonical security-level exposure data source is `exposure_fact_table`, a DataFrame with 10 columns and one row per security (300 rows in production).

Column definitions:

| Column | Description |
|---|---|
| `ticker` | Security identifier |
| `asset_type` | Asset class (Equity, Bond, Loan) |
| `sector` | Industry sector |
| `country` | Country of domicile |
| `rating` | Credit rating; `NR` is preserved for unrated equities |
| `weight` | Signed portfolio weight (negative = short), rounded to 4 d.p. |
| `long_contribution` | `weight` if `weight > 0`, else `0` |
| `short_contribution` | `weight` if `weight < 0`, else `0` |
| `net_contribution` | `long_contribution + short_contribution` (equals signed weight) |
| `gross_contribution` | `abs(weight)` |

Zero-weight rows are included with all contribution columns set to zero.

Portfolio-level identities that must hold (tolerance ±0.01):

```text
Σ net_contribution   ≈ Σ weight
Σ gross_contribution ≈ Σ |weight|
Σ short_contribution ≈ Σ min(weight, 0)
```

The fact table is the canonical source for Dash interactive aggregation (Phase 2). Dimensional aggregates (e.g. net exposure by sector) are derived on demand via `groupby` rather than pre-materialised.

## Testing and production scaling

- Unit tests on pure quantitative modules with synthetic fixtures
- Production scaling notes to be added here
