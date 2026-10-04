"""Paths and experiment constants shared by every step of the pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_CSV = RAW_DIR / "checkout_experiment.csv"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
POWERBI_DATA_DIR = ROOT / "powerbi" / "data"

# Simulation
SEED = 42
N_USERS = 50_000
EXPERIMENT_START = "2026-06-01"
EXPERIMENT_DAYS = 28
TRUE_RELATIVE_LIFT = 0.08

# Decision rules, fixed before looking at the results
ALPHA = 0.05
POWER = 0.80
MDE_RELATIVE = 0.08          # smallest lift the test was sized to detect
MIN_PRACTICAL_LIFT = 0.02    # relative lift below this is not worth shipping
SRM_THRESHOLD = 0.001        # chi-square p-value below this flags a sample ratio mismatch

# Tables the star schema exposes, in the order Power BI should load them
STAR_TABLES = [
    "dim_variant",
    "dim_device",
    "dim_date",
    "fct_user_outcomes",
    "fct_experiment_results",
]
RESULTS_TABLE = "fct_test_results"
