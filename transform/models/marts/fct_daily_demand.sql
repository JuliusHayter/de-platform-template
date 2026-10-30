-- GRAIN: one product, in one country, on one day (p_id, country, order_date).
-- The table the ML team asked for.
SELECT
    {{ dbt_utils.generate_surrogate_key(['p_id', 'country', 'order_date']) }} AS demand_key,
    p_id,
    country,
    order_date,
    SUM(qty)          AS units,
    SUM(line_revenue) AS revenue
FROM {{ ref('fct_order_items') }}
GROUP BY p_id, country, order_date
