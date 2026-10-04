-- One row per device type.
select
    row_number() over (order by device) as device_key,
    device                              as device_name
from (select distinct device from {{ ref('stg_checkout_experiment') }})
