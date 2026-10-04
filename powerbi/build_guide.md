# Building the Power BI report

A two-page report for stakeholders: **Executive summary** answers "do we ship?" in five
seconds; **Deep dive** shows the evidence behind it. About 45 minutes in Power BI Desktop.

Before you start, run `make all` (or at least `make export`) so `powerbi/data/` holds fresh CSVs.

---

## Part 1. Load and model the data

1. **Open Power BI Desktop** > Blank report. Save it as `powerbi/checkout_ab_test.pbix`.
2. **Turn off relationship auto-detect**: File > Options and settings > Options > Current file >
   Data Load > untick *Autodetect new relationships after data is loaded*.
3. **Load the CSVs**: Home > Get data > Text/CSV. Load each file in `powerbi/data/`:
   `dim_variant`, `dim_device`, `dim_date`, `fct_user_outcomes`, `fct_experiment_results`,
   `fct_test_results`. Click **Load** (not Transform) for each unless a type needs fixing.
4. **Check column types** against the table in [`model.md`](model.md#column-types-to-check-after-import).
   If you use comma decimals, follow the locale note there.
5. **Create relationships** in Model view exactly as listed in [`model.md`](model.md#relationships).
6. **Mark `dim_date` as the date table** (date column `date`) and set `day_name` to sort by
   `day_of_week`.
7. **Add the measures table**: Home > Enter data > name it `_Measures` > Load. Delete its
   default `Column1` after adding the first measure.
8. **Add measures**: select `_Measures` > Modeling > New measure, and paste each measure from
   [`measures.dax`](measures.dax). Set the format shown in each comment (Measure tools > Format).
9. **Hide columns** listed in [`model.md`](model.md#columns-to-hide).
10. **Apply the theme**: View > Themes > Browse for themes > `powerbi/theme.json`. Control will be
    blue (`#2A78D6`) and treatment orange (`#EB6834`) on every visual.
11. **Create revenue bins** (needed on page 2): in the Data pane right-click
    `fct_user_outcomes[revenue]` > New group > Group type *Bin*, Bin type *Size of bins*,
    Bin size **20**. Name it `revenue (bins)`.

---

## Part 2. Page 1 — "Executive summary"

Rename the first page to **Executive summary**. Canvas 1280 x 720 (the default 16:9).

Layout, top to bottom:

```
┌───────────────────────────────────────────────────────────────────┐
│ Title                                                             │
├──────────────────────────────────────────────┬────────────────────┤
│ Decision card                                │ SRM status card    │
├──────────────────────────────────────────────┴────────────────────┤
│ KPI cards: Users | Conversion rate | Revenue per user  (control)  │
│ KPI cards: Users | Conversion rate | Revenue per user  (treatment)│
├───────────────────────────────────────────────────────────────────┤
│ Lift with 95% confidence interval (bar chart with error bars)     │
└───────────────────────────────────────────────────────────────────┘
```

No slicers on this page: every number here is for the whole experiment, and the test results
do not change with filters.

### 2.1 Title

- **Visual**: Text box.
- **Text**: "Checkout redesign A/B test" (20 pt, Segoe UI Semibold) and a second line
  "50,000 users, 1–28 June 2026. Primary metric: conversion rate." (11 pt, grey `#52514E`).

### 2.2 Decision card

- **Visual**: Card (new card visual; the classic Card works too).
- **Field**: `_Measures[Decision Label]`.
- **Format**:
  - Callout value 18 pt, bold, white text.
  - Background > fx > Format style *Field value* > `_Measures[Decision Color]`.
  - Turn off the category label; add a title "Recommendation".
- Reads e.g. **SHIP: +11.4% conversion (95% CI +6.0% to +16.8%)** on a green background.

### 2.3 SRM status card

- **Visual**: Card.
- **Fields**: `_Measures[SRM Status]` as the value; add `_Measures[Control Share of Users]` as a
  reference label (new card) or put it in a second small card beneath (classic card).
- **Format**: Callout value font colour > fx > Field value > `_Measures[SRM Color]`. Title
  "Data quality". Tooltip text: "Checks the 50/50 split. If this fails, ignore every other number."

### 2.4 KPI cards per variant

Six cards in two rows, one row per variant.

| Card | Field | Visual-level filter | Format |
|---|---|---|---|
| Users, control | `[Users]` | `dim_variant[variant_name]` is `control` | Whole number, `#,0` |
| Conversion rate, control | `[Conversion Rate]` | same | Percentage, 2 decimals |
| Revenue per user, control | `[Revenue per User]` | same | Currency, 2 decimals |
| Users, treatment | `[Users]` | `dim_variant[variant_name]` is `treatment` | Whole number |
| Conversion rate, treatment | `[Conversion Rate]` | same | Percentage, 2 decimals |
| Revenue per user, treatment | `[Revenue per User]` | same | Currency, 2 decimals |

Tips:
- Put a small text box "Current checkout (control)" left of the first row and
  "Redesign (treatment)" left of the second, each with a 4 px accent bar in the variant colour
  (Insert > Shapes > Rectangle).
- Build one card, format it, then copy-paste and swap the field and filter. Format painter
  copies styling between cards.
- Optional seventh card: `[Relative Lift]` titled "Conversion lift", format `+0.0%;-0.0%`.

### 2.5 Lift with confidence interval

- **Visual**: Clustered bar chart.
- **Y-axis**: `fct_test_results[metric]`.
- **X-axis**: `_Measures[Test Relative Lift]`.
- **Analytics pane** (magnifying glass icon):
  - **Error bars** > Enable > Upper bound `[Test CI High (Relative)]`, Lower bound
    `[Test CI Low (Relative)]`. Relationship to measure: *Absolute*. Error bar colour `#0B0B0B`,
    width 2 px, marker *Line*.
  - **X-axis constant line** at `0.02`, dashed grey, data label "Minimum worth shipping (+2%)".
  - **X-axis constant line** at `0`, solid grey, no label.
- **Format**:
  - X-axis: display units none, format `+0%`, start 0 (or blank if any lift is negative).
  - Data labels on, format `+0.0%`, position *Inside end*.
  - Bars: single colour `#2A78D6`. Sort by metric so `conversion_rate` sits on top.
  - Tooltip: add `[Test P Value]` to Tooltips.
  - Title: "Relative lift vs control, with 95% confidence interval".
- Optional: rename metric values in Power Query (Replace values) to "Conversion rate",
  "Revenue per user", "Conversion rate (CUPED)", "Revenue per user (CUPED)".

---

## Part 3. Page 2 — "Deep dive"

Add a page named **Deep dive**.

```
┌───────────────────────────────────────────────────────────────────┐
│ Title                                    Slicers: Device, Variant │
├───────────────────────────────────────────────────────────────────┤
│ Cumulative conversion over time (line chart)                      │
├─────────────────────────────────┬─────────────────────────────────┤
│ Conversion by device (bar)      │ Revenue distribution (column)   │
├─────────────────────────────────┴─────────────────────────────────┤
│ Results by device (matrix)                                        │
└───────────────────────────────────────────────────────────────────┘
```

### 3.1 Slicers

| Slicer | Field | Style |
|---|---|---|
| Device | `dim_device[device_name]` | Tile (horizontal buttons), multi-select with Ctrl, "Select all" on |
| Variant | `dim_variant[variant_name]` | Tile, "Select all" on |

Both slicers filter every visual on this page. Slicers only affect their own page unless you
sync them (View > Sync slicers); leave them unsynced so page 1 always shows whole-experiment
numbers.

### 3.2 Cumulative conversion over time

- **Visual**: Line chart.
- **X-axis**: `dim_date[date]` (use the column itself, not the date hierarchy: click the arrow on
  the field and choose `date`).
- **Y-axis**: `_Measures[Daily Cumulative Conversion by Variant]`.
- **Legend**: `dim_variant[variant_name]`.
- **Format**: Y-axis format `0%`, range 6% to 14% so the gap is readable; line width 2 px;
  markers off; data labels off except *Series label* at the end of each line (Format > Series
  labels, in recent versions). Title "Cumulative conversion rate by variant".
- **What to point out**: the lines wobble in the first days and settle after about a week. That
  wobble is why the test was not called early.

### 3.3 Conversion by device

- **Visual**: Clustered bar chart.
- **Y-axis**: `dim_device[device_name]`.
- **X-axis**: `_Measures[Conversion Rate]`.
- **Legend**: `dim_variant[variant_name]`.
- **Tooltips**: `[Users]`, `[Relative Lift]`.
- **Format**: data labels `0.0%`; X-axis starts at 0; title "Conversion rate by device".

### 3.4 Revenue distribution

- **Visual**: Clustered column chart.
- **X-axis**: `fct_user_outcomes[revenue (bins)]` (created in Part 1 step 11). Set X-axis type to
  *Categorical*.
- **Y-axis**: `_Measures[Users]`.
- **Legend**: `dim_variant[variant_name]`.
- **Visual-level filter**: `fct_user_outcomes[revenue]` *is greater than* 0. Without it the
  roughly 45,000 non-buyers at $0 flatten everything else.
- **Format**: title "Order value distribution (buyers only)"; X-axis title "Order value ($)".
- **What to point out**: both variants have the same shape. The redesign got more people to buy,
  it did not change how much they spend.

### 3.5 Results by device

- **Visual**: Matrix.
- **Rows**: `dim_device[device_name]`.
- **Values**: `[Users]`, `[Control Conversion Rate]`, `[Treatment Conversion Rate]`,
  `[Relative Lift]`, `[Revenue per User]`.
- **Format**:
  - Conditional formatting on `[Relative Lift]`: Cell elements > Data bars, positive bar
    `#2A78D6`, negative `#E34948`.
  - Turn on row subtotals so the total row matches page 1.
  - Title "Results by device".
- **Caveat to add as a subtitle**: "Device splits are exploratory. The test was sized for the
  overall result, so per-device differences are not statistically confirmed."

---

## Part 4. Formatting checklist

- **Colours**: control is always blue `#2A78D6`, treatment always orange `#EB6834`. The theme
  handles this as long as `control` sorts before `treatment` in every legend (it does,
  alphabetically). Green/amber/red are reserved for the decision and SRM cards.
- **Numbers**: rates as percentages with 1–2 decimals; lifts with an explicit sign
  (`+0.0%;-0.0%`); money with a currency symbol. Never show raw decimals like 0.1102.
- **Axes**: rates start at zero on bar charts. Line charts may zoom in, but label the axis.
- **Text**: sentence-case titles that say what the visual shows. Avoid default titles like
  "Conversion Rate by device_name and variant_name".
- **Gridlines**: light grey, horizontal only; turn off vertical gridlines.
- **Tooltips**: add `[Users]` to every chart so readers can see how much data sits behind a bar.
- **Alt text**: Format > General > Alt text on each visual for screen-reader users.
- **Page navigation**: add two buttons (Insert > Buttons > Navigator > Page navigator) at the top
  of each page.
- **Refresh**: after re-running `make all`, click Home > Refresh. Paths are absolute, so if you
  move the repo use Transform data > Data source settings > Change source.

## Part 5. Save and share

1. Save `powerbi/checkout_ab_test.pbix`.
2. Export a screenshot of each page (File > Export > Export to PDF, or a screen capture) to
   `powerbi/screenshots/executive_summary.png` and `powerbi/screenshots/deep_dive.png`; the
   README links to the first one.
3. To share online: Home > Publish to your Power BI workspace.
