-- GRAIN: one calendar day, from var date_start to var date_end (exclusive).
SELECT
    CAST(date_day AS DATE)                          AS date_day,
    EXTRACT(YEAR FROM date_day)                     AS year,
    EXTRACT(MONTH FROM date_day)                    AS month,
    EXTRACT(DAY FROM date_day)                      AS day,
    FORMAT_DATE('%Y-%m', date_day)                  AS year_month,
    FORMAT_DATE('%A', date_day)                     AS day_name,
    EXTRACT(DAYOFWEEK FROM date_day) IN (1, 7)      AS is_weekend
FROM (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('date_start') ~ "' as date)",
        end_date="cast('" ~ var('date_end') ~ "' as date)"
    ) }}
)
