-- fct_city_aqi_daily - daily AQI summary per city (IST calendar day).

with stations as (

    select * from {{ ref('fct_station_aqi') }}
    where is_valid_aqi

),

daily as (

    select
        city,
        state,
        reading_date_ist,
        count(distinct station_name)            as stations_reporting,
        count(distinct reading_hour_ist)        as hours_covered,
        {{ round_float('avg(aqi)') }}           as avg_aqi,
        max(aqi)                                as max_aqi,
        min(aqi)                                as min_aqi
    from stations
    group by city, state, reading_date_ist

)

select
    {{ dbt.hash(dbt.concat([
        "city", "'|'", "state", "'|'", "cast(reading_date_ist as " ~ dbt.type_string() ~ ")"
    ])) }}                                  as city_day_id,
    daily.*,
    {{ aqi_category('avg_aqi') }}           as aqi_category
from daily
