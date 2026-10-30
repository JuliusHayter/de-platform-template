# ADR-0005: Staging and intermediate models are views, marts are tables

- **Status:** accepted
- **Date:** 2026-10-29
- **Author:** Julius Hayter
- **Lesson:** L05

## Context

The dbt project in [`transform/`](../../transform) builds twelve views and five
tables from bronze in BigQuery. The choice is one block in `dbt_project.yml`:
folders `staging/` and `intermediate/` are views, `marts/` are tables. Nothing in
the SQL says so, and in six months the config is the only evidence.

Two facts decide it. Bronze is read through **external tables**, so every read of
a view over it scans Parquet in the bucket again. And the marts are read far more
often than they are built: the ML team reads daily demand every morning, and a
full rebuild is one run.

Measured on 2026-10-29: a full `dbt build` takes 33 seconds and processes about
73 MiB building the five tables (fct_order_items 41.6, fct_daily_demand 15.5,
dim_product 9.8, dim_country 6.2, dim_date 0), roughly $0.0005 at $7.50 per TiB.

## Options considered

| Option | For | Against |
|---|---|---|
| Everything as views | Always fresh; nothing stored | Every consumer pays the whole scan, every time |
| Everything as tables | Fast and cheap to read | Stale between runs; every layer stored a second time for no reader |
| **Views, then tables** | Staging and intermediate are always current and cost nothing to keep; marts are cheap to read | A rebuild step; marts are only as fresh as the last run |
| Incremental marts | Cheap rebuilds at scale | "New" has to be defined, and late rows handled (see below) |

## Evidence

The same revenue-by-month query over twelve months, run for real with the cache
off (a dry run reports 0 bytes on views over external tables, so it cannot be
used here):

| `fct_order_items` as | Bytes processed |
|---|---|
| a table (what we built) | 5,891,632 |
| a view over the staging views and the external tables | 28,088,162 (4.8x) |

At this size both are fractions of a cent. The ratio is what carries: a mart read
fifty times a day as a view would scan bronze fifty times.

## Decision

Staging and intermediate: **views**. Marts: **tables**, rebuilt by `dbt build`.

What I give up: the marts are as old as the last run. Today nothing schedules
that run (lesson 7), so they are as old as the last time someone typed
`dbt build`. The source freshness check reports this honestly: orders and
payments are 45 days behind because bronze is a static export.

## Consequences

- A change to staging or intermediate SQL is live the moment it is saved; a change
  to a mart needs a rebuild. People will forget the second.
- Views over external tables re-read the bucket on every mart build. Native bronze
  copies would be cheaper (lesson 4's `warehouse_julius`), at the cost of a second
  copy. I did not make that move because it would put a load step between bronze
  and dbt that is not in the architecture yet.

## What would change my mind

- **A rebuild that takes an hour.** Today it takes 33 seconds. Past about ten
  minutes, `fct_order_items` and `fct_daily_demand` move to **incremental**, and
  the cost is real: "new" must be defined (by `order_date`, with a lookback), and
  `int_orders` is not a row-by-row operation. A twin can be placed up to four days
  after its original, so an incremental run would have to re-read at least the last
  five days, not just today.
- **A consumer that needs minute-fresh data.** Then the mart cannot be a table
  rebuilt daily. Streaming the clickstream already gives sub-minute data; the
  orders marts would need change data capture (ADR-0003), which this project does
  not run.
- **A mart read once a week.** Then a view would cost less than storing and
  rebuilding it; `dim_country` (6 rows) is already close to that line, and is a
  table only to keep the rule simple.
