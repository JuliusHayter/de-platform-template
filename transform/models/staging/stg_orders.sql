-- Drops Unnamed__0, the exporter's row index (present on all 222,644 rows), and
--   dt, which the external table adds from the file path and is not a source column.
-- Parses order_date from text to DATE: bronze holds it as the string 'YYYY-MM-DD'.
-- Casts discount_id from FLOAT to INT64: the CSV export stored it as a float
--   because most rows are empty.
-- Left alone on purpose: the twin orders. Which orders are the same order is a
--   decision, so it is made in int_orders and not here.
SELECT
    order_id,
    buyer_id,
    payment_id,
    CAST(discount_id AS INT64) AS discount_id,
    PARSE_DATE('%Y-%m-%d', order_date) AS order_date
FROM {{ source('marketplace', 'orders') }}
