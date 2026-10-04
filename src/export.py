"""Export the star schema and fct_test_results to CSV for Power BI Desktop.

Run with: python -m src.export
"""
import duckdb

from src import config

EXPORT_TABLES = config.STAR_TABLES + [config.RESULTS_TABLE]


def export_tables(out_dir=config.POWERBI_DATA_DIR) -> dict[str, int]:
    """Write every table to `<out_dir>/<table>.csv` and return row counts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    with duckdb.connect(str(config.WAREHOUSE), read_only=True) as con:
        for table in EXPORT_TABLES:
            path = out_dir / f"{table}.csv"
            con.execute(f"copy (select * from {table}) to '{path.as_posix()}' (header, delimiter ',')")
            counts[table] = con.sql(f"select count(*) from {table}").fetchone()[0]
    return counts


def main() -> None:
    for table, rows in export_tables().items():
        print(f"{table:<24} {rows:>7,} rows -> powerbi/data/{table}.csv")


if __name__ == "__main__":
    main()
