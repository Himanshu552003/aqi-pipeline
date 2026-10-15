-- city_ranking_24h - cities ranked by average AQI over the last 24 hours of data
-- (rank 1 = most polluted). The window is measured from the newest reading, not from "now",
-- so the result does not change just because the pipeline ran late.

with hourly as (

    select * from {{ ref('fct_city_aqi_hourly') }}

),

window_end as (

    select max(hour_start_ist) as newest_hour from hourly

),

last_24h as (

    select
        h.city,
        h.state,
        {{ round_float('avg(h.avg_aqi)') }}     as avg_aqi_24h,
        max(h.max_aqi)                          as peak_aqi_24h,
        count(*)                                as hours_covered
    from hourly as h
    cross join window_end as w
    where h.hour_start_ist > {{ dbt.dateadd('hour', -24, 'w.newest_hour') }}
    group by h.city, h.state

)

select
    city,
    state,
    avg_aqi_24h,
    {{ aqi_category('avg_aqi_24h') }}                   as aqi_category,
    peak_aqi_24h,
    hours_covered,
    rank() over (order by avg_aqi_24h desc)             as most_polluted_rank,
    rank() over (order by avg_aqi_24h asc)              as cleanest_rank
from last_24h
