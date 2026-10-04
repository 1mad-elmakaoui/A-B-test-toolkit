-- Fails if the mart loses or duplicates users or revenue on the way from staging.
with mart as (
    select sum(users) as users, sum(conversions) as conversions, sum(revenue) as revenue
    from {{ ref('fct_experiment_results') }}
),

staged as (
    select count(*) as users, sum(converted) as conversions, sum(revenue) as revenue
    from {{ ref('stg_checkout_experiment') }}
)

select *
from mart, staged
where mart.users != staged.users
   or mart.conversions != staged.conversions
   or mart.revenue != staged.revenue
