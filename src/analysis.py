"""Statistical analysis of the checkout experiment.

Reads the dbt star schema from DuckDB, runs the pre-registered checks and tests,
and writes one row per metric to the `fct_test_results` table.

Run with: python -m src.analysis
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from src import config

RESULT_COLUMNS = [
    "metric", "control_value", "treatment_value", "absolute_lift", "relative_lift",
    "ci_low", "ci_high", "p_value", "srm_passed", "decision",
]


# --------------------------------------------------------------------------- data

def load_user_outcomes(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per user with readable variant, device and date columns."""
    return con.sql("""
        select f.user_id, v.variant_name as variant, d.device_name as device, dt.date as assignment_date,
               dt.experiment_day, f.pre_period_orders, f.converted, cast(f.revenue as double) as revenue
        from fct_user_outcomes f
        join dim_variant v using (variant_key)
        join dim_device d using (device_key)
        join dim_date dt on f.assignment_date_key = dt.date_key
    """).df()


# ------------------------------------------------------------------- design checks

def required_sample_size(baseline_rate: float, mde_relative: float = config.MDE_RELATIVE,
                         alpha: float = config.ALPHA, power: float = config.POWER) -> int:
    """Users needed per variant to detect `mde_relative` lift on a conversion rate (two-sided)."""
    effect = proportion_effectsize(baseline_rate * (1 + mde_relative), baseline_rate)
    n = NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power, ratio=1.0,
                                     alternative="two-sided")
    return int(np.ceil(n))


def srm_check(n_control: int, n_treatment: int, expected_control_share: float = 0.5,
              threshold: float = config.SRM_THRESHOLD) -> dict:
    """Chi-square goodness-of-fit test that the observed split matches the planned split.

    A p-value below `threshold` means randomisation or logging is broken and the
    results should not be trusted, however good they look.
    """
    total = n_control + n_treatment
    expected = [total * expected_control_share, total * (1 - expected_control_share)]
    chi2, p_value = stats.chisquare([n_control, n_treatment], f_exp=expected)
    return {"chi2": float(chi2), "p_value": float(p_value), "passed": bool(p_value >= threshold),
            "control_share": n_control / total}


# ----------------------------------------------------------------------- the tests

def two_proportion_ztest(conv_control: int, n_control: int, conv_treatment: int, n_treatment: int,
                         alpha: float = config.ALPHA) -> dict:
    """Two-sided z-test for a difference in conversion rates.

    The p-value uses the pooled standard error (the null says both rates are equal);
    the confidence interval for the difference uses the unpooled standard error.
    """
    p_c, p_t = conv_control / n_control, conv_treatment / n_treatment
    diff = p_t - p_c

    p_pool = (conv_control + conv_treatment) / (n_control + n_treatment)
    se_pooled = np.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_treatment))
    z = diff / se_pooled
    p_value = 2 * stats.norm.sf(abs(z))

    se_unpooled = np.sqrt(p_c * (1 - p_c) / n_control + p_t * (1 - p_t) / n_treatment)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    return {"control": p_c, "treatment": p_t, "diff": diff, "z": float(z), "p_value": float(p_value),
            "ci_low": diff - z_crit * se_unpooled, "ci_high": diff + z_crit * se_unpooled}


def welch_ttest(control: np.ndarray, treatment: np.ndarray, alpha: float = config.ALPHA) -> dict:
    """Welch's t-test (unequal variances) for a difference in means, with a Welch CI."""
    control, treatment = np.asarray(control, float), np.asarray(treatment, float)
    diff = treatment.mean() - control.mean()
    var_c, var_t = control.var(ddof=1) / len(control), treatment.var(ddof=1) / len(treatment)
    se = np.sqrt(var_c + var_t)
    dof = (var_c + var_t) ** 2 / (var_c ** 2 / (len(control) - 1) + var_t ** 2 / (len(treatment) - 1))
    t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
    t_crit = stats.t.ppf(1 - alpha / 2, dof)
    return {"control": control.mean(), "treatment": treatment.mean(), "diff": diff, "t": float(t_stat),
            "p_value": float(p_value), "ci_low": diff - t_crit * se, "ci_high": diff + t_crit * se,
            "se": se}


def cuped_adjust(metric: np.ndarray, covariate: np.ndarray) -> tuple[np.ndarray, float]:
    """CUPED: remove the part of the metric that pre-experiment behaviour already predicts.

    theta is estimated on both arms pooled. The covariate was measured before
    assignment, so it cannot be affected by the treatment and the adjustment keeps
    the estimate unbiased while shrinking its variance by roughly corr^2.
    Returns the adjusted metric and theta.
    """
    metric, covariate = np.asarray(metric, float), np.asarray(covariate, float)
    theta = np.cov(metric, covariate, ddof=1)[0, 1] / covariate.var(ddof=1)
    return metric - theta * (covariate - covariate.mean()), float(theta)


def cuped_ttest(df: pd.DataFrame, metric: str, covariate: str = "pre_period_orders",
                alpha: float = config.ALPHA) -> dict:
    """Welch t-test on the CUPED-adjusted metric, plus how much variance it removed."""
    adjusted, theta = cuped_adjust(df[metric], df[covariate])
    is_treatment = (df["variant"] == "treatment").to_numpy()
    result = welch_ttest(adjusted[~is_treatment], adjusted[is_treatment], alpha)
    raw = welch_ttest(df.loc[~is_treatment, metric], df.loc[is_treatment, metric], alpha)
    result["theta"] = theta
    result["variance_reduction"] = 1 - (result["se"] / raw["se"]) ** 2
    return result


# ------------------------------------------------------------------------ peeking

def simulate_peeking(n_sims: int = 5000, users_per_arm: int = 25_000, baseline_rate: float = 0.10,
                     n_looks: int = config.EXPERIMENT_DAYS, alpha: float = config.ALPHA,
                     seed: int = config.SEED) -> dict:
    """Simulate A/A tests (no real difference) and check them daily.

    Each simulated experiment enrols users evenly over `n_looks` days. After every
    day we run the two-proportion z-test on the data so far. Returns:
      fpr_fixed_horizon: share of experiments significant at the final look only
      fpr_peeking:       share significant on at least one of the daily looks
      fpr_by_look:       cumulative share that had "won" by each day
    """
    rng = np.random.default_rng(seed)
    per_look = users_per_arm // n_looks
    n = per_look * np.arange(1, n_looks + 1)

    conv_a = rng.binomial(per_look, baseline_rate, size=(n_sims, n_looks)).cumsum(axis=1)
    conv_b = rng.binomial(per_look, baseline_rate, size=(n_sims, n_looks)).cumsum(axis=1)

    p_a, p_b = conv_a / n, conv_b / n
    p_pool = (conv_a + conv_b) / (2 * n)
    se = np.sqrt(p_pool * (1 - p_pool) * 2 / n)
    z = np.divide(p_b - p_a, se, out=np.zeros_like(se), where=se > 0)
    significant = np.abs(z) > stats.norm.ppf(1 - alpha / 2)

    ever_significant = np.maximum.accumulate(significant, axis=1)
    return {
        "fpr_fixed_horizon": float(significant[:, -1].mean()),
        "fpr_peeking": float(ever_significant[:, -1].mean()),
        "fpr_by_look": ever_significant.mean(axis=0),
        "n_sims": n_sims,
        "n_looks": n_looks,
    }


# ----------------------------------------------------------------------- decision

def decide(p_value: float, ci_low: float, ci_high: float, relative_lift: float, srm_passed: bool,
           alpha: float = config.ALPHA, min_practical_lift: float = config.MIN_PRACTICAL_LIFT) -> str:
    """Turn a test result into a decision using rules fixed before the test ran."""
    if not srm_passed:
        return "Invalid - SRM"
    if p_value >= alpha:
        return "Inconclusive"
    if ci_high < 0:
        return "Don't ship"
    if ci_low > 0 and relative_lift >= min_practical_lift:
        return "Ship"
    return "Not practically significant"


def _result_row(metric: str, test: dict, srm_passed: bool) -> dict:
    relative = test["diff"] / test["control"]
    return {
        "metric": metric,
        "control_value": test["control"],
        "treatment_value": test["treatment"],
        "absolute_lift": test["diff"],
        "relative_lift": relative,
        "ci_low": test["ci_low"],
        "ci_high": test["ci_high"],
        "p_value": test["p_value"],
        "srm_passed": srm_passed,
        "decision": decide(test["p_value"], test["ci_low"], test["ci_high"], relative, srm_passed),
    }


def build_results_table(df: pd.DataFrame) -> pd.DataFrame:
    """Run every test and return the fct_test_results table.

    conversion_rate is the pre-registered primary metric; the others are
    secondary (revenue) or sensitivity checks (CUPED).
    """
    control, treatment = df[df["variant"] == "control"], df[df["variant"] == "treatment"]
    srm = srm_check(len(control), len(treatment))

    conversion = two_proportion_ztest(control["converted"].sum(), len(control),
                                      treatment["converted"].sum(), len(treatment))
    revenue = welch_ttest(control["revenue"], treatment["revenue"])

    rows = [
        _result_row("conversion_rate", conversion, srm["passed"]),
        _result_row("revenue_per_user", revenue, srm["passed"]),
        _result_row("conversion_rate_cuped", cuped_ttest(df, "converted"), srm["passed"]),
        _result_row("revenue_per_user_cuped", cuped_ttest(df, "revenue"), srm["passed"]),
    ]
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


# ------------------------------------------------------------ business translation

def monthly_users(df: pd.DataFrame) -> float:
    """Checkout users per 30 days, assuming the test ran on all checkout traffic."""
    days = df["assignment_date"].nunique()
    return len(df) / days * 30


def business_impact(results: pd.DataFrame, users_per_month: float) -> dict:
    """Extra orders and revenue per month if every user got the treatment, with 95% ranges."""
    conv = results.set_index("metric").loc["conversion_rate"]
    rev = results.set_index("metric").loc["revenue_per_user"]
    return {
        "users_per_month": users_per_month,
        "extra_orders": users_per_month * conv["absolute_lift"],
        "extra_orders_low": users_per_month * conv["ci_low"],
        "extra_orders_high": users_per_month * conv["ci_high"],
        "extra_revenue": users_per_month * rev["absolute_lift"],
        "extra_revenue_low": users_per_month * rev["ci_low"],
        "extra_revenue_high": users_per_month * rev["ci_high"],
    }


def recommendation(results: pd.DataFrame, impact: dict) -> str:
    """Plain-English recommendation driven by the primary metric."""
    conv = results.set_index("metric").loc["conversion_rate"]
    rev = results.set_index("metric").loc["revenue_per_user"]
    rel_low, rel_high = conv["ci_low"] / conv["control_value"], conv["ci_high"] / conv["control_value"]
    decision = conv["decision"]

    if decision == "Ship":
        revenue_note = (
            f"about ${impact['extra_revenue']:,.0f} more revenue per month "
            f"(likely between ${impact['extra_revenue_low']:,.0f} and ${impact['extra_revenue_high']:,.0f})"
        )
        if rev["p_value"] >= config.ALPHA:
            revenue_note += ", although the revenue gain on its own is not yet statistically certain"
        return (
            f"Ship the new checkout. It lifts conversion by {conv['relative_lift']:+.1%} "
            f"(95% range {rel_low:+.1%} to {rel_high:+.1%}), which means roughly "
            f"{impact['extra_orders']:,.0f} extra orders and {revenue_note}."
        )
    if decision == "Invalid - SRM":
        return ("Do not act on these results. The traffic split between variants is off, so the data "
                "collection is broken. Fix the assignment and rerun the test.")
    if decision == "Don't ship":
        return (f"Don't ship. The new checkout lowers conversion by {abs(conv['relative_lift']):.1%} "
                f"(95% range {rel_low:+.1%} to {rel_high:+.1%}).")
    if decision == "Not practically significant":
        return (f"Don't ship on this evidence. The lift of {conv['relative_lift']:+.1%} is real but smaller "
                f"than the {config.MIN_PRACTICAL_LIFT:.0%} we agreed is worth the change.")
    return (f"No decision yet. The observed lift of {conv['relative_lift']:+.1%} could be noise "
            f"(95% range {rel_low:+.1%} to {rel_high:+.1%}). Keep the current checkout.")


# --------------------------------------------------------------------------- main

def main() -> None:
    con = duckdb.connect(str(config.WAREHOUSE))
    df = load_user_outcomes(con)

    control = df[df["variant"] == "control"]
    baseline = control["converted"].mean()
    n_needed = required_sample_size(baseline)
    srm = srm_check(len(control), len(df) - len(control))
    peeking = simulate_peeking()

    results = build_results_table(df)
    con.register("results_df", results)
    con.execute(f"create or replace table {config.RESULTS_TABLE} as select * from results_df")
    con.close()

    impact = business_impact(results, monthly_users(df))

    print(f"Sample size: need {n_needed:,} users per variant for a {config.MDE_RELATIVE:.0%} relative lift "
          f"on a {baseline:.2%} baseline; have {len(control):,} / {len(df) - len(control):,}")
    print(f"SRM check: control share {srm['control_share']:.4f}, p = {srm['p_value']:.3f} -> "
          f"{'passed' if srm['passed'] else 'FAILED'}")
    print(f"Peeking: A/A false positive rate {peeking['fpr_fixed_horizon']:.1%} with one look, "
          f"{peeking['fpr_peeking']:.1%} when checked daily for {peeking['n_looks']} days")
    print()
    print(results.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    print(recommendation(results, impact))
    print(f"\nWrote {len(results)} rows to {config.RESULTS_TABLE} in {config.WAREHOUSE.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
