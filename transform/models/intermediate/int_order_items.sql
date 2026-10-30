-- order_items has no date and no buyer of its own; both come from the order.
-- An INNER join to int_orders is deliberate: the lines of a twin order are
-- dropped with the twin. One line has exactly one order, so the grain is unchanged.
SELECT
    i.order_id, i.p_id, i.qty, i.price_at_purchase,
    o.order_date, o.buyer_id
FROM {{ ref('stg_order_items') }} AS i
JOIN {{ ref('int_orders') }}      AS o USING (order_id)
