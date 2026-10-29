-- The same tables at different grains. Month is the grain kept; day and year
-- exist to measure what each costs (docs/warehouse-tuning.md).

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.orders_p`
PARTITION BY DATE_TRUNC(order_date, MONTH) AS
SELECT * FROM `data-engineering-a.warehouse_julius.orders`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items_p`
PARTITION BY DATE_TRUNC(order_date, MONTH) AS
SELECT * FROM `data-engineering-a.warehouse_julius.order_items`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items_pc`
PARTITION BY DATE_TRUNC(order_date, MONTH) CLUSTER BY p_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.order_items`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items_clustered`
CLUSTER BY p_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.order_items`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items_day`
PARTITION BY order_date CLUSTER BY p_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.order_items`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items_year`
PARTITION BY DATE_TRUNC(order_date, YEAR) CLUSTER BY p_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.order_items`;

-- Q3 has no date. Clustering on the join keys is the only thing that could help it.
CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.review_c`
CLUSTER BY review_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.review`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.product_reviews_c`
CLUSTER BY p_id AS
SELECT * FROM `data-engineering-a.warehouse_julius.product_reviews`;
