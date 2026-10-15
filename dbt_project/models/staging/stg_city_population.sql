-- stg_city_population - Wikipedia city populations with standardised city names.
-- One row per city + state (some names, e.g. Aurangabad, exist in two states).

with population as (

    select * from {{ ref('city_population') }}

),

aliases as (

    select * from {{ ref('city_name_aliases') }}

)

select
    coalesce(a.standard_name, p.city) as city,
    p.state,
    p.population_2011,
    p.population_2001,
    p.latitude,
    p.longitude

from population as p
left join aliases as a
    on p.city = a.alias
