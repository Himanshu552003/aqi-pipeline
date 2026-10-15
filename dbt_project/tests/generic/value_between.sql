{#
    value_between - custom generic test: fails for every row where the column is outside [min_value, max_value].
    Usage in a .yml file:
        data_tests:
          - value_between:
              arguments:
                min_value: 0
                max_value: 500
#}
{% test value_between(model, column_name, min_value, max_value) %}

select *
from {{ model }}
where {{ column_name }} < {{ min_value }}
   or {{ column_name }} > {{ max_value }}

{% endtest %}
