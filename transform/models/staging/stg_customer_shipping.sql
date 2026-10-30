-- Drops Unnamed__0 (present on every row). A link table; nothing else to fix.
SELECT
    address_id,
    c_id,
    is_default
FROM {{ source('marketplace', 'customer_shipping') }}
