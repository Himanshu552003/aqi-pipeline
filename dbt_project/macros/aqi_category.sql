{#
    aqi_category.sql - CPCB National AQI category for an AQI value.
    Defined once here and reused by every model, so the bands can never disagree.
#}
{% macro aqi_category(aqi_column) -%}
    case
        when {{ aqi_column }} is null then null
        when {{ aqi_column }} <= 50  then 'Good'
        when {{ aqi_column }} <= 100 then 'Satisfactory'
        when {{ aqi_column }} <= 200 then 'Moderate'
        when {{ aqi_column }} <= 300 then 'Poor'
        when {{ aqi_column }} <= 400 then 'Very Poor'
        else 'Severe'
    end
{%- endmacro %}


{% macro aqi_category_order(category_column) -%}
    case {{ category_column }}
        when 'Good' then 1
        when 'Satisfactory' then 2
        when 'Moderate' then 3
        when 'Poor' then 4
        when 'Very Poor' then 5
        when 'Severe' then 6
    end
{%- endmacro %}
