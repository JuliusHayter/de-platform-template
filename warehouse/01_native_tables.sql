-- Bronze (Parquet in the bucket, read through external tables in bronze_julius)
-- copied into native tables. Run with: bq --location=europe-west1 query --nouse_legacy_sql < file
-- The only change is a type: order_date arrives as a string and has to be a DATE to partition on.

CREATE SCHEMA IF NOT EXISTS `data-engineering-a.warehouse_julius` OPTIONS (location = 'europe-west1');

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.orders` AS
SELECT * EXCEPT (order_date, dt), PARSE_DATE('%Y-%m-%d', order_date) AS order_date
FROM `data-engineering-a.bronze_julius.orders_external`;

-- order_items records no date of its own: it is fetched from the order.
CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.order_items` AS
SELECT i.order_id, i.p_id, i.qty, i.price_at_purchase, o.order_date
FROM `data-engineering-a.bronze_julius.order_items_external` AS i
JOIN `data-engineering-a.warehouse_julius.orders` AS o USING (order_id);

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.review` AS
SELECT * FROM `data-engineering-a.bronze_julius.review_external`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.product_reviews` AS
SELECT * FROM `data-engineering-a.bronze_julius.product_reviews_external`;

-- Lesson 5's dimensions, loaded now while bronze is open.
CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.product` AS
SELECT * FROM `data-engineering-a.bronze_julius.product_external`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.customer_shipping` AS
SELECT * FROM `data-engineering-a.bronze_julius.customer_shipping_external`;

CREATE OR REPLACE TABLE `data-engineering-a.warehouse_julius.shipping_details` AS
SELECT * FROM `data-engineering-a.bronze_julius.shipping_details_external`;
