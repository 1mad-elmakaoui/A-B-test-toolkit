"""Simulate a seeded e-commerce checkout A/B test and save it to data/raw/.

Each user has a latent purchase propensity that drives both their orders in the
90 days before the test (pre_period_orders) and their chance of converting during
the test. That shared driver is what makes CUPED useful later on. The treatment
multiplies every user's conversion probability by 1.08, a true +8% relative lift.
"""
import numpy as np
import pandas as pd

from src import config

DEVICE_SHARE = {"mobile": 0.58, "desktop": 0.35, "tablet": 0.07}
DEVICE_CONVERSION_MULTIPLIER = {"mobile": 0.85, "desktop": 1.25, "tablet": 1.0}


def simulate(n_users: int = config.N_USERS, seed: int = config.SEED,
             relative_lift: float = config.TRUE_RELATIVE_LIFT) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    variant = rng.choice(["control", "treatment"], size=n_users)
    day_offset = rng.integers(0, config.EXPERIMENT_DAYS, size=n_users)
    assignment_date = pd.Timestamp(config.EXPERIMENT_START) + pd.to_timedelta(day_offset, unit="D")
    device = rng.choice(list(DEVICE_SHARE), size=n_users, p=list(DEVICE_SHARE.values()))

    propensity = rng.gamma(shape=0.7, scale=1.0, size=n_users)
    pre_period_orders = rng.poisson(propensity * 3.0)

    device_multiplier = pd.Series(device).map(DEVICE_CONVERSION_MULTIPLIER).to_numpy()
    p_convert = (0.02 + 0.115 * np.minimum(propensity, 5.0)) * device_multiplier
    p_convert = np.where(variant == "treatment", p_convert * (1 + relative_lift), p_convert)
    converted = rng.random(n_users) < np.clip(p_convert, 0, 0.95)

    order_value = rng.lognormal(mean=np.log(52), sigma=0.55, size=n_users) * (1 + 0.08 * np.minimum(pre_period_orders, 5))
    revenue = np.where(converted, order_value, 0.0).round(2)

    return pd.DataFrame({
        "user_id": [f"u{i:06d}" for i in range(1, n_users + 1)],
        "variant": variant,
        "assignment_date": assignment_date.strftime("%Y-%m-%d"),
        "device": device,
        "pre_period_orders": pre_period_orders,
        "converted": converted.astype(int),
        "revenue": revenue,
    })


def main() -> None:
    df = simulate()
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CSV, index=False)
    summary = df.groupby("variant").agg(users=("user_id", "size"), conversion_rate=("converted", "mean"),
                                        revenue_per_user=("revenue", "mean"))
    print(f"Wrote {len(df):,} users to {config.RAW_CSV.relative_to(config.ROOT)}")
    print(summary.round(4).to_string())


if __name__ == "__main__":
    main()
