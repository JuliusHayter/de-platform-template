-- Drops dt (path artefact).
-- Rounds amount to cents and stores it as NUMERIC: FLOAT cannot be compared for
--   equality, and int_orders needs the amount to decide which orders are twins.
-- Parses created_at from text to TIMESTAMP.
SELECT
    transaction_id,
    order_id,
    payment_id,
    CAST(ROUND(amount, 2) AS NUMERIC) AS amount,
    method,
    status,
    PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', created_at) AS created_at
FROM {{ source('marketplace', 'payment') }}
