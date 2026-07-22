# Mini Portfolio Risk Platform

混合资产组合风险平台 take-home 项目（Dash 版）。

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run dashboard

```bash
python app.py
```

启动时会一次性 load → validate → clean → compute，然后用 Dash 展示结果。

## Smoke test (load + validation)

```bash
python test.py
python test.py --debug      # include full missing-value details
python test.py --info       # also print DataFrame.info()
```

Validation output is printed and saved to `validation_report.log`.

## Validation parameters (`risk_platform/config.py`)

| Parameter | Default | Description |
|---|---|---|
| `WEIGHT_TOLERANCE` | `0.01` | Pass if \|computed - expected\| < 0.01 for net/gross/short |
| `SPLIT_RATIO_TOLERANCE` | `0.05` | Pass if raw implied split ratio within 5% of stated ratio |
| `TRI_SPLIT_MAX_ABS_RETURN` | `0.10` | Pass if TRI daily return on split date is within 10% |
| `VALIDATION_LOG_PATH` | `validation_report.log` | Validation report output file |

Security master missing-value checks are asset-type aware:

- **Equity:** `effective_duration`, `convexity`, `spread_duration` expected empty
- **Bond / Loan:** `equity_beta` expected empty
- Other required fields are still checked normally

## Tests

```bash
pytest
```

## Project layout

```text
app.py                 # entry point
risk_platform/         # quantitative engine (Dash-independent)
  data_loader.py       # load raw workbook
  validation.py        # one-shot validation
  cleaning.py          # clean + USD security returns
  performance.py       # performance metrics
  exposure.py          # exposure metrics
  stress.py            # stress scenario metrics
  pipeline.py          # orchestration; merges metrics dict
dashboard/             # Dash layout, figures, callbacks
data/                  # candidate_data.xlsx, candidate_brief.docx
tests/                 # unit tests
methodology.md         # methodology note
```

Computed dashboard metrics are stored in ``PipelineResult.metrics`` as
``{metric_name: DataFrame | Series | scalar}``.

See [methodology.md](methodology.md) for assumptions and conventions.
