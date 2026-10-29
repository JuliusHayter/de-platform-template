-- Every line in the fact belongs to an order that survived the order definition.
SELECT f.order_id, f.p_id
FROM {{ ref('fct_order_items') }} AS f
LEFT JOIN {{ ref('int_orders') }} AS o USING (order_id)
WHERE o.order_id IS NULL
