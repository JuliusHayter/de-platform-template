-- GRAIN: one country. n_customers counts default addresses.
SELECT
    country,
    COUNT(*) AS n_customers
FROM {{ ref('int_customer_addresses') }}
GROUP BY country
