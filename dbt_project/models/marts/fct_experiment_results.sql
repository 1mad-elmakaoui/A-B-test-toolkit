-- Headline metrics per variant. Statistical tests live in fct_test_results (src/analysis.py).
with per_variant as (
    select
        f.variant_key,
        count(*)            as users,
        cast(sum(f.converted) as bigint) as conversions,
        cast(sum(f.revenue) as decimal(18, 2)) as revenue
    from {{ ref('fct_user_outcomes') }} as f
    group by f.variant_key
)

select
    p.variant_key,
    v.variant_name,
    p.users,
    p.conversions,
    p.revenue,
    p.conversions / p.users                            as conversion_rate,
    cast(p.revenue / p.users as double)                as revenue_per_user,
    p.users / sum(p.users) over ()                     as share_of_users
from per_variant as p
inner join {{ ref('dim_variant') }} as v using (variant_key)
order by p.variant_key
