{#
    generate_schema_name.sql - use the schema name from dbt_project.yml as-is.
    By default dbt would build "public_staging" / "public_analytics". We want clean layer
    names (raw, staging, analytics) on both Postgres and Snowflake.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
