-- ONE DEFINITION OF AN ORDER. Twin orders are duplicates the export never
-- marked. Two orders are the same order when they share buyer, card (payment_id),
-- discount, date and amount; the lowest order_id is kept.
--
-- This is the middle definition from lesson 1. It is precise and it under-removes:
-- measured on this data it drops 22,053 of 222,644 orders, 22,052 of them real
-- twins, and leaves 89,270 twins standing (80% of twins are placed 1 to 4 days
-- after their original, so they never match on date). docs/acceptance-criteria.md
-- says what this means for revenue.
WITH paid AS (
    SELECT o.order_id, o.buyer_id, o.payment_id, o.discount_id, o.order_date, p.amount
    FROM {{ ref('stg_orders') }} AS o
    -- One payment per order (tested in stg_payment), so this join cannot multiply rows.
    JOIN {{ ref('stg_payment') }} AS p USING (order_id)
),
ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY buyer_id, payment_id, COALESCE(discount_id, -1), order_date, amount
            ORDER BY order_id
        ) AS rn
    FROM paid
)
SELECT order_id, buyer_id, payment_id, discount_id, order_date, amount
FROM ranked
WHERE rn = 1
