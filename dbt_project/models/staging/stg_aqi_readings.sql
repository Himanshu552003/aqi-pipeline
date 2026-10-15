-- stg_aqi_readings - cleaned pollutant readings: one row per station x pollutant x reading time.
-- Renames columns, standardises city names, adds IST date/hour helpers and removes duplicates.

with source as (

    select * from {{ source('raw', 'aqi_readings') }}

),

aliases as (

    select * from {{ ref('city_name_aliases') }}

),

deduplicated as (

    -- Postgres enforces the primary key, but Snowflake does not, so guarantee uniqueness here
    select
        *,
        row_number() over (
            partition by station, pollutant_id, reading_time_utc
            order by loaded_at_utc desc
        ) as row_num
    from source

)

select
    {{ dbt.hash(dbt.concat([
        "d.station", "'|'", "d.pollutant_id", "'|'",
        "cast(d.reading_time_utc as " ~ dbt.type_string() ~ ")"
    ])) }}                                              as reading_id,
    d.station                                           as station_name,
    d.pollutant_id,
    coalesce(a.standard_name, d.city)                   as city,
    d.state,
    d.latitude,
    d.longitude,
    d.reading_time_utc,
    d.reading_time_ist,
    cast(d.reading_time_ist as date)                    as reading_date_ist,
    cast(extract(hour from d.reading_time_ist) as integer) as reading_hour_ist,
    d.min_value                                         as min_sub_index,
    d.max_value                                         as max_sub_index,
    d.avg_value                                         as avg_sub_index,
    d.fetched_at_utc,
    d.loaded_at_utc

from deduplicated as d
left join aliases as a
    on  d.city = a.alias
    and (a.state is null or a.state = d.state)   -- state-specific aliases (e.g. Aurangabad exists in 2 states)
where d.row_num = 1
