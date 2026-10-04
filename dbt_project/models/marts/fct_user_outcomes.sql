-- Fact table at user grain: one row per enrolled user, with foreign keys to every dimension.
select
    s.user_id,
    v.variant_key,
    d.device_key,
    cast(strftime(s.assignment_date, '%Y%m%d') as integer) as assignment_date_key,
    s.pre_period_orders,
    s.converted,
    s.revenue
from {{ ref('stg_checkout_experiment') }} as s
inner join {{ ref('dim_variant') }} as v on s.variant = v.variant_name
inner join {{ ref('dim_device') }} as d on s.device = d.device_name
