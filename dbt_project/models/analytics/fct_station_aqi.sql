-- fct_station_aqi - AQI per station per reading time (one row per station x hour).
--
-- CPCB method: a station's AQI is the HIGHEST pollutant sub-index, and it is only valid when
-- at least 3 pollutants are reported and one of them is PM2.5 or PM10.
--
-- Incremental model: each run only processes the last 6 hours of readings (new hours plus any
-- the source revised) instead of rebuilding the whole history.
-- Rebuild everything with: python run_dbt.py build --full-refresh

{{ config(
    materialized='incremental',
    unique_key=['station_name', 'reading_time_utc'],
    incremental_strategy='delete+insert'
) }}

with readings as (

    select * from {{ ref('stg_aqi_readings') }}

    {% if is_incremental() %}
    where reading_time_utc >= (
        select {{ dbt.dateadd('hour', -6, 'max(reading_time_utc)') }} from {{ this }}
    )
    {% endif %}

),

per_station as (

    select
        station_name,
        city,
        state,
        max(latitude)                                                       as latitude,
        max(longitude)                                                      as longitude,
        reading_time_utc,
        reading_time_ist,
        reading_date_ist,
        reading_hour_ist,
        count(*)                                                            as pollutants_reported,
        max(case when pollutant_id in ('PM2.5', 'PM10') then 1 else 0 end) as has_particulate,
        max(avg_sub_index)                                                  as aqi,
        max(case when pollutant_id = 'PM2.5' then avg_sub_index end)        as pm25_sub_index,
        max(case when pollutant_id = 'PM10'  then avg_sub_index end)        as pm10_sub_index,
        max(case when pollutant_id = 'NO2'   then avg_sub_index end)        as no2_sub_index,
        max(case when pollutant_id = 'SO2'   then avg_sub_index end)        as so2_sub_index,
        max(case when pollutant_id = 'CO'    then avg_sub_index end)        as co_sub_index,
        max(case when pollutant_id = 'OZONE' then avg_sub_index end)        as ozone_sub_index,
        max(case when pollutant_id = 'NH3'   then avg_sub_index end)        as nh3_sub_index
    from readings
    group by
        station_name, city, state,
        reading_time_utc, reading_time_ist, reading_date_ist, reading_hour_ist

),

dominant_pollutant as (

    -- the pollutant with the highest sub-index "drives" the AQI
    select
        station_name,
        reading_time_utc,
        pollutant_id,
        row_number() over (
            partition by station_name, reading_time_utc
            order by avg_sub_index desc, pollutant_id
        ) as pollutant_rank
    from readings

)

select
    {{ dbt.hash(dbt.concat([
        "p.station_name", "'|'", "cast(p.reading_time_utc as " ~ dbt.type_string() ~ ")"
    ])) }}                                          as station_reading_id,
    p.station_name,
    p.city,
    p.state,
    p.latitude,
    p.longitude,
    p.reading_time_utc,
    p.reading_time_ist,
    p.reading_date_ist,
    p.reading_hour_ist,
    p.aqi,
    {{ aqi_category('p.aqi') }}                     as aqi_category,
    d.pollutant_id                                  as dominant_pollutant,
    p.pollutants_reported,
    case
        when p.pollutants_reported >= 3 and p.has_particulate = 1 then true
        else false
    end                                             as is_valid_aqi,
    p.pm25_sub_index,
    p.pm10_sub_index,
    p.no2_sub_index,
    p.so2_sub_index,
    p.co_sub_index,
    p.ozone_sub_index,
    p.nh3_sub_index

from per_station as p
inner join dominant_pollutant as d
    on  p.station_name = d.station_name
    and p.reading_time_utc = d.reading_time_utc
    and d.pollutant_rank = 1
