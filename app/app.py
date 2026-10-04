"""Streamlit dashboard for the checkout experiment. Run with: make app"""
import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.analysis import business_impact, load_user_outcomes, monthly_users, recommendation, srm_check  # noqa: E402

VARIANT_COLORS = {"control": "#2a78d6", "treatment": "#eb6834"}
INK, MUTED_INK, GRID = "#0b0b0b", "#52514e", "#e4e3df"
METRIC_LABELS = {
    "conversion_rate": "Conversion rate",
    "revenue_per_user": "Revenue per user",
    "conversion_rate_cuped": "Conversion rate (CUPED)",
    "revenue_per_user_cuped": "Revenue per user (CUPED)",
}

st.set_page_config(page_title="Checkout A/B test", layout="wide")


@st.cache_data
def load():
    with duckdb.connect(str(config.WAREHOUSE), read_only=True) as con:
        variants = con.sql("select * from fct_experiment_results order by variant_key").df()
        results = con.sql(f"select * from {config.RESULTS_TABLE}").df()
        users = load_user_outcomes(con)
    return variants, results, users


if not config.WAREHOUSE.exists():
    st.error("No warehouse found. Run `make all` first.")
    st.stop()

variants, results, users = load()
primary = results.set_index("metric").loc["conversion_rate"]
impact = business_impact(results, monthly_users(users))
control, treatment = variants.set_index("variant_name").loc["control"], variants.set_index("variant_name").loc["treatment"]
srm = srm_check(int(control["users"]), int(treatment["users"]))

st.title("Checkout redesign A/B test")
st.caption(f"{len(users):,} users, {users['assignment_date'].min():%b %d} to {users['assignment_date'].max():%b %d, %Y}. "
           "Primary metric: conversion rate. Decision rules fixed before launch.")

# --- recommendation and SRM ------------------------------------------------------
left, right = st.columns([3, 1])
with left:
    box = st.success if primary["decision"] == "Ship" else st.warning
    # Escape dollar signs so Streamlit markdown does not render them as LaTeX.
    box(f"**Recommendation: {primary['decision']}.** " + recommendation(results, impact).replace("$", r"\$"))
with right:
    if srm["passed"]:
        st.success(f"**SRM check passed**  \nSplit {srm['control_share']:.2%} / {1 - srm['control_share']:.2%}, "
                   f"p = {srm['p_value']:.2f}")
    else:
        st.error(f"**SRM detected**  \nSplit {srm['control_share']:.2%} / {1 - srm['control_share']:.2%}, "
                 f"p = {srm['p_value']:.4f}. Do not trust the results.")

# --- KPIs per variant ------------------------------------------------------------
st.subheader("Key metrics by variant")
cols = st.columns(4)
cols[0].metric("Users (control)", f"{int(control['users']):,}")
cols[0].metric("Users (treatment)", f"{int(treatment['users']):,}")
cols[1].metric("Conversion rate (control)", f"{control['conversion_rate']:.2%}")
cols[1].metric("Conversion rate (treatment)", f"{treatment['conversion_rate']:.2%}",
               delta=f"{primary['relative_lift']:+.1%}")
rpu = results.set_index("metric").loc["revenue_per_user"]
cols[2].metric("Revenue per user (control)", f"${control['revenue_per_user']:.2f}")
cols[2].metric("Revenue per user (treatment)", f"${treatment['revenue_per_user']:.2f}",
               delta=f"{rpu['relative_lift']:+.1%}")
cols[3].metric("Extra orders per month", f"{impact['extra_orders']:,.0f}",
               help=f"95% range {impact['extra_orders_low']:,.0f} to {impact['extra_orders_high']:,.0f}")
cols[3].metric("Extra revenue per month", f"${impact['extra_revenue']:,.0f}",
               help=f"95% range ${impact['extra_revenue_low']:,.0f} to ${impact['extra_revenue_high']:,.0f}")

# --- lift with confidence interval ---------------------------------------------------
st.subheader("Relative lift with 95% confidence interval")
lift = results.assign(
    label=results["metric"].map(METRIC_LABELS),
    lift=results["relative_lift"],
    low=results["ci_low"] / results["control_value"],
    high=results["ci_high"] / results["control_value"],
)
base = alt.Chart(lift).encode(y=alt.Y("label:N", sort=list(METRIC_LABELS.values()), title=None,
                                       axis=alt.Axis(labelLimit=250, labelFontSize=13, labelColor=INK)))
tooltip = [alt.Tooltip("label:N", title="Metric"), alt.Tooltip("lift:Q", format="+.1%", title="Lift"),
           alt.Tooltip("low:Q", format="+.1%", title="CI low"), alt.Tooltip("high:Q", format="+.1%", title="CI high"),
           alt.Tooltip("p_value:Q", format=".4f", title="p-value"), alt.Tooltip("decision:N", title="Decision")]
interval = base.mark_rule(strokeWidth=2, color=VARIANT_COLORS["control"]).encode(
    x=alt.X("low:Q", axis=alt.Axis(format="+%", title="Lift vs control", gridColor=GRID, tickCount=6)), x2="high:Q",
    tooltip=tooltip)
point = base.mark_circle(size=110, color=VARIANT_COLORS["control"], opacity=1).encode(x="lift:Q", tooltip=tooltip)
labels = base.mark_text(dy=-12, color=INK, fontSize=12).encode(x="lift:Q", text=alt.Text("lift:Q", format="+.1%"))
zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=MUTED_INK).encode(x="x:Q")
practical = alt.Chart(pd.DataFrame({"x": [config.MIN_PRACTICAL_LIFT]})).mark_rule(
    color=MUTED_INK, strokeDash=[4, 4]).encode(x="x:Q")
st.altair_chart((interval + point + labels + zero + practical).properties(height=240), width="stretch")
st.caption(f"Solid line: no effect. Dashed line: {config.MIN_PRACTICAL_LIFT:.0%} minimum lift worth shipping. "
           "CUPED rows adjust for each user's orders before the test, which narrows the interval.")

# --- conversion by device --------------------------------------------------------------
st.subheader("Conversion rate by device")
by_device = users.groupby(["device", "variant"], as_index=False).agg(users=("user_id", "size"),
                                                                      conversion_rate=("converted", "mean"))
device_chart = alt.Chart(by_device).mark_bar(cornerRadiusEnd=4, size=18).encode(
    x=alt.X("conversion_rate:Q", axis=alt.Axis(format="%", title="Conversion rate", gridColor=GRID, tickCount=6)),
    y=alt.Y("variant:N", title=None, axis=None),
    row=alt.Row("device:N", title=None, header=alt.Header(labelAngle=0, labelAlign="left", labelColor=INK)),
    color=alt.Color("variant:N", scale=alt.Scale(domain=list(VARIANT_COLORS), range=list(VARIANT_COLORS.values())),
                    legend=alt.Legend(title=None, orient="top")),
    tooltip=[alt.Tooltip("device:N"), alt.Tooltip("variant:N"), alt.Tooltip("users:Q", format=","),
             alt.Tooltip("conversion_rate:Q", format=".2%")],
).properties(height=50)
st.altair_chart(device_chart, width="stretch")

with st.expander("Full test results table"):
    st.dataframe(results, hide_index=True, width="stretch")
