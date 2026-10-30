-- Drops Unnamed__0 (present on every row).
-- Trims names into NULL: 6 products have an empty name.
-- Rounds price to cents: 35,205 of 42,858 prices carry floating-point noise.
-- Left alone: p_desc, which is free text and not used downstream.
SELECT
    p_id,
    NULLIF(TRIM(p_name), '') AS product_name,
    category_id,
    ROUND(price, 2) AS price,
    qty AS stock
FROM {{ source('marketplace', 'product') }}
