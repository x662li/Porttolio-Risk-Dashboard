# Methology

---

## 1. Data Pipeline

Data pipeline (coded in `pipeline.py`) consists of three step, loading, validation and cleaning. First the loader loaded the data into a workbook (dictionary), then in the validation process, data integrety is checked. Finally, in cleaning, data is formatted and manipulated so that it is ready for calculations.

### Data Loading

Porfolio dataset (`candidate_data.xlsx` file) is stored in `/data`, then in `data_loader.py`, the excel file is loaded as dictionary of pandas dataframes, the required dataframes are shown below:

```python
REQUIRED_SHEETS = (
    "SecurityMaster",
    "PortfolioWeights",
    "TotalReturnIndex_Local",
    "RawPrice_Local",
    "FX_Local_per_USD",
    "CorporateActions",
)
```

then `exposure_check` is separated from `portfolio_weights` to be usded for validation.

After loading datasets, we check if all the required columns exists and then we rename them. The renaming dictionary is stored in `config.py`.

### Data Validation

After we obtain an renamed workbook of dataframes, we start the validation process. Here 5 validations are performed.

#### a. Date Alignment

This is to make sure all the dates in `TotalReturnIndex_Local`, `RawPrice_Local`, `FX_Local_per_USD` and `CorporateActions` can align with each other. This makes sure that later when we join TRI with FX, we can always find a value

#### b. Missing Values

This check goes through all the required sheets check for missing values (Null values).

#### c. Ticker Coverage

This check is to make sure all the tickers in `PortfolioWeights` exists in `SecurityMaster`, `TotalReturnIndex_Local`, and `FX_Local_per_USD`. This is crucial for performance and risk metric calculations.

#### d. Weight Exposure Reconciliation Check

During this step we take the sum of all signed weights in `PortfolioWeights` as net exposure, and then all absolute value sum as gross exposure, and sum all the negative weights are short positions, then we compare with the values in `exposure_check`. the error tolerance is set to $0.01$ in `config.py`.

#### e. Stock Split Sanity Check

During this step, two checks are performed. 

- First we checked the changes in `RawPrice_Local` for the security on the date stock split happens, we calculate the price difference ratio before and after the stock split and compare it to the ratio in `CorporateActions`. the tolerance here is set to $0.05$.

- The second check is for `TotalReturnIndex_Local`. We checked to make sure the change in cumulative return index for the security on that date is smaller than $0.01$

**Error found during validation are output as logs (validation report) and is shown on dashboard. There is no correction down at this time**.

### Data Cleaning

After we passed validation process, we start engineering the data so that we can compute meaningful metrics. the process is shown below:

#### a. Data Normalization

the dataframes we need are: `PortfolioWeights`, `SecurityMaster`, `TotalReturnIndex_Local`, and `FX_Local_per_USD`.

The formatting including:

- for all strings, we trail whitespaces to make sure join works,
- for all floats, we format to float64 and then keep 4 decimal places,
- we make sure all currencies are in upper case,
- For all time dependent files, we format date as pandas datetime and then sort by date.
- finally we sort values by tickers for time independent files and and sort by tickers.

#### b. `usd_security_returns` Generation.

In order to calculate risk metrics, we need to calculate daily return from `TotalReturnIndex_Local` (TRI). the formular is the following:

$$
    r_t = \frac{TRI_t - TRI_{t-1}}{TRI_{t-1}} = \frac{TRI_t}{TRI_{t-1}} - 1
$$

However, since securities have different base currencies, we need to adjust the return base on exhange rate to get USD based daily return.

$$
    r_t = \frac{TRI_t / FX_t}{TRI_{t-1} / FX_{t-1}} - 1
$$

Therefore, for each row, we can first join and divide by exchange rate, then calcualte the percent change. The code is shown below:

```python
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
```

Since for each daily return, we need four values: $TRI_t$, $TRI_{t-1}$, $FX_t$, $FX_{t-1}$, if any value is NaN, the daily return $r_t$ is NaN. We apply this rule because any imputation will introduce fake data thus mess up our risk metrics.

After this procedure, we obtai three tables for performance calcualtion: `usd_security_returns`,  `PortfolioWeights` and `SecurityMaster`.

---

## 2. Performance Metrics

After Data ETL process, we can start calculating performance metrics.

### Cumulative Return

First we need is a wealth curve, we do this for top 5 weighted securities and also the entire portfolio. We first calulated portfolio level daily return:

$$
    r_t^{portfolio} = \sum_{i} w_i * r_{i,t}
$$

This is a important intermediate table.

Then we compound to obtain the wealth curve.

$$
    W_t = \prod_{a=1}^{t}(1 + r_a)
$$

The code is shown below:

```python
def _compute_wealth_curve(portfolio_return: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """NaN breakpoint compound: skip invalid days but continue from last valid wealth."""
    wealth_prev = 1.0
    cumulative: list[float] = []
    wealth: list[float] = []

    for daily_return in portfolio_return["return"]:
        if pd.isna(daily_return):
            cumulative.append(np.nan)
            wealth.append(np.nan)
            continue

        wealth_t = wealth_prev * (1.0 + daily_return)
        cumulative.append(wealth_t - 1.0)
        wealth.append(wealth_t)
        wealth_prev = wealth_t

    return (
        pd.Series(cumulative, dtype="float64"),
        pd.Series(wealth, dtype="float64"),
    )
```

### VaR

For VaR calculation, we multiply portfolio daily return by $-1$ to get portfolio daily loss, then we sort the values and take $95$ and $99$ percentile. 

### Expected Shortfall

For ES calculation, we pick all the losses greater or equal to VaR95 or Var99,then we compute the mean to get ES95 and ES99. The result is rounded to 4 decimal places.

### Annulized Volatility

Here we compute the standard deviation of the entire daily return dataset with sample degree of freedom, then we times the sqaure root of number of trading days per year (252), to obtain the annulized volatility.

### Max Drawdown

We go down the cumulative return dataframe and compute drawdown for each day. The drawdown is computed by finding the previous peak up to $W_t$ (`cummax()`) and then find the distance to $W_t$, Then we take the min of drawndown series. the code is shown below:

```python
def _compute_drawdown(wealth: pd.Series) -> pd.Series:
    peak = np.nan
    drawdowns: list[float] = []

    for wealth_t in wealth:
        if pd.isna(wealth_t):
            drawdowns.append(np.nan)
            continue
        if pd.isna(peak) or wealth_t > peak:
            peak = wealth_t
        drawdowns.append(wealth_t / peak - 1.0)

    return pd.Series(drawdowns, dtype="float64")


def _compute_max_drawdown(drawdown: pd.Series) -> float:
    valid = drawdown.dropna()
    if valid.empty:
        return float("nan")
    return _round_scalar(-float(valid.min()))
```

These metrics are computed on portfolio level for year 2024, 2025 and the entire data length. the wealth curves are to be plotted in dashboard. The NaN values in wealth curve will be preserved and will be plotted as discontinuities.

---

## 3. Exposure

The display of market exposure views are designed to be an interactive feature on our dashboard. There are four filters `Asset Type`, `Sector`, `Country` and `Rating`, we can apply these filters on the dashboard and then obtain an aggregated result.

### Exposure Fact Table

In order to make the query and aggregation process smooth, an `exposure_fact_table` is build from portfolio weights:

- Copy weights from `portfolio_weights` and only keep these columns: `"ticker", "asset_type", "sector", "country", "rating", "weight"`, 
- round weights to 4 decimal places, and compute `long_contribution`, `short_contribution`, `net_contribution` and `gross_contribution` from `weight`.

The code is shown below:

```python
def _build_exposure_fact_table(cleaned: CleanedWorkbook) -> pd.DataFrame:
    """Build a security-level exposure fact table from cleaned portfolio weights."""
    weights = cleaned.portfolio_weights[
        ["ticker", "asset_type", "sector", "country", "rating", "weight"]
    ].copy()

    w = weights["weight"].fillna(0.0)
    weights["long_contribution"] = w.clip(lower=0.0).round(DECIMAL_PLACES)
    weights["short_contribution"] = w.clip(upper=0.0).round(DECIMAL_PLACES)
    weights["net_contribution"] = weights["weight"].round(DECIMAL_PLACES)
    weights["gross_contribution"] = w.abs().round(DECIMAL_PLACES)
    weights["weight"] = weights["weight"].round(DECIMAL_PLACES)

    fact = weights[list(EXPOSURE_FACT_COLUMNS)].sort_values("ticker").reset_index(drop=True)
    assert list(fact.columns) == list(EXPOSURE_FACT_COLUMNS), "Column mismatch in exposure_fact_table"
    return fact
```

An `expusre_fact_table` example is shown below:

| ticker  | asset_type | sector     | country | rating | weight  | long_contribution | short_contribution | net_contribution | gross_contribution |
|---------|------------|------------|---------|--------|---------|-------------------|--------------------|------------------|--------------------|
| Risk001 | Equity     | Technology | US      | NR     |  0.0500 |            0.0500 |             0.0000 |           0.0500 |             0.0500 |
| Risk002 | Bond       | Financials | US      | BBB    |  0.0300 |            0.0300 |             0.0000 |           0.0300 |             0.0300 |
| Risk003 | Equity     | Energy     | US      | NR     | -0.0200 |            0.0000 |            -0.0200 |          -0.0200 |             0.0200 |
| Risk004 | Loan       | Healthcare | US      | BB     |  0.0150 |            0.0150 |             0.0000 |           0.0150 |             0.0150 |

Notice the granularity is on ticker level, which allows better extensibility and easier aggregation.

Then, aggregation queries are implemented as callback functions for dashboard.

Here we display net and gross exposure together, this allows fund managers to be aware of how much each filtered market is invested besides the net exposure (net positions in the market).

---

## 4. Stress Scenarios

Stress test is applied to the current snapshot of portfolio. Since the weight is static, we can just use `PortfolioWeights` and `SecurityMaster` table to apply stress tests.

### Equity Selloff

Equity selloff only impacts equities. we apply beta of each equity to market shock to get approximated shock for each equity, the formula is shown below:

$$
    r_{i}^{stress} = \beta_i \times (-\Delta m)

$$

here $\quad \Delta m = 15\%$, and for portfolio impact, we just apply weights and add up all equities:

$$
    P^{equity} = \sum_{i \in \text{Equity}} w_i \cdot r_{i}^{stress}

$$


### Rate Shock

Rate shock only impacts bond and loans, similar to equity selloff, for each bond/loan, we apply the following formula:

$$
    r_{i}^{stress} = -D_i \cdot \Delta y + \frac{1}{2} \cdot C_i \cdot (\Delta y)^2
$$

here $\quad \Delta y = +1\%$ and $-D_i$ is the effective duration of each bond/loan because rate shock is the change in benchmark interest rate.

For portfolio level impact, we do the same thing as equity selloff:

$$
    P^{rate} = \sum_{i \in \text{Bond, Loan}} w_i \cdot r_{i}^{stress}
$$

### Combined

Since Equity selloff and Rate Shock impacts different asset types, we can just add them up to obtain the portfolio level impact.

The implementation is in `stress.py`.

---

## 5. Dashboard Design

We designed a compact one page dashboard using python Dash from Plotly. Since this is a small project, using Dash can avoid building a full scale JavaScript frontend.

The layout consists of 5 parts:

- A wealth curve plot, which displays cumulative return curve portfolio and top 5 weight asset. It can be zooms in or out for details.
- A performance metrics table, to show all risk metrics.
- A exposure view filter, here we can apply filters and compare net and gross exposure. 
- A Stres Scenario Results display
- A Data Validation and Cleaning log panel, for fund managers and engineers to check validation results.

---

## 6. Production Upgrade Design

For a full scale production system, the following aspects are expected to be taken care of.

### a. Unit and Integration Test

When implementing functions, we first need to design unit test that covers all the codes. Then a integration test or accuracy test should be performed.

For financial reporting system like this, data accuracy is number one important thing. The main source of error are from calculation logics and rounding. When building the system, we need to obtain an original source of calculation (spread sheet, old sql system, etc,) to serve as a correct source. The correct source should be able to produce any intermediate result rather than a blackbox which output the final answer only. Then we can generate or pick a list of test cases, and compare our system to the true results. 

At last, after the system is complete, we need to test all the historical data to make sure no calculation error exists.


### b. Data Management

For a full production system, we need to make sure all data sources are well managed. For risk management systems like this, we can divide data source into different databases:

#### (1) Portfolio Weights

In production environment, this table will not be static. Fund manager may adjust portfolio weights. Therefore, this table should consists of snapshots of portfolio weights labeled by dates. And maintained by DB admin. 

#### (2) Security Master

This table contains all the security related info. fields like beta and durations should all be maintained by the data team. It should be frequently updated according to current market conditions. If these parameters changes with time, we should also store these in a separate table for backtesting or stress test.

#### (3) Security Price and Return Data:

In production scenario, these data are not given like this. We can calculate it from market value, dividend reinvested and interest payment. This should be designed as a micro service itself, which is responsible for producing daily equity return

#### (4) Forex

This should be a separate service maintained by the data team. Here we maintain a table of daily forex (including spreads) and could be used by other departments across the institute (like currency exchange service).


#### (5) Stress Scenarios

For production environment, stress test is usually performed using monte carlo simulations on time series data. Not just on one snapshots. Therefore, this part is done on a iterative bases (stepwise calculation). We need to maintina a stress scenario database with economic scenarios, market scenarios and so on.

These data source mentioned above should be well maintained and stored on cloud using AWS (RDS, S3...) or locally (Sybase, Postgres)

### c. Application Design

We can integrate this risk dashboard into existing platform as a micro service. each component (marekt value, stress test, forex, reporting...) can be a individual service built using uvvicorn serviers. and communicate to each other using grpc. Then from gateway, we use fastAPI to expose restful APIs to frontend or the platform's API gateway. Then at the backend, we query database using sqlAlchemy (postgres query to RDS ...).

### d. deployment

We develop this service as a docker image, then we deploy it in kubernetes managed by AWS EKS, this allows better service availability and the ability to scale up. for some updating process (updating market values, exchange rate and portfolio weights), we can enable automatic jobs using AWS Lambda.

#### (6) User Interface

There should be some data query API designed for quant researchers to do equity research. for example, historical market value query, historical interest rate query and so on. These historical data should be well maintained.