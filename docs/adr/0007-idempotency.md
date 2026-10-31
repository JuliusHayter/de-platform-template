# ADR-0007: Make reruns safe by overwriting, replacing and a saved cursor; MERGE where a key is trusted

- **Status:** accepted
- **Date:** 2026-10-31
- **Author:** Alexandro Bizeul
- **Lesson:** L07

## Context

Airflow retries a task when it fails and a person clears it when something looks wrong,
so every task will run for the same interval more than once. The question is what the
second run does. Lesson 4 showed what duplicates do to revenue, and BigQuery does not
enforce uniqueness, so a primary key stops nothing.

Three tasks write ([`docs/orchestration.md`](../orchestration.md)):

| Task | Writes | Mechanism chosen |
|---|---|---|
| `extract_tables` | one Parquet object per table | **Overwrite the same object path** |
| `extract_orders` | new Parquet files per run | **Cursor on `order_id`, saved after the write** |
| `dbt_build` | dbt tables and views | **`CREATE OR REPLACE`** (dbt's table materialisation) |

## Options considered

| Option | Works when | Breaks when |
|---|---|---|
| Delete, then insert, by partition | the interval maps to one partition | an interval spans partitions, or the delete succeeds and the insert fails |
| **MERGE on a business key** | you have a key you trust | the key is not unique, which lesson 5's tests exist to catch. Not used here: there is no BigQuery load task, because the extractors write Parquet to the bucket |
| Write a new table, then swap | the table is small enough | storage doubles during the swap |
| **Overwrite one object** | the output is a whole table, small enough to rewrite | the table grows until a full copy is slow or costly |
| **Cursor saved after the write** | the source has a column that only grows | rows are updated in place, or two machines hold different cursors |
| Accept duplicates | never, here | always: lesson 4 |

## Decision

- `extract_tables`: **overwrite**. Measured: a second run left `product_pg` at
  42859 rows (42859 after the first).
- `dbt_build`: **replace**. Revenue was 35355484.83 after one run and 35355484.83 after two.
- `extract_orders`: **a cursor**. `bronze/orders_pg` held 260486 rows after one run and
  260486 after two.

Where a MERGE would go: if the extractors are replaced by a task that loads into BigQuery,
that load merges on `order_id` for orders and on `(order_id, p_id)` for lines, which are the
keys lesson 5 tests as unique.

## The one I am least sure about: `extract_orders`

It is **at-least-once, not idempotent**, in four ways I can name:

1. The cursor is saved after the write. If the container dies between the two, the rerun
   writes that batch again.
2. The cursor is a file on the machine that runs the task. A second machine, or a lost
   volume, starts at 0 and writes every order again (hazard 2 in
   [`docs/orchestration.md`](../orchestration.md) says what this run saw).
3. It sees new rows only: an UPDATE or DELETE in the source never reaches it
   ([ADR-0003](0003-ingestion-modes.md)).
4. Two runs at once both start from the same cursor. Observed once: a scheduled run started
   while a manual one was extracting, and `bronze/orders_pg/` ended with 445,563 rows for 259,014
   orders ([`docs/orchestration.md`](../orchestration.md), hazard 1). `max_active_runs=1` does not cover a run
   started by `airflow dags test`, and a back-fill runs its runs at the same time: the three runs of
   this drill finished their tasks in the same second, and only found nothing to extract because the
   cursor was already at the end.

Nothing reads `bronze/orders_pg/` yet, which is the only reason none of this has cost
anything.

## Consequences

- A person can clear any task in the UI and expect the same end state, except
  `extract_orders`, where they should read the first line of
  [`runbooks/failed-run.md`](../runbooks/failed-run.md) first.
- Back-filling is safe for `extract_tables` and `dbt_build` and does nothing useful for
  `extract_orders`, because the period selects no data (measured:
  260486 rows before a three-run back-fill, 260486 after).

## What would change my mind

- **Reads of `orders_pg` by dbt or anyone else.** Then the cursor moves off the local volume
  into a bucket object, and the write is named by the interval so a rerun overwrites it.
- **A table too big to rewrite.** Then `extract_tables` moves to a cursor or to partition
  replacement, with the delete-then-insert failure window that comes with it.
- **A load into BigQuery.** Then MERGE on the key, as above.
