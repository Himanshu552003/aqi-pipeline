-- city_hour_of_day_profile - typical AQI for each hour of the day (0-23, IST) per city,
-- over all collected history. is_peak_hour marks each city's most polluted hour.

with hourly as (

    select * from {{ ref('fct_city_aqi_hourly') }}

),

profile as (

    select
        city,
        state,
        reading_hour_ist                    as hour_of_day,
        {{ round_float('avg(avg_aqi)') }}   as avg_aqi,
        count(*)                            as days_observed
    from hourly
    group by city, state, reading_hour_ist

)

select
    city,
    state,
    hour_of_day,
    avg_aqi,
    days_observed,
    case
        when rank() over (partition by city, state order by avg_aqi desc) = 1 then true
        else false
    end as is_peak_hour
from profile
