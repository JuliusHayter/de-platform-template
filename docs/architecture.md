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
  kafka -->|"consume_clickstream.py: at-least-once, schema-checked"| clickstream
  kafka -.->|"rejected events"| dlq
  pg -.->|"change data capture: tried by hand, no pipeline"| bronze
  csv[CSV export, loaded by hand in L02] --> tables

  subgraph gcs[Cloud Storage: data-engineering-a-groupe-julius-bronze, europe-west1, uniform access]
    subgraph bronze[bronze/]
      tables[(27 tables, zstd Parquet<br/>dt=YYYY-MM on 3 of them)]
      orders_pg[(orders_pg/<br/>dt=YYYY-MM)]
      clickstream[(clickstream/<br/>dt=YYYY-MM-DD, by event_time)]
      dlq[(_dlq/clickstream/<br/>rejected events)]
    end
  end

  access{{Access today: project owners, editors and viewers via default legacy roles}} -.-> bronze
  bronze -->|planned| silver[(Silver — warehouse, not built yet)]
  silver --> gold[(Gold — warehouse, not built yet)]
  gold --> analysts[Analysts]
  gold --> ml[ML team: daily demand]
```

Two automated paths now write into bronze: the extractor (from PostgreSQL) and
the consumer (from Kafka). The third, change data capture, was run by hand in
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
| Silver | Deduplicated orders, customers and products, with payment and password data stripped | One agreed version of each fact; no secrets; history of changes over time, not just the current state | Pipeline jobs building gold tables |
| Gold | Tables that answer a named question: reporting tables for analysts, the daily units-sold-by-product-by-country table for the ML team | Each table answers one stated question and is safe to query directly | Analysts, ML team |

## Decisions

| ADR | Decision | Status |
|---|---|---|
| [0001](adr/0001-target-architecture.md) | Two-tier architecture: object storage for bronze, a warehouse for silver and gold | Accepted |
| [0002](adr/0002-bronze-layout.md) | Bronze as zstd Parquet, partitioned by month on the three transactional tables | Accepted |
| [0003](adr/0003-ingestion-modes.md) | Streaming consumer for clickstream, incremental cursor for orders, updates and deletes unhandled | Accepted |

## Change log

| Lesson | What changed |
|---|---|
| L01 | First version |
| L02 | Bronze built: bucket, layout, lifecycle and real access shown; silver and gold still planned |
| L03 | Two ingestion paths into bronze (extractor, consumer) with a dead letter queue; change data capture and Airbyte not built |
