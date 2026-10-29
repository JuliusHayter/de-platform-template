# Lineage

Generated from `transform/target/manifest.json` by
[`transform/lineage_mermaid.py`](../transform/lineage_mermaid.py) after
`dbt docs generate`: 8 sources, 8 staging views, 4 intermediate views, 5 marts,
22 dependencies. Regenerate it whenever a model changes.

```mermaid
flowchart LR
  subgraph src[Bronze (sources)]
    orders[orders]
    order_items[order_items]
    payment[payment]
    product[product]
    review[review]
    product_reviews[product_reviews]
    customer_shipping[customer_shipping]
    shipping_details[shipping_details]
  end
  subgraph stg[Staging (views)]
    stg_orders[stg_orders]
    stg_order_items[stg_order_items]
    stg_payment[stg_payment]
    stg_product[stg_product]
    stg_review[stg_review]
    stg_product_reviews[stg_product_reviews]
    stg_customer_shipping[stg_customer_shipping]
    stg_shipping_details[stg_shipping_details]
  end
  subgraph int[Intermediate (views)]
    int_order_items[int_order_items]
    int_orders[int_orders]
    int_product_ratings[int_product_ratings]
    int_customer_addresses[int_customer_addresses]
  end
  subgraph marts[Marts (tables)]
    dim_date[dim_date]
    fct_daily_demand[fct_daily_demand]
    dim_product[dim_product]
    dim_country[dim_country]
    fct_order_items[fct_order_items]
  end
  fct_order_items --> fct_daily_demand
  stg_order_items --> int_order_items
  int_orders --> int_order_items
  stg_orders --> int_orders
  stg_payment --> int_orders
  orders --> stg_orders
  order_items --> stg_order_items
  payment --> stg_payment
  stg_product --> dim_product
  int_product_ratings --> dim_product
  product --> stg_product
  stg_product_reviews --> int_product_ratings
  stg_review --> int_product_ratings
  review --> stg_review
  product_reviews --> stg_product_reviews
  int_customer_addresses --> dim_country
  stg_customer_shipping --> int_customer_addresses
  stg_shipping_details --> int_customer_addresses
  customer_shipping --> stg_customer_shipping
  shipping_details --> stg_shipping_details
  int_order_items --> fct_order_items
  int_customer_addresses --> fct_order_items
```

## If the most upstream source changed shape

The most upstream source that matters is **`orders`** (bronze). If it gained,
lost or retyped a column tomorrow:

1. `stg_orders` reads it by name, so a **dropped or renamed** column fails the
   build there, loudly. A **new** column is ignored: staging selects explicit
   columns, which is why `Unnamed__0` never gets through.
2. A **retyped** `order_date` (it arrives as text and is parsed with
   `PARSE_DATE`) fails in `stg_orders`, before anything downstream is built.
3. Everything downstream depends on it: `int_orders`, `int_order_items`,
   `fct_order_items`, `fct_daily_demand`, and through them `dim_date` and
   `dim_country` by relationship. If a test on the way fails, `dbt build` skips
   everything below it (I saw 11 nodes skipped when I broke the grain on purpose),
   and `assert_staging_loses_no_orders` is the one that would notice a quiet change
   in the number of rows.

What I would look at first: `stg_orders`, then `int_orders`. Its twin rule keys on
`buyer_id`, `payment_id`, `discount_id` and `order_date`; a change to the meaning
of any of them changes which orders count, and nothing fails. That is the change
that would pass every test.
