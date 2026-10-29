# Architecture

> Update this page at the end of every lesson. It is the diagram you present at
> the oral defence.

## Context

Albert's Marketplace needs its order, stock and review data turned into
trustworthy reports and, eventually, a daily demand forecast, without
burdening the operational database that serves live checkout traffic.
Analysts need one agreed figure per question instead of a report per tool,
and the ML team needs a daily, historised table it does not have today.
Daily freshness is enough everywhere; nothing in the current data flows needs
real-time delivery. Payment and password data must never leave the source
system unredacted, which constrains every layer built on top of it.

## Architecture as built

```mermaid
flowchart LR
  checkout[(Web shop: checkout)] --> pg[(PostgreSQL: operational DB)]
  reviews[(Web shop: reviews)] --> pg
  checkout -->|JSON events| kafka[[Kafka topic: clickstream]]

  pg -->|"extract_orders.py: incremental, order_id cursor, new rows only"| orders_pg
  pg -->|"extract_tables.py: full refresh of 6 tables, secrets left out"| tables_pg
  kafka -->|"consume_clickstream.py: at-least-once, schema-checked"| clickstream
  kafka -.->|"rejected events"| dlq
  pg -.->|"change data capture: tried by hand, no pipeline"| bronze
  csv[CSV export, loaded by hand in L02] --> tables

  subgraph gcs[Cloud Storage: data-engineering-a-groupe-julius-bronze, europe-west1, uniform access]
    subgraph bronze[bronze/]
      tables[(27 tables, zstd Parquet<br/>dt=YYYY-MM on 3 of them)]
      orders_pg[(orders_pg/<br/>dt=YYYY-MM)]
      tables_pg[(6 more tables as table_pg/<br/>one file each)]
      clickstream[(clickstream/<br/>dt=YYYY-MM-DD, by event_time)]
      dlq[(_dlq/clickstream/<br/>rejected events)]
    end
  end

  access{{Access today: project owners, editors and viewers via default legacy roles}} -.-> bronze
  bronze -->|"external tables, read on every query"| ext[bronze_julius: external tables]
  ext -->|"copy 7 tables, cast order_date"| wh[(BigQuery warehouse_julius: 7 native tables<br/>order_items partitioned by month + clustered by p_id)]
  wh --> mv[(daily_demand: materialised view<br/>partitioned like its base)]
  ext -->|"dbt: staging, one defect fixed per source"| silver[(Silver: l05_julius<br/>8 staging + 4 intermediate views<br/>int_orders: one definition of an order)]
  silver -->|"dbt: tables, grain declared and tested"| gold[(Gold: l05_julius<br/>fct_order_items, fct_daily_demand<br/>dim_product, dim_country, dim_date)]
  gold --> analysts[Analysts]
  gold --> ml[ML team: daily demand]
  tests{{"62 tests + 2 freshness checks<br/>docs/acceptance-criteria.md"}} -.-> gold
```

Silver and gold now exist (lesson 5): a dbt project reads bronze through
external tables and builds the star schema in `l05_julius`. Revenue now has one
definition, which is a rule that under-removes duplicate orders, so it is a better
answer and not yet the true one ([`acceptance-criteria.md`](acceptance-criteria.md)).

Bronze is queryable through BigQuery (lesson 4): seven tables are copied into
native, tuned tables and one materialised view serves the ML team's daily
demand. It reads straight off bronze, with no definition of an order between
them, so "revenue" has two answers (13.07 M and 6.52 M EUR over twelve months;
see [`warehouse-tuning.md`](warehouse-tuning.md)). Every query has a byte cap.

Three scripts now write into bronze: two extractors (from PostgreSQL) and the
consumer (from Kafka). The third, change data capture, was run by hand in
exercise 1 and has no pipeline, so its arrow is dashed. There is no Airbyte
connector. Neither script is scheduled yet; I start them by hand until
lesson 7. Access is still the project default
([`infra/iam.md`](../infra/iam.md)). Choices are argued in
[ADR-0002](adr/0002-bronze-layout.md) and
[ADR-0003](adr/0003-ingestion-modes.md); failure behaviour is in
[`ingestion-failure-modes.md`](ingestion-failure-modes.md).

## Layers

| Layer | What lands here | What it guarantees | Who reads it |
|---|---|---|---|
| Bronze | 27 tables from the operational database as zstd Parquet in `europe-west1`; `orders`, `order_items`, `payment` partitioned by month | Nothing that arrived is lost or altered; full raw history is kept, including rows later found to be duplicates or errors. Holds secrets (passwords, card data), flagged in the [data dictionary](data-dictionary.md) | Intended: silver job only, no direct analyst or ML access. Today: the whole project (see `infra/iam.md`) |
| Silver | Built (L05): staging views fixing one named defect each, and intermediate views holding the joins that decide something. Twin orders collapsed by one rule; no contact or payment data selected | One agreed version of each fact, with the limit that the twin rule under-removes. **No history of changes**: there are no snapshots | Pipeline jobs building gold tables |
| Gold | Tables that answer a named question: reporting tables for analysts, the daily units-sold-by-product-by-country table for the ML team | Each table answers one stated question and is safe to query directly | Analysts, ML team |

## Decisions

| ADR | Decision | Status |
|---|---|---|
| [0001](adr/0001-target-architecture.md) | Two-tier architecture: object storage for bronze, a warehouse for silver and gold | Accepted |
| [0002](adr/0002-bronze-layout.md) | Bronze as zstd Parquet, partitioned by month on the three transactional tables | Accepted |
| [0003](adr/0003-ingestion-modes.md) | Streaming consumer for clickstream, incremental cursor for orders, updates and deletes unhandled | Accepted |
| [0004](adr/0004-warehouse-pricing.md) | BigQuery on demand with a per-query byte cap | Accepted |
| [0005](adr/0005-materialisations.md) | Views for staging and intermediate, tables for marts | Accepted |

## Change log

| Lesson | What changed |
|---|---|
| L01 | First version |
| L02 | Bronze built: bucket, layout, lifecycle and real access shown; silver and gold still planned |
| L03 | Two ingestion paths into bronze (extractor, consumer) with a dead letter queue; change data capture and Airbyte not built |
| L04 | Warehouse added: bronze queryable, 7 native tables, month partitions, a materialised view, a byte cap. Slow-query runbook in `docs/runbooks/` |
| L05 | Silver and gold built with dbt in `transform/`: sources, staging, one definition of an order, a star schema with declared and tested grains, 62 tests and freshness. Lineage in `docs/lineage.md` |
