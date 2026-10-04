-- Continuous calendar covering every day of the experiment, even days with no assignments.
with bounds as (
    select min(assignment_date) as first_day, max(assignment_date) as last_day
    from {{ ref('stg_checkout_experiment') }}
),

days as (
    select cast(d as date) as date_day, first_day
    from bounds, range(first_day, last_day + interval 1 day, interval 1 day) as t(d)
)

select
    cast(strftime(date_day, '%Y%m%d') as integer) as date_key,
    date_day                                      as date,
    date_diff('day', first_day, date_day) + 1     as experiment_day,
    date_diff('day', first_day, date_day) // 7 + 1 as experiment_week,
    isodow(date_day)                              as day_of_week,
    dayname(date_day)                             as day_name,
    isodow(date_day) in (6, 7)                    as is_weekend
from days
