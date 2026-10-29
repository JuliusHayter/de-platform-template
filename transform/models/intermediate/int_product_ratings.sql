-- A product has many reviews and none is THE review. The data has no rule to
-- pick one, so the only safe move is to aggregate to one row per product BEFORE
-- anything joins it. Joining reviews straight onto order lines would repeat every
-- line once per review.
SELECT
    pr.p_id,
    COUNT(*)                AS n_reviews,
    ROUND(AVG(r.rating), 3) AS avg_rating
FROM {{ ref('stg_product_reviews') }} AS pr
JOIN {{ ref('stg_review') }}          AS r USING (review_id)
GROUP BY pr.p_id
