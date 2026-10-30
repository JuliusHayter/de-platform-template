{{ config(severity='warn') }}
-- 30 order lines in the source (28 after the twins are removed) have a price that
-- rounds to 0.00: they are lines of five products priced under half a cent. They
-- stay; this reports them on every build instead of hiding them.
SELECT order_id, p_id, price_at_purchase, line_revenue
FROM {{ ref('fct_order_items') }}
WHERE line_revenue <= 0
