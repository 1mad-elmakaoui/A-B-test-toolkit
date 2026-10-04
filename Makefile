PYTHON ?= python3
DBT = cd dbt_project && dbt

.PHONY: setup data dbt analyze export notebook app test all clean

setup:  ## Install Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

data:  ## Simulate the experiment into data/raw/
	$(PYTHON) -m src.simulate

dbt:  ## Build the star schema in DuckDB and run dbt tests
	$(DBT) run --profiles-dir .
	$(DBT) test --profiles-dir .

analyze:  ## Run the statistics and write fct_test_results
	$(PYTHON) -m src.analysis

export:  ## Write star schema + test results to powerbi/data/ as CSV
	$(PYTHON) -m src.export

notebook:  ## Execute the analysis notebook in place
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

app:  ## Open the Streamlit dashboard
	$(PYTHON) -m streamlit run app/app.py

test:  ## Run pytest
	$(PYTHON) -m pytest -q

all: data dbt analyze export notebook test  ## Run the whole pipeline end to end

clean:  ## Remove the warehouse and dbt build files
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal
	rm -rf dbt_project/target dbt_project/logs
