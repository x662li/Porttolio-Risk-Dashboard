# Methodology

> Replace this file with your own methodology. Below are **formatting samples** only.

---

## 1. Title

Use one `#` for the document title (shown above as **Methodology**).

Use `##` for major sections, e.g. Data Choices, Performance, Exposure, Stress Tests.

Use `###` for subsections within a topic.

---

## 2. Subtitle / Section intro

After a section heading, add a short paragraph to set context before bullets or formulas.

### Example subsection

This section describes how portfolio daily returns are computed from security-level USD returns and signed weights.

---

## 3. Bullet points

Use `-` for unordered lists. Keep one idea per bullet; use nested bullets for details.

- Main assumption or data source
- Key rule or convention
- Edge-case handling
  - Sub-point: what happens when data is missing
  - Sub-point: what is excluded from the calculation

**Bold** for emphasis; `` `inline code` `` for column names, parameters, or file paths.

---

## 4. LaTeX formulas

GitHub and most Markdown viewers render math with `$...$` (inline) or `$$...$$` (block).

Inline example: portfolio return on day $t$ is $r_{p,t} = \sum_i w_i \, r_{i,t}$.

Block example — annualized volatility:

$$
\sigma_{\text{annual}} = \sigma_{\text{daily}} \sqrt{252}
$$

Block example — sample variance ($n$ observations, $ddof = 1$):

$$
s^2 = \frac{1}{n - 1} \sum_{t=1}^{n} (r_t - \bar{r})^2
$$

Block example — rate shock (bond/loan):

$$
\Delta P/P \approx -D \,\Delta y + \tfrac{1}{2} C \,(\Delta y)^2
$$

Tips:
- Use `\text{...}` for words inside formulas: `\sigma_{\text{daily}}`
- Subscripts: `r_{i,t}`; fractions: `\frac{a}{b}`; sums: `\sum_{i=1}^{n}`

---

## 5. Code blocks

Use fenced blocks with a language tag for syntax highlighting, or `text` for pseudo-code / formulas.

**Python (implementation reference):**

```python
portfolio_return = (security_returns * weights).sum(axis=1)
annualized_vol = daily_returns.std(ddof=1) * (252 ** 0.5)
```

**Plain text (identities or pseudo-code):**

```text
net_exposure   = sum(net_contribution)
gross_exposure = sum(gross_contribution)
```

**Shell (commands, if relevant):**

```bash
python app.py
```

---

## 6. Optional: tables

| Column | Description |
|--------|-------------|
| `ticker` | Security identifier |
| `weight` | Signed portfolio weight |

---

## 7. Suggested outline for your write-up

Delete everything above and fill in sections such as:

1. **Data & cleaning** — sources, FX conversion, missing data policy
2. **Portfolio return** — weighting scheme, NaN rules
3. **Performance** — wealth curve, VaR/ES, volatility, drawdown
4. **Exposure** — signed weights, fact table, aggregation
5. **Stress tests** — equity selloff, rate shock, combined scenario
6. **Assumptions & limitations** — what you chose and why

---

*End of formatting samples.*
