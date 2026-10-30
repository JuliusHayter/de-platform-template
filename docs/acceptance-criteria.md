# Acceptance criteria

What must be true for the warehouse to be usable, as tests that run on every
`dbt build`. The criteria come from what this repository already promises:
[ADR-0001](adr/0001-target-architecture.md), the layers table in
[`architecture.md`](architecture.md) and [`data-flows.md`](data-flows.md). Tests
live in [`transform/`](../transform).

Last run, 2026-10-29: `dbt build` gave **PASS=75 WARN=4 ERROR=0** (79 nodes: 62
data tests, 17 models), and `dbt source freshness` gave **2 errors**.

## Criteria that run

| # | Criterion | Test | Result |
|---|---|---|---|
| 1 | Revenue is not double-counted at the grain | `unique_combination_of_columns` on `(order_id, p_id)` in [`fct_order_items`](../transform/models/marts/_marts.yml) and on `(p_id, country, order_date)` in `fct_daily_demand` | Pass. When I broke it on purpose it failed with **284,306** rows |
| 2 | The same revenue in every layer | [`assert_revenue_reconciles`](../transform/tests/assert_revenue_reconciles.sql) | Pass |
| 3 | An order is defined once | [`assert_an_order_is_defined_once`](../transform/tests/assert_an_order_is_defined_once.sql) and `unique` on `int_orders.order_id` | Pass |
| 4 | Every order line belongs to a kept order | [`assert_every_order_line_has_a_kept_order`](../transform/tests/assert_every_order_line_has_a_kept_order.sql) | Pass |
| 5 | Every order line has a product | `relationships` to `dim_product` | Pass |
| 6 | Every order line has a date in the calendar | `relationships` to `dim_date` | Pass |
| 7 | Every order line has a country | `not_null` and `relationships` to `dim_country`. The join is a LEFT join, so without this a lost address would shrink revenue silently | Pass |
| 8 | Ratings are between 1 and 5 | `accepted_range` on `stg_review.rating` and `dim_product.avg_rating` | Pass |
| 9 | Each order has one payment | `unique` on `stg_payment.order_id` | Pass |
| 10 | Each customer has one default address | `unique` on `int_customer_addresses.c_id` | Pass |
| 11 | Nothing that arrived is lost between bronze and staging | [`assert_staging_loses_no_orders`](../transform/tests/assert_staging_loses_no_orders.sql) | Pass |
| 12 | Payment, password and contact data never leave bronze | [`assert_no_secret_or_personal_column_in_the_models`](../transform/tests/assert_no_secret_or_personal_column_in_the_models.sql) reads the column list of everything dbt built | Pass |
| 13 | The ML team's daily table exists at the grain they asked for | `unique` on `fct_daily_demand.demand_key` and the grain test above | Pass |
| 14 | Every product has a name | `not_null` on `dim_product.product_name`, severity warn | **Warn: 6** products, a fact about the source |
| 15 | Every product has a price | `accepted_range > 0` on `dim_product.price`, severity warn | **Warn: 5** products priced under half a cent |
| 16 | No order line brings in zero revenue | [`assert_line_revenue_is_positive`](../transform/tests/assert_line_revenue_is_positive.sql), severity warn | **Warn: 28** lines (30 in the source; two belonged to removed twins), all from the five products above |
| 17 | Reviews carry text | `not_null` on `stg_review.review_text`, severity warn | **Warn: 137** blank or missing |
| 18 | Data is no more than a day old (ADR-0001: daily is enough) | `dbt source freshness` on `orders` (warn 4 days, error 7) and `payment` (warn 72 hours, error 5 days) | **Error: orders 45.9 days old, payment 44.9.** Bronze is a static export ending 2026-09-14; nothing refreshes it until the lesson 3 pipelines are scheduled (lesson 7) |

The four warnings are known and not fixed here: the build reports them every
time and still succeeds. The freshness errors are real. `dbt build` does not run
freshness, so the build can be green while criterion 18 is red, which is exactly
what freshness is for.

## Criteria I could not turn into a test

| Criterion | Why no test can check it |
|---|---|
| **Revenue is the true revenue** | The twin rule under-removes, and nothing in the data says by how much. The generator marks originals (`order_id <= 111322`); a real company does not. Measured with that marker: the rule removes 22,053 of 222,644 orders (22,052 real twins) and leaves **89,270 twins standing**, because 80% of twins are placed one to four days after their original and never match on date. Twelve months to 2026-09-14: **11,801,682.40 EUR** over 66,992 orders by this rule, **6,523,907.20 EUR** over 37,147 originals only, and 13,065,805.92 EUR with no rule. A test can only compare the data with a rule; it cannot compare the rule with the truth. |
| Silver holds one version of each fact, **including after a correction or a delete** | Bronze comes from a cursor and a static export; neither sees updates or deletes ([ADR-0003](adr/0003-ingestion-modes.md)). dbt only sees what bronze holds. |
| Bronze matches the operational database | dbt cannot reach PostgreSQL. A reconciliation would have to live in ingestion. |
| History of changes over time, "last March's price" (ADR-0001) | The project has no snapshots, so there is nothing to test. `dim_product.price` is the current price only. |
| The figures match what analysts reported before | There is no earlier figure written down to compare with. |
