# Power BI data model

Every table is a CSV in `powerbi/data/`, written by `make export` from the dbt star schema
plus the Python test results.

```
                 dim_variant ──1:*── fct_experiment_results
                      │1
                      │*
dim_date ──1:*── fct_user_outcomes ──*:1── dim_device

fct_test_results   (no relationships)
_Measures          (empty table that holds the DAX measures)
```

## Tables

| Table | Grain | Rows | Role |
|---|---|---|---|
| `fct_user_outcomes` | one row per user | 50,000 | Fact. Test outcome for every enrolled user |
| `dim_variant` | one row per arm | 2 | Dimension. control / treatment |
| `dim_device` | one row per device | 3 | Dimension. desktop / mobile / tablet |
| `dim_date` | one row per experiment day | 28 | Dimension. Calendar of the test window |
| `fct_experiment_results` | one row per arm | 2 | Aggregate. Users, conversion rate, revenue per user |
| `fct_test_results` | one row per metric tested | 4 | Statistical results from `src/analysis.py` |

### Column types to check after import

Power BI usually detects these correctly. Fix any that differ in Power Query (Transform data):

| Table | Column | Type |
|---|---|---|
| `fct_user_outcomes` | `user_id` | Text |
| `fct_user_outcomes` | `variant_key`, `device_key`, `assignment_date_key`, `pre_period_orders`, `converted` | Whole number |
| `fct_user_outcomes` | `revenue` | Fixed decimal number |
| `dim_date` | `date_key` | Whole number |
| `dim_date` | `date` | Date |
| `dim_date` | `is_weekend` | True/False |
| `dim_variant` | `is_control` | True/False |
| `fct_test_results` | `control_value` … `p_value` | Decimal number |
| `fct_test_results` | `srm_passed` | True/False |

If your Windows regional settings use a comma as the decimal separator, numbers like
`0.0989` will import wrongly. In Power Query, right-click the column > Change Type >
Using Locale > Decimal Number, English (United States). Or set File > Options >
Current file > Regional settings > Locale for import to English (United States) before
loading.

## Relationships

Create these in Model view (drag the key from the dimension onto the fact). Turn off
Auto-detect relationships first (File > Options > Current file > Data Load) so Power BI
does not guess.

| From (one side) | To (many side) | Cardinality | Cross-filter direction | Active |
|---|---|---|---|---|
| `dim_variant[variant_key]` | `fct_user_outcomes[variant_key]` | One to many (1:*) | Single | Yes |
| `dim_device[device_key]` | `fct_user_outcomes[device_key]` | One to many (1:*) | Single | Yes |
| `dim_date[date_key]` | `fct_user_outcomes[assignment_date_key]` | One to many (1:*) | Single | Yes |
| `dim_variant[variant_key]` | `fct_experiment_results[variant_key]` | One to many (1:*) | Single | Yes |

Notes:

- Power BI may propose one-to-one for `dim_variant` to `fct_experiment_results` because both
  sides have two unique rows. Change it to one-to-many with single direction so filters flow
  only from the dimension to the fact, like the rest of the model.
- `fct_test_results` stays disconnected on purpose. Its numbers are whole-experiment results
  computed in Python. Letting a device slicer filter them would suggest the p-values change
  with the slicer, which they do not.
- Never use bidirectional filters here. The model is a plain star and does not need them.

## Date table

Select `dim_date` > Table tools > Mark as date table > Date column: `date`. This lets the
cumulative measure and the date axis behave correctly.

## Sort orders

| Column | Sort by column |
|---|---|
| `dim_date[day_name]` | `dim_date[day_of_week]` |

## Columns to hide

Hide these in Model view (right-click > Hide in report view). Report builders should use the
dimension attributes and the DAX measures instead.

| Table | Hide | Why |
|---|---|---|
| `fct_user_outcomes` | `variant_key`, `device_key`, `assignment_date_key` | Foreign keys; use the dimension columns |
| `fct_user_outcomes` | `converted` | Use the Conversions / Conversion Rate measures |
| `fct_user_outcomes` | `user_id`, `pre_period_orders` | Row-level detail not used in visuals |
| `fct_experiment_results` | `variant_key`, `variant_name` | Use `dim_variant[variant_name]` |
| `dim_variant` | `variant_key`, `is_control` | Technical columns |
| `dim_device` | `device_key` | Surrogate key |
| `dim_date` | `date_key`, `day_of_week` | Key and sort-by column |

Keep `fct_user_outcomes[revenue]` visible: the revenue distribution chart bins on it.
Once the `revenue (bins)` group exists you can hide the raw column too.

## Measures

All measures live in `_Measures` and are defined in `measures.dax`. Set each measure's format
in Measure tools as noted in its comment (percentages for rates and lifts, currency for
revenue).
