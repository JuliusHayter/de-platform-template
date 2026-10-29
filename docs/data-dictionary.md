# Data dictionary v1

Every table landed in bronze (`bronze/<table>/`, Parquet, columns exactly as
exported). Types are the Parquet types written from the CSV: `INT64`, `FLOAT64`,
`STRING`. Meanings are inferred from column names and sample values; correct
them when the source owners answer. Rows are counts in the export.

**PII column**

- `direct`: identifies or contacts a person.
- `indirect`: an ID that points to a person in another table.
- `possible`: free text or a photo link that may contain personal data.
- `secret`: credentials and payment data. It must never leave bronze.
- `no`: nothing personal.

Every table also has an `Unnamed: 0` column (INT64, the exporter's row index; `no`), shown only where listed.
`dt` (STRING, `YYYY-MM`) is added by the partitioning on `orders`, `order_items` and `payment`; it is not a source column.

## Customers and sellers

### customer (130,766 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| Unnamed: 0 | INT64 | Export row index | no |
| c_id | STRING | Customer id | indirect |
| fname | STRING | First name | direct |
| lname | STRING | Last name | direct |
| phone | INT64 | Phone number (leading zeros lost in export) | direct |
| email | STRING | Email address | direct |
| pwd | STRING | Stored password | **secret** |

### buyer (100,000 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| Unnamed: 0 | INT64 | Export row index | no |
| buyer_id | STRING | Buyer id used by orders, reviews and wishlists | indirect |

### customer_payment (100,000 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| payment_id | INT64 | Payment instrument id (see `payment_details`) | indirect |
| c_id | STRING | Owner | indirect |
| is_default | INT64 | 1 if the default instrument | no |

### customer_shipping (200,001 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| address_id | INT64 | Address id (see `shipping_details`) | indirect |
| c_id | STRING | Owner | indirect |
| is_default | INT64 | 1 if the default address | no |

### subscription (50,091 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| subscription_id | INT64 | Subscription id | no |
| c_id | STRING | Subscriber | indirect |
| start_date, end_date | STRING | Subscription period | no |

### wishlist_item (24,810 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| product_id | STRING | Wished product | no |
| buyer_id | STRING | Who wished it | indirect |

### seller (30,766 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| seller_id | STRING | Seller id | indirect |
| seller_type | STRING | Kind of seller | no |
| seller_name | FLOAT64 | Seller name; empty in the export, so typed as a float | possible (sellers may be individuals) |

## Payments (legacy tables)

### payment_details (100,000 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| payment_id | INT64 | Instrument id | indirect |
| card_no | INT64 | Full card number | **secret** |
| cvv | INT64 | Card security code | **secret** |
| expiry_date | STRING | Card expiry | **secret** |
| billing_address | STRING | Billing address | direct |

### payment (222,644 rows, partitioned by `dt`)
| Column | Type | Meaning | PII |
|---|---|---|---|
| transaction_id | INT64 | Transaction id | no |
| order_id | INT64 | Order paid | indirect |
| payment_id | INT64 | Instrument used | indirect |
| amount | FLOAT64 | Amount | no |
| method | STRING | Payment method | no |
| status | STRING | Transaction status | no |
| created_at | STRING | Timestamp | no |

## Shipping

### shipping_details (200,001 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| address_id | INT64 | Address id | indirect |
| street_address | STRING | Street | direct |
| city, state, zip | STRING | Locality | direct |
| country | STRING | Country | no on its own |
| phone | INT64 | Contact phone | direct |

### shipment (408,560 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| shipping_id | INT64 | Shipment id | no |
| order_id | INT64 | Order | indirect |
| p_id | STRING | Product shipped | no |
| carrier_id | INT64 | Carrier | no |
| shipment_type, status | STRING | Service level, state | no |
| est_delivery_date, actual_delivery_date | STRING | Dates | no |

### carrier (4 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| carrier_id | INT64 | Carrier id | no |
| carrier_name | STRING | Name | no |

## Orders

### orders (222,644 rows, partitioned by `dt`)
| Column | Type | Meaning | PII |
|---|---|---|---|
| order_id | INT64 | Order id | no |
| buyer_id | STRING | Buyer | indirect |
| discount_id | FLOAT64 | Discount applied; null if none | no |
| payment_id | INT64 | Instrument used | indirect |
| order_date | STRING | Order date | no |

### order_items (408,560 rows, partitioned by `dt`)
| Column | Type | Meaning | PII |
|---|---|---|---|
| order_id | INT64 | Order | no |
| p_id | STRING | Product | no |
| qty | INT64 | Units | no |
| price_at_purchase | FLOAT64 | Unit price when bought | no |

## Catalogue and reviews

### product (42,858 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| p_id | STRING | Product id | no |
| p_name, p_desc | STRING | Name, description | no |
| price | FLOAT64 | Current price | no |
| qty | INT64 | Stock | no |
| category_id | INT64 | Category | no |

### product_images (186,837 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| p_id | STRING | Product | no |
| p_image | STRING | Image link | no |

### category (2 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| category_id | INT64 | Category id | no |
| name, c_desc | STRING | Name, description | no |

### seller_products (46,593 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| seller_id, p_id | STRING | Seller offers product | indirect |

### review (111,322 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| review_id | INT64 | Review id | no |
| buyer_id | STRING | Author | indirect |
| r_desc, title | STRING | Free text | possible |
| rating | INT64 | Rating | no |
| seller_product_flag | STRING | Whether the review is of a seller or a product | no |

### review_images (119,382 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| review_id | INT64 | Review | no |
| review_img | STRING | Photo link | possible |

### product_reviews (111,322 rows) and seller_reviews (111,322 rows)
| Column | Type | Meaning | PII |
|---|---|---|---|
| review_id | INT64 | Review | no |
| p_id / seller_id | STRING | Product, or seller, reviewed | no / indirect |

## Landed empty (header only)

`cart`, `cart_items`, `daily_deals`, `discount`, `returns`: 0 rows. Columns:
`cart(cart_id, buyer_id, total_qty, total_price)`, `cart_items(cart_id, p_id, qty)`,
`daily_deals(p_id, deal_date, discount)`,
`discount(discount_id, discount_name, d_desc, discount_amt)`,
`returns(return_id, buyer_id, p_id, order_id)`. Types are unknown because no row
exists; `buyer_id` is `indirect`, the rest `no`.

## Clickstream (L03)

`bronze/clickstream/dt=YYYY-MM-DD/`, Parquet written by
`ingestion/consume_clickstream.py`. `dt` is the day of `event_time` and lives in
the path only. One row per event; fields outside an event's type are null. The
schema is [`ingestion/clickstream.schema.json`](../ingestion/clickstream.schema.json).

| Column | Type | Meaning | PII |
|---|---|---|---|
| schema_version | INT64 | Version of the event schema (1) | no |
| event_id | STRING | Unique event id (UUID), the key for deduplication | no |
| event_type | STRING | `product_viewed`, `added_to_cart` or `order_placed` | no |
| event_time | STRING | When it happened (ISO 8601, simulated clock) | no |
| emitted_at | STRING | When the storefront sent it (real clock) | no |
| session_id | STRING | One shopping session (UUID); links a person's events together | indirect |
| buyer_id | STRING | The buyer; joins to `buyer`/`customer` | indirect |
| p_id | STRING | Product viewed or added (not on `order_placed`) | no |
| price | FLOAT64 | Unit price at the time (not on `order_placed`) | no |
| qty | INT64 | Units added (`added_to_cart` only) | no |
| order_id | INT64 | The order created (`order_placed` only); joins to `orders` | indirect |
| payment_method | STRING | `Credit Card` or `PayPal` (`order_placed` only) | no |
| amount | FLOAT64 | Order total (`order_placed` only) | no |
| currency | STRING | Always `EUR` in version 1 | no |
| items | LIST<STRUCT<p_id, qty, price>> | Order lines (`order_placed` only) | no |

`buyer_id` and `session_id` are pseudonymous, not anonymous: they carry no name,
but `buyer_id` joins straight to `customer.fname`, `lname`, `phone` and `email`,
and `session_id` shows one person's browsing in order. Treat them as personal
data. Events hold no payment card data.

**Dead letter:** `bronze/_dlq/clickstream/dt=<day received>/`. Columns: `raw`
(the message as received, which may itself contain anything a client sent, so
treat it as sensitive), `reason`, `received_at`, `topic`, `partition`, `offset`.

## Which path wrote which table

Bronze does not have one shape. The origin decides the columns.

| Bronze prefix | Written by | Differences |
|---|---|---|
| `bronze/<table>/` (27 tables) | `ingestion/bronze_export.py` from the CSV export, run by hand in L02 | Has the exporter's `Unnamed: 0` column on most tables; dates are strings |
| `bronze/orders_pg/` | `ingestion/extract_orders.py`, from PostgreSQL | Same columns as the database `orders` table, without `Unnamed: 0`; `order_date` keeps the database type; partitioned by `dt=YYYY-MM`; new files only, no history before the first run |
| `bronze/clickstream/` | `ingestion/consume_clickstream.py` | As above |
| `bronze/_dlq/clickstream/` | the same consumer | As above |

None of these carries Airbyte's four extra columns (`_airbyte_raw_id`,
`_airbyte_extracted_at`, `_airbyte_meta`, `_airbyte_generation_id`), because no
Airbyte connection exists (see [ADR-0003](adr/0003-ingestion-modes.md)). If one
is added later, tables from that path will have them and the others will not.
`bronze/orders` and `bronze/orders_pg` hold overlapping orders from two paths;
silver has to pick one.

## What this tells lesson 3 and lesson 10

Never ingest into silver: `customer.pwd`, `payment_details.card_no`,
`payment_details.cvv`, `payment_details.expiry_date`. Redact or hash: the
`direct` columns. Audit: every table holding `indirect` ids, since joining them
re-identifies a person. Bronze itself holds the secrets, so its bucket access
(see `infra/iam.md`) is the only control on them today.
