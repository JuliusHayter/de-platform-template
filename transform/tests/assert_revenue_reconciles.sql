-- Revenue must be the same number in every layer. A fan-out or a lost join in
-- either mart makes the two totals disagree; returns a row when they do.
SELECT f.revenue AS fact_revenue, d.revenue AS demand_revenue
FROM (SELECT SUM(line_revenue) AS revenue FROM {{ ref('fct_order_items') }}) AS f
CROSS JOIN (SELECT SUM(revenue) AS revenue FROM {{ ref('fct_daily_demand') }}) AS d
WHERE ABS(f.revenue - d.revenue) > 0.01
