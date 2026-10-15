{#
    round_float.sql - round a floating-point expression, portable across databases.
    Postgres has no round(double precision, int), so it needs a cast to numeric and back.
    adapter.dispatch picks postgres__round_float on Postgres and default__round_float elsewhere.
#}
{% macro round_float(expression, digits=1) -%}
    {{ return(adapter.dispatch('round_float')(expression, digits)) }}
{%- endmacro %}

{% macro default__round_float(expression, digits) -%}
    round({{ expression }}, {{ digits }})
{%- endmacro %}

{% macro postgres__round_float(expression, digits) -%}
    cast(round(cast({{ expression }} as numeric), {{ digits }}) as double precision)
{%- endmacro %}
