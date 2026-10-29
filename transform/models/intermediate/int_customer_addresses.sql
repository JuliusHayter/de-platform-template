-- One row per customer: their DEFAULT address. A customer has several addresses,
-- so joining all of them would multiply every order by the number of addresses;
-- the rule that picks one (is_default = 1) exists in the data and is tested
-- (every customer has exactly one default).
SELECT
    cs.c_id,
    sd.country
FROM {{ ref('stg_customer_shipping') }} AS cs
JOIN {{ ref('stg_shipping_details') }}  AS sd USING (address_id)
WHERE cs.is_default = 1
