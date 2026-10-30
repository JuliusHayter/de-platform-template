-- Nothing that arrived is lost between bronze and silver: staging must carry as
-- many orders and lines as the source holds. (Twins are removed later, in
-- int_orders, and counted there.)
SELECT 'orders' AS what, s.n AS in_bronze, t.n AS in_staging
FROM (SELECT COUNT(*) AS n FROM {{ source('marketplace', 'orders') }}) AS s,
     (SELECT COUNT(*) AS n FROM {{ ref('stg_orders') }}) AS t
WHERE s.n != t.n
UNION ALL
SELECT 'order_items', s.n, t.n
FROM (SELECT COUNT(*) AS n FROM {{ source('marketplace', 'order_items') }}) AS s,
     (SELECT COUNT(*) AS n FROM {{ ref('stg_order_items') }}) AS t
WHERE s.n != t.n
