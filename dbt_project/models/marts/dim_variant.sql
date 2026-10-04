-- One row per experiment arm. Control always gets key 1.
select
    row_number() over (order by variant) as variant_key,
    variant                              as variant_name,
    variant = 'control'                  as is_control,
    case variant
        when 'control' then 'Current checkout'
        when 'treatment' then 'Redesigned checkout'
    end                                  as variant_description
from (select distinct variant from {{ ref('stg_checkout_experiment') }})
