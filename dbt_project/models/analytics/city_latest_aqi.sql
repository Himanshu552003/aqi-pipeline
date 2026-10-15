-- city_latest_aqi - the current air quality of every city (powers the KPI cards and the map).
-- "Current" = each station's latest valid reading, if it is at most 3 hours older than the newest
-- reading in the data. Stations that stopped reporting are left out instead of showing stale values.

with stations as (

    select * from {{ ref('fct_station_aqi') }}
    where is_valid_aqi

),

newest as (

    select max(reading_time_utc) as newest_reading_utc from stations

),

latest_per_station as (

    select
        s.*,
        row_number() over (partition by s.station_name order by s.reading_time_utc desc) as recency_rank
    from stations as s
    cross join newest as n
    where s.reading_time_utc >= {{ dbt.dateadd('hour', -3, 'n.newest_reading_utc') }}

),

current_station as (

    select * from latest_per_station where recency_rank = 1

),

worst_station as (

    select
        city,
        state,
        station_name        as worst_station,
        dominant_pollutant,
        row_number() over (partition by city, state order by aqi desc, station_name) as station_rank
    from current_station

),

city_now as (

    select
        city,
        state,
        count(*)                                as stations_reporting,
        {{ round_float('avg(aqi)') }}           as avg_aqi,
        max(aqi)                                as max_aqi,
        min(aqi)                                as min_aqi,
        avg(latitude)                           as latitude,
        avg(longitude)                          as longitude,
        max(reading_time_ist)                   as last_reading_ist
    from current_station
    group by city, state

),

population as (

    -- a city name can appear in two states, so join on both
    select city, state, max(population_2011) as population_2011
    from {{ ref('stg_city_population') }}
    group by city, state

)

select
    c.city,
    c.state,
    c.avg_aqi,
    {{ aqi_category('c.avg_aqi') }}         as aqi_category,
    c.max_aqi,
    c.min_aqi,
    c.stations_reporting,
    w.worst_station,
    w.dominant_pollutant,
    c.latitude,
    c.longitude,
    p.population_2011,
    c.last_reading_ist

from city_now as c
inner join worst_station as w
    on  c.city = w.city
    and c.state = w.state
    and w.station_rank = 1
left join population as p
    on  c.city = p.city
    and c.state = p.state
