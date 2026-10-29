-- Payment, password and contact data must not leave bronze. Looks at every column
-- of every model dbt built and returns any that carries one of those names.
SELECT table_name, column_name
FROM `{{ target.project }}.{{ target.dataset }}`.INFORMATION_SCHEMA.COLUMNS
WHERE LOWER(column_name) IN (
    'pwd', 'password', 'card_no', 'cvv', 'expiry_date', 'billing_address',
    'fname', 'lname', 'email', 'phone', 'street_address', 'zip'
)
