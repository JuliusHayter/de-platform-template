-- The definition of an order (int_orders): no two kept orders share buyer, card,
-- discount, date and amount. Returns the pairs that do.
SELECT buyer_id, payment_id, discount_id, order_date, amount, COUNT(*) AS n_orders
FROM {{ ref('int_orders') }}
GROUP BY buyer_id, payment_id, discount_id, order_date, amount
HAVING COUNT(*) > 1
