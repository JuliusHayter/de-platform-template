-- GRAIN: one product in one order (order_id, p_id).
SELECT
    i.order_id,
    i.p_id,
    i.qty,
    i.price_at_purchase,
    -- Computed once, here, so every mart agrees on what revenue means.
    i.qty * i.price_at_purchase AS line_revenue,
    i.order_date,
    -- LEFT join: a line whose buyer has no address is still revenue. An inner
    -- join would shrink the totals with nothing failing. The country not_null
    -- test is what would tell us that happened.
    a.country
FROM {{ ref('int_order_items') }}        AS i
LEFT JOIN {{ ref('int_customer_addresses') }} AS a ON a.c_id = i.buyer_id
