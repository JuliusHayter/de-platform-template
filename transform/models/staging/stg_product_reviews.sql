-- Drops Unnamed__0 (present on every row). A link table; nothing else to fix.
SELECT
    p_id,
    review_id
FROM {{ source('marketplace', 'product_reviews') }}
