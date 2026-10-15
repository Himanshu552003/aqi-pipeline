-- fct_city_aqi_hourly - average AQI per city per hour (IST), across all stations in the city.
-- Only valid station AQIs (CPCB rule) are used.

with stations as (

    select * from {{ ref('fct_station_aqi') }}
    where is_valid_aqi

),

hourly as (

    select
        city,
        state,
        {{ dbt.date_trunc('hour', 'reading_time_ist') }}    as hour_start_ist,
        reading_date_ist,
        reading_hour_ist,
        count(*)                                            as stations_reporting,
        {{ round_float('avg(aqi)') }}                       as avg_aqi,
        max(aqi)                                            as max_aqi,
        min(aqi)                                            as min_aqi
    from stations
    group by
        city, state,
        {{ dbt.date_trunc('hour', 'reading_time_ist') }},
        reading_date_ist, reading_hour_ist

)

select
    {{ dbt.hash(dbt.concat([
        "city", "'|'", "state", "'|'", "cast(hour_start_ist as " ~ dbt.type_string() ~ ")"
    ])) }}                                  as city_hour_id,
    hourly.*,
    {{ aqi_category('avg_aqi') }}           as aqi_category
from hourly
