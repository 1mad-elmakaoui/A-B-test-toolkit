-- Typed, cleaned copy of the raw export. One row per user.
select
    cast(user_id as varchar)            as user_id,
    lower(trim(cast(variant as varchar))) as variant,
    cast(assignment_date as date)       as assignment_date,
    lower(trim(cast(device as varchar)))  as device,
    cast(pre_period_orders as integer)  as pre_period_orders,
    cast(converted as integer)          as converted,
    cast(revenue as decimal(12, 2))     as revenue
from {{ source('raw', 'checkout_experiment') }}
