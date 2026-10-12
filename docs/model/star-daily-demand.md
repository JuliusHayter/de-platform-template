# Star: daily demand

## Business process

Selling a product to a customer: every line of a completed order contributes
to how much of that product moved, in which country, on which day.

## Grain

One row per product, per country, per day.

## Dimensions

- **Product** — with its category. The seller cannot be a dimension at this
  grain: an order line does not record which seller sold the product.
- **Country** — the shipping country of the order.
- **Date** — the calendar day the order was placed.

## Facts

| Fact | Summable? |
|---|---|
| Units sold | Yes — sums across product, country and date |
| Revenue | Yes — sums across product, country and date |

## Sketch

```mermaid
erDiagram
  FACT_DAILY_DEMAND }o--|| DIM_PRODUCT : "references"
  FACT_DAILY_DEMAND }o--|| DIM_COUNTRY : "references"
  FACT_DAILY_DEMAND }o--|| DIM_DATE : "references"

  FACT_DAILY_DEMAND {
    string product_id FK
    string country_id FK
    date date_id FK
    int units_sold
    decimal revenue
  }

  DIM_PRODUCT {
    string product_id PK
    string name
    string category
  }

  DIM_COUNTRY {
    string country_id PK
    string name
  }

  DIM_DATE {
    date date_id PK
    int year
    int month
    int day
  }
```

## Why this grain, from the very first ingestion

This sketch is what the ML team asked for (flow 5 in
[`data-flows.md`](../data-flows.md)), and it says which columns bronze must
carry even though the warehouse model isn't built until L05:

- Every order line needs its **product**, **shipping country** and **order
  date** to survive ingestion untouched — this fact table cannot be rebuilt
  later from an aggregate that dropped them.
- **Seller** is deliberately left out: it does not exist at the order-line
  grain, and adding it later would mean re-extracting raw data, not just
  re-modelling what's already in bronze.
