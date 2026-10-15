-- aqi_category_distribution - how often each city's stations were in each AQI category
-- (share of station-hours: Good / Satisfactory / Moderate / Poor / Very Poor / Severe).

with stations as (

    select * from {{ ref('fct_station_aqi') }}
    where is_valid_aqi

),

counts as (

    select
        city,
        state,
        aqi_category,
        count(*) as station_hours
    from stations
    group by city, state, aqi_category

)

select
    city,
    state,
    aqi_category,
    {{ aqi_category_order('aqi_category') }}        as category_order,
    station_hours,
    {{ round_float(
        '100.0 * station_hours / sum(station_hours) over (partition by city, state)'
    ) }}                                            as share_pct
from counts
