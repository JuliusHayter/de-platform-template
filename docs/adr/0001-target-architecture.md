# ADR-0001: Adopt a two-tier architecture — object storage for bronze, a warehouse for silver and gold

- **Status:** accepted
- **Date:** 2026-10-12
- **Author:** Julius Hayter
- **Lesson:** L01

## Context

Albert's Marketplace runs on a single operational PostgreSQL database: the web
shop writes orders, lines, payments and stock to it continuously, and reviews
land there too. Analysts query it on demand with SQL, and a nightly CSV export
of selected tables is reconciled by hand in spreadsheets (see
[`data-flows.md`](../data-flows.md), flows 1-4). None of this database is a
warehouse, a lake, two-tier or a lakehouse: it integrates nothing, keeps no
history, and its model records orders rather than aggregating them.

This creates concrete problems: analytical queries add load to the database
that also serves live checkout traffic; duplicate orders are handled
differently by each report, so the same figure can disagree depending on who
computed it; only the current state is kept, so last March's price is gone;
and sensitive data (saved cards, passwords) sits in the same tables analysts
query. On top of this, the ML team wants a table of units sold per product,
per country, per day — a flow that does not exist yet (flow 5).

## Options considered

| Option | For | Against |
|---|---|---|
| Data warehouse only | Strong SQL tooling, mature governance and access control, good fit for structured, modelled reporting | Poor fit for unstructured data (review text, photos); loading raw data first requires modelling it before it even lands, which slows down bronze-style "keep everything" ingestion |
| Data lake only | Cheap, schema-on-read storage for any format (structured orders, review text, photos); keeps full history of raw files | No enforced structure or quality guarantees downstream; analysts and the ML team would query raw/semi-structured files directly, reintroducing the "everyone computes it their own way" problem |
| Two-tier (lake + warehouse) | Raw data lands untouched in object storage (bronze) before anything is modelled; a warehouse then holds one agreed, structured version for reporting and ML (silver/gold); clean separation keeps secrets out of the modelled layers | Two systems to run and keep in sync instead of one; some duplication of storage between bronze and the warehouse |
| Lakehouse | One system serving both raw and modelled data, with warehouse-like guarantees (ACID, schema enforcement) directly on lake storage; less duplication than two-tier | Newer tooling, fewer people on the team already know it; strong guarantees depend on correctly configuring the lakehouse engine, which adds operational risk for a small team |

## Criteria

- **Workload:** the two consumers are reporting (analysts) and machine
  learning (the wanted daily-demand table). Neither needs sub-second
  freshness, so both a warehouse-only and a two-tier setup score well here;
  a lake alone scores worse, since neither consumer wants to query raw files.
- **Data types:** orders and reviews are structured, but review text and
  photo links are not. A warehouse-only option handles the structured side
  well but forces unstructured data into a shape it doesn't naturally take.
  A lake, two-tier or lakehouse option handles both without compromise.
- **Freshness:** daily is enough for reporting and for the ML team's demand
  table — nothing in the data flows needs streaming. This removes any
  pressure toward architectures built for real-time ingestion, and favours
  the simpler options.
- **Team and skills:** the team is small. A warehouse-only setup is the most
  familiar and the cheapest to operate well. Two-tier, built on managed
  services, is close behind. A lakehouse scores lowest here: its stronger
  guarantees depend on operational maturity the team does not have yet.
- **Governance:** payment and password data must never leave the source
  system's trust boundary unredacted. A two-tier design can enforce this at
  the boundary between bronze and silver, keeping secrets out of every layer
  analysts or the ML team touch. A warehouse-only design, which models
  straight from the source, makes that boundary harder to draw.

## Decision

Adopt a two-tier architecture: object storage holds the bronze layer (raw
orders, lines, payments, stock, reviews, exactly as they arrive, nothing
lost), and a warehouse holds the silver layer (one agreed, deduplicated
version of each fact, with secrets stripped) and the gold layer (tables that
answer a named question, such as the ML team's daily units-sold-by-product-
by-country table). A lakehouse remains a defensible alternative once the team
has the operational skills to run one; it is not chosen now because the team
is small and better served by two well-understood, managed systems.

## Consequences

- **Easier:** analysts and the ML team read from modelled, deduplicated
  tables instead of the live operational database, removing both the load on
  checkout and the "two reports, two answers" problem. Raw data is never
  lost, so a modelling mistake in silver or gold can be recomputed from
  bronze instead of re-extracted from the source.
- **Harder:** two systems (object storage and the warehouse) must be
  provisioned, secured and kept in sync instead of one; the bronze-to-silver
  step that strips secrets and deduplicates orders becomes a new piece of
  pipeline that must be built and tested, not just a reporting query.
- **To watch:** that no raw table containing payment or password data is ever
  exposed past bronze; that the bronze-to-silver job stays the single place
  where duplicate orders are resolved, so figures don't start disagreeing
  again; and that storage costs between bronze (full raw history) and the
  warehouse (modelled layers) don't quietly duplicate more than intended.
