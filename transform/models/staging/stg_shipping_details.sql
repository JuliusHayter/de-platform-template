-- Drops Unnamed__0 and the personal data nothing downstream needs: street_address,
--   zip and phone. Keeping them would carry personal data into every layer built
--   on this one. Lesson 10 will redact properly; until then they are not selected.
SELECT
    address_id,
    city,
    state,
    country
FROM {{ source('marketplace', 'shipping_details') }}
