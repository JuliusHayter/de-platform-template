-- GRAIN: one product (p_id).
-- LEFT join and COALESCE go together: most products have no reviews, and zero
-- reviews is a fact, not a missing value.
SELECT
    p.p_id,
    p.product_name,
    p.category_id,
    p.price,
    COALESCE(r.n_reviews, 0) AS n_reviews,
    r.avg_rating
FROM {{ ref('stg_product') }}              AS p
LEFT JOIN {{ ref('int_product_ratings') }} AS r USING (p_id)
