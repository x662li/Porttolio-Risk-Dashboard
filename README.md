# Mini Portfolio Risk Platform

A take-home project for portfolio risk analytics: load and validate Excel workbook data, compute performance / exposure / stress metrics in Python, and present results in an interactive **Dash** dashboard.

## Technology

| Layer | Stack |
|---|---|
| Language | **Python 3.11+** |
| Data & computation | **pandas**, **numpy**, **openpyxl** |
| Dashboard | **Dash** + **Plotly** |
| Testing | **pytest** |

The quantitative engine lives under `risk_platform/` and is independent of Dash. `dashboard/` handles layout, charts, and lightweight filtering callbacks only.

---

## Prerequisites

- **Python 3.11 or newer** (tested with 3.11)
- `pip` and `venv`

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd take_home
```

### 2. Create the data directory and add the workbook

The app expects the input file at:

```text
data/candidate_data.xlsx
```

Create the folder and place the Excel file inside it:

```bash
mkdir -p data
# Copy your workbook into data/
cp /path/to/candidate_data.xlsx data/candidate_data.xlsx
```

> **Note:** The `data/` folder may be git-ignored. You must provide `candidate_data.xlsx` locally before running the app.

### 3. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows**

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Run the dashboard

From the project root (with the virtual environment activated):

```bash
python app.py
```

On startup the app runs the full pipeline once:

`load → validate → clean → compute metrics → launch Dash`

When the server is ready, open your browser at:

**http://127.0.0.1:8050/**

The dashboard includes:

- Portfolio wealth curve (with optional top-5 securities overlay)
- Performance metrics table (2024 / 2025 / Total)
- Interactive exposure filters (asset type, sector, country, rating)
- Stress test results
- Validation & cleaning log (Info / Debug tabs)

To stop the server, press `Ctrl+C` in the terminal.

---

## Smoke test (CLI, no dashboard)

Run the pipeline from the command line and print key outputs:

```bash
python test.py
python test.py --debug   # full validation details
```

Validation output is also written to `validation_report.log`.

---

## Run tests

```bash
pytest
```

---

## Project layout

```text
app.py                 # Entry point: run pipeline + start Dash
risk_platform/         # Quantitative engine (Dash-independent)
  data_loader.py       # Load raw workbook
  validation.py        # One-shot validation
  cleaning.py          # Clean data + USD security returns
  performance.py       # Performance metrics
  exposure.py          # Exposure fact table
  stress.py            # Stress scenario impacts
  pipeline.py          # Orchestration; merges metrics dict
dashboard/             # Dash layout, figures, callbacks
data/                  # candidate_data.xlsx (not committed)
tests/                 # Unit tests
methodology.md         # Methodology and assumptions
```

Computed metrics are stored in `PipelineResult.metrics` as `{metric_name: DataFrame | Series | scalar}`.

See [methodology.md](methodology.md) for calculation conventions and design choices.
