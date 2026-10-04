# Checkout A/B test analysis

An end-to-end product analytics project: simulate an e-commerce checkout experiment, model it
with dbt in DuckDB, test it properly in Python, and present the answer in a notebook, a Streamlit
dashboard and a Power BI report.

## Business question

We redesigned the checkout page. **Does the redesign make more visitors complete their purchase,
and is the gain big enough to ship?**

- **Primary metric:** conversion rate (share of checkout visitors who order)
- **Secondary metric:** revenue per visitor
- **Decision rule (set before launch):** ship if the conversion lift is statistically significant
  (p < 0.05, 95% CI above zero), at least +2% relative, and the traffic split passes the SRM check.

## Stack

| Layer | Tool |
|---|---|
| Data | Python (NumPy), seeded simulation of 50,000 users |
| Warehouse | DuckDB |
| Modelling | dbt (dbt-duckdb): staging, star schema, mart, 40 data tests |
| Statistics | pandas, SciPy, statsmodels |
| Write-up | Jupyter notebook for a non-technical manager |
| Dashboards | Streamlit (local), Power BI (stakeholder report) |
| Quality | pytest, Makefile |

## How to run

```bash
make setup   # install dependencies (Python 3.10+; use a virtualenv if you like)
make all     # simulate -> dbt run + test -> analysis -> Power BI export -> notebook -> pytest
make app     # open the Streamlit dashboard at http://localhost:8501
```

Individual steps: `make data`, `make dbt`, `make analyze`, `make export`, `make notebook`, `make test`.

## Key results

| Metric | Control | Treatment | Relative lift | 95% CI (relative) | p-value | Decision |
|---|---|---|---|---|---|---|
| Conversion rate | 9.89% | 11.02% | **+11.4%** | +6.0% to +16.8% | < 0.0001 | Ship |
| Revenue per user | $7.52 | $8.15 | +8.4% | +2.1% to +14.8% | 0.009 | Ship |
| Conversion rate (CUPED) | | | +10.2% | +5.0% to +15.4% | 0.0001 | Ship |

- **Sample size:** 23,128 users per variant were needed to detect an 8% lift with 80% power;
  the test had ~25,000 per variant.
- **SRM check:** 49.94% / 50.06% split, p = 0.80. Passed.
- **Peeking simulation:** in A/A tests, checking once gives a 5.0% false positive rate; checking
  daily for 28 days gives 27.6%.
- The data was simulated with a true +8% lift. The observed +11.4% is higher, but the true value
  sits inside the 95% interval, which is what the interval promises.

## Recommendation

**Ship the new checkout.** It lifts conversion by about **+11%** (plausible range +6% to +17%).
At current traffic (~53,600 checkout visitors a month) that is roughly **600 extra orders and
$34,000 extra revenue per month**, with a 95% range of $8,300 to $59,700. Even the low end is
positive. Average order size did not change, so the gain comes from more people buying.
Keep monitoring conversion for a few weeks after rollout to confirm the effect holds once the
novelty wears off.

## Power BI report

A two-page report built on the exported star schema:

- **Executive summary:** decision card, lift with confidence interval, KPI cards per variant,
  SRM status.
- **Deep dive:** cumulative conversion over time, results by device, revenue distribution.

Everything needed is in [`powerbi/`](powerbi/): the data (`data/*.csv`, refreshed by
`make export`), [`measures.dax`](powerbi/measures.dax),
[`model.md`](powerbi/model.md) (tables, relationships, hidden columns),
[`build_guide.md`](powerbi/build_guide.md) (step-by-step build) and a colour
[`theme.json`](powerbi/theme.json).

> **Screenshot placeholder:** after building the report, save page 1 as
> `powerbi/screenshots/executive_summary.png` and replace this note with
> `![Power BI executive summary](powerbi/screenshots/executive_summary.png)`.

## Mistakes this analysis avoids

**Peeking.** Checking results every day and stopping at the first "significant" result turns a 5%
false positive rate into roughly 28% (see the simulation in `src/analysis.py` and the notebook).
The test length was fixed in advance from a power calculation, and the result was read once.

**Ignoring sample ratio mismatch.** If a 50/50 test does not come out close to 50/50, assignment
or logging is broken, and the results are biased in unknown ways. A chi-square SRM check runs
before anything else; if it fails, every metric is labelled "Invalid - SRM" and the
recommendation says not to act.

**Confusing statistical and practical significance.** With enough traffic, a +0.3% lift can be
"significant" and still not worth the engineering and maintenance cost. The decision rule
requires both a significant result and a lift of at least +2%, agreed before the test. Results
are always reported with a confidence interval and translated into orders and revenue, not only
a p-value.

Also: CUPED (adjusting for each user's pre-test orders) is reported alongside the raw result as a
sensitivity check. It uses only pre-experiment data, so it cannot be biased by the treatment.

## Project layout

```
data/raw/            simulated experiment (checkout_experiment.csv)
dbt_project/         staging model, star schema, mart, schema + singular tests
src/
  simulate.py        seeded data simulation
  analysis.py        sample size, SRM, z-test, Welch t-test, CUPED, peeking sim, decisions
  export.py          CSV export for Power BI
notebooks/           analysis.ipynb (executed, narrated for a manager)
app/app.py           Streamlit dashboard
tests/               statistics unit tests, pipeline integration tests, dashboard smoke test
powerbi/             data/, measures.dax, model.md, build_guide.md, theme.json
```

### Data model

```
                 dim_variant ──1:*── fct_experiment_results
                      │1
                      │*
dim_date ──1:*── fct_user_outcomes ──*:1── dim_device

fct_test_results   (written by src/analysis.py, one row per metric)
```

`fct_test_results` columns: metric, control_value, treatment_value, absolute_lift, relative_lift,
ci_low, ci_high (95% CI of the absolute lift), p_value, srm_passed, decision.
