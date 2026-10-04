"""Integration tests on the built warehouse and the Power BI export.

These need the pipeline to have run first (`make all` does this in order).
"""
import duckdb
import pandas as pd
import pytest

from src import config
from src.analysis import RESULT_COLUMNS
from src.export import EXPORT_TABLES

pytestmark = pytest.mark.skipif(not config.WAREHOUSE.exists(),
                                reason="warehouse not built yet; run `make data dbt analyze export`")


@pytest.fixture(scope="module")
def con():
    with duckdb.connect(str(config.WAREHOUSE), read_only=True) as connection:
        yield connection


@pytest.mark.parametrize("table", EXPORT_TABLES)
def test_exported_csv_matches_warehouse_row_count(con, table):
    csv_path = config.POWERBI_DATA_DIR / f"{table}.csv"
    assert csv_path.exists(), f"{csv_path} missing; run `make export`"
    db_rows = con.sql(f"select count(*) from {table}").fetchone()[0]
    assert len(pd.read_csv(csv_path)) == db_rows


def test_fact_table_has_one_row_per_raw_user(con):
    raw_rows = len(pd.read_csv(config.RAW_CSV))
    assert con.sql("select count(*) from fct_user_outcomes").fetchone()[0] == raw_rows


def test_results_table_shape(con):
    results = con.sql(f"select * from {config.RESULTS_TABLE}").df()
    assert list(results.columns) == RESULT_COLUMNS
    assert "conversion_rate" in set(results["metric"])
    assert results["ci_low"].le(results["absolute_lift"]).all()
    assert results["ci_high"].ge(results["absolute_lift"]).all()


def test_simulated_lift_is_recovered(con):
    """The data was simulated with a true +8% lift; the 95% CI should contain it."""
    row = con.sql(f"select * from {config.RESULTS_TABLE} where metric = 'conversion_rate'").df().iloc[0]
    true_diff = row["control_value"] * config.TRUE_RELATIVE_LIFT
    assert row["ci_low"] <= true_diff <= row["ci_high"]
