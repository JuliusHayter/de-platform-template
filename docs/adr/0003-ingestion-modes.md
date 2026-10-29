# ADR-0003: Ingest events by streaming and orders by an incremental cursor; leave updates and deletes unhandled for now

- **Status:** accepted
- **Date:** 2026-10-29
- **Author:** Julius Hayter
- **Lesson:** L03

## Context

Bronze ([ADR-0002](0002-bronze-layout.md)) was filled by hand from a CSV export.
Two sources now have to feed it without a person: the clickstream (Kafka topic
`clickstream`, JSON events from the storefront) and the company PostgreSQL
database (orders and the tables around them). Both are the company's live stack;
the events and the live orders are generated at 400 times real time.

My teacher's route for this course was route 3: no Airbyte, because routes 1
and 2 were not workable. So the "connector" is a script I wrote
(`ingestion/extract_tables.py`), and there is no Airbyte connection or exported
configuration in the repository.

The figures below are from my own runs of the exercise steps on this stack.

## Options considered

| Source | Option | For | Against |
|---|---|---|---|
| Clickstream | **Streaming consumer, commit after write** | Never loses an event | Duplicates on a crash: 200 in my kill test |
| Clickstream | Commit before write (or auto-commit) | No duplicates after a crash | A crash between the two loses the batch, permanently and silently. Rejected. |
| Orders | **Incremental batch, cursor `order_id` with `>`** | Simple; no boundary row: the first row of a re-run was cursor + 1 | Never sees an update or a delete |
| Orders | Incremental on `order_date` with `>=` | Matches how analysts think | Re-reads the boundary row on every run and shares one value across hundreds of orders. Rejected. |
| Orders, products | Change data capture | The log saw all three of my changes (insert, update, delete); the slot retained 50 kB after a few minutes | Needs a long-running reader (Debezium or Airbyte) that I could not use, and a forgotten slot grows for ever |

## Criteria

Losing nothing outranks duplicates, because duplicates carry an `event_id` and
can be removed in silver, while a lost event leaves no trace. Second, whether
the mode sees what the business needs: revenue needs deletes and price
corrections eventually, a daily demand table does not. Third, whether I could
build and run it with what I had.

## Decision

- **Clickstream:** the Kafka consumer, writing then committing, partitioned by
  `event_time`. Guarantee: at-least-once. Validation against
  `clickstream.schema.json`; rejects go to `bronze/_dlq/`.
- **Orders:** the extractor, incremental on `order_id`, `>`, cursor saved after
  the write. Guarantee: at-least-once. It sees new orders only. It writes to
  `bronze/orders_pg/`, apart from the CSV-derived `bronze/orders/`, because the
  two have different column sets and types.
- **The other six tables** (`order_items`, `review`, `product_reviews`,
  `product`, `customer_shipping`, `shipping_details`): `extract_tables.py`, a
  full refresh that overwrites one file per table, so a re-run cannot duplicate.
  Secret columns (`pwd`, `card_no`, `cvv`, and `expiry_date`) are removed from
  the column list before the query is sent, and `check_secrets_excluded.py`
  reads the output back and fails if one is there. Rejected for these tables:
  a cursor, since none of them has a column I could trust for updates.
- **Updates and deletes:** not handled. **Planned, not built:** a daily full
  refresh of `product` (42,858 rows, about 4.8 MB as Parquet), where prices
  change and a cursor cannot see it; the other mutable tables are not yet
  decided.
- **Libraries:** `psycopg` 3 as the driver (plain SQL, no ORM), `confluent-kafka`,
  `pyarrow` to write Parquet (and to reach the bucket), `jsonschema` for the
  event schema.

## Consequences

- **Evidence:** consumer killed between write and commit: 9 files, 1,403 rows,
  1,203 distinct, **200 duplicates**, which is one flush of 200 rows. A date
  cursor moved by an `UPDATE`: the corrected order was **not** in the next
  sync, which read 24 rows, all new.
- **Delivery guarantees:** both pipelines are at-least-once. Silver has to
  deduplicate clickstream events on `event_id`. Orders in `bronze/orders_pg/`
  can contain a stale version of an order that was later corrected: that is a
  known inaccuracy, not a bug.
- **Cost of the cursor's blindness:** the warehouse would keep an order's old
  date or discount and an order that was deleted, with no error. For revenue
  that is wrong in a way found only by reconciliation.
- **Would force a change:** a business question that depends on corrections or
  cancellations (move `orders` to change data capture, with its slot and a
  reader to operate); a second schema version of the events (add a validator
  per version, as the consumer is written to allow); partitions that stay small
  at real volumes (batch less often).
- **Weaker than a connector:** the exclusion is in my code, not in a tool's
  configuration, so a later `SELECT *` would undo it and only the check script
  would notice. Full refresh also copies every row each time (415,047
  `order_items` rows today).
- **Not true yet:** nothing starts these two scripts; both run only when I run
  them until the scheduler of lesson 7. "No human in the loop" holds for the
  data path, not for starting it.
