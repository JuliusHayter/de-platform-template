-- Drops Unnamed__0 (present on every row).
-- Turns blank review text into NULL: 110 texts are a single space and 27 are
--   already NULL, so after TRIM and NULLIF all 137 read as "no review" and a
--   not_null test can do its job. (The lesson's 14 empty strings arrived as
--   NULL in this bronze, because pandas read an empty CSV field as missing.)
SELECT
    review_id,
    buyer_id,
    rating,
    NULLIF(TRIM(r_desc), '') AS review_text,
    NULLIF(TRIM(title), '')  AS review_title,
    seller_product_flag
FROM {{ source('marketplace', 'review') }}
