-- The coarser alternative, to show the collapse ratio moves (2.47 lines per row
-- instead of 1.14). Not what the ML team reads.
CREATE MATERIALIZED VIEW `data-engineering-a.warehouse_julius.monthly_demand` AS
SELECT p_id, DATE_TRUNC(order_date, MONTH) AS month, SUM(qty) AS units, SUM(qty * price_at_purchase) AS revenue
FROM `data-engineering-a.warehouse_julius.order_items_pc`
GROUP BY p_id, month;
