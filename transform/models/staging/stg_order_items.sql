-- Drops dt, the partition column the external table adds from the file path.
-- Left alone on purpose: 30 lines whose price rounds to 0.00. They belong to five
--   products that cost under half a cent, so they are in the source; removing
--   them would change revenue. assert_line_revenue_is_positive reports them as a
--   warning every build (28 once int_orders has removed two twins).
SELECT
    order_id,
    p_id,
    qty,
    price_at_purchase
FROM {{ source('marketplace', 'order_items') }}
