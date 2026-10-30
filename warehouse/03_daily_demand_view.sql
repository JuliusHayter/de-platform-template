-- What the ML team reads every morning: units and revenue per product per day.
-- Partitioned and clustered like its base table. Without PARTITION BY the view
-- cannot prune: a filter on one month read 9,995,468 bytes instead of 366,940.
CREATE MATERIALIZED VIEW `data-engineering-a.warehouse_julius.daily_demand`
PARTITION BY DATE_TRUNC(order_date, MONTH) CLUSTER BY p_id AS
SELECT p_id, order_date, SUM(qty) AS units, SUM(qty * price_at_purchase) AS revenue
FROM `data-engineering-a.warehouse_julius.order_items_pc`
GROUP BY p_id, order_date;
