# ADR-0002: Bronze as zstd Parquet in one regional bucket, partitioned by month on the transactional tables

- **Status:** accepted
- **Date:** 2026-10-29
- **Author:** Julius Hayter
- **Lesson:** L02

## Context

[ADR-0001](0001-target-architecture.md) put bronze in object storage. This ADR
fixes how the files are laid out. The export is 27 CSV tables, 206 MB in total,
from three years of orders (2023-09-15 to 2026-09-14, 1,096 distinct days).
`order_items` has 408,560 rows, `orders` and `payment` 222,644 each. Bronze
keeps what arrived: no cleaning, no deduplication, no dropped column.

Consumers are pipeline jobs only (silver). The one query shape we know of is
the ML team's: units per product per day, filtered on a date range.
The bucket is `gs://data-engineering-a-groupe-julius-bronze`, which already
existed in `europe-west1` with uniform access.

All figures below are from my own runs of the exercise-1 scripts on the real
export (pandas + pyarrow) and from the bucket and BigQuery.

## Options considered

| Option | For | Against |
|---|---|---|
| CSV as exported | Nothing to do; human-readable | 10.4 MB for `order_items` against 2.5 MB; no types, no column statistics, every query reads every column |
| Parquet, unpartitioned | Smallest (2.5 MB, 1 object) | Every query opens the whole table, whatever date range it asks for |
| Parquet, `dt=YYYY-MM-DD` | Matches the ML query (daily) | 1,966 objects and 26.4 MB for `order_items`: ~10x the single file, because each tiny file carries its own footer |
| Parquet, `dt=YYYY-MM-DD/p_id=...` | Finest pruning | One month alone: 8,649 objects and 32.7 MB against 31 objects and 0.37 MB (279x the objects, 88x the bytes) for the same 9,893 rows |
| **Parquet, `dt=YYYY-MM`** | 36 partitions of ~11,000 rows; 37 objects and 5.7 MB for `order_items` | Day filters are not pruned by partition, only by row-group statistics |

One month (2026-08, 9,893 rows) written two ways, uploaded to the bucket and
queried through BigQuery external tables (same `SUM(qty)` over 7 days, cache
off, 3 runs each, times read from `INFORMATION_SCHEMA.JOBS_BY_USER`):

| | `dt=` only | `dt=` and `p_id=` | Ratio |
|---|---|---|---|
| Objects | 31 | 8,649 | 279x |
| Bytes | 372,214 | 32,662,322 | 88x |
| Query, median elapsed | 263 ms | 875 ms | 3.3x |
| Bytes processed | 17,056 | 17,056 | 1x |

The bill for the query is the same; the damage is in storage, object count and
time. Codec, on `order_items` as one file: CSV 10,373,925 B; snappy 3,546,854 B (2.9x
smaller); zstd 2,540,868 B (4.1x smaller, 28% below snappy).

## Criteria

- **Bytes stored:** the layout must not be bigger than the CSV it replaces.
  Daily partitions fail this on `orders` (22.8 MB of Parquet against 13.3 MB
  of CSV) and `payment` (23.8 MB against 15.0 MB).
- **Object count:** per-file cost (listing, opening, footer) does not depend on
  how much data a query asked for, and each upload is a Class A operation.
- **Filtered by a real query:** the key must be a column consumers filter on.
  Only dates qualify; `p_id` is filtered on too, but has 42,858 values.
- **Fidelity:** nothing dropped, nothing rewritten.

## Decision

One bucket in `europe-west1` with uniform access. Each source table is written
as zstd-compressed Parquet under `bronze/<table>/`. `orders`, `order_items` and
`payment` are partitioned by `dt=YYYY-MM`, taken from `order_date` (for
`order_items`, through `orders.order_id`) and `created_at`; the other 24 tables
are one file each. `dt` is added as a partition column; every source column is
kept as arrived.

## Consequences

- **Easier:** 135 objects and 73.4 MB (read back from the bucket) for the whole export, against 5,052
  objects and 128 MB if the three big tables were partitioned by day. Silver
  can read one month at a time, and a rebuild never touches the source database.
- **Harder:** a one-day query reads one month of that table; at this size that
  is a few MB, which is cheaper than opening 30 files. External tables need
  `WITH PARTITION COLUMNS (dt STRING)` with a string month, not a `DATE`.
- **Would force a rewrite:** monthly partitions growing past roughly 100 MB
  (about a hundredfold more data), where daily becomes worth its footers; a
  consumer that filters on another column such as country; or a codec the
  warehouse cannot read.
- **Not measured:** the monthly layout against daily on the real query (one
  day of `order_items`). Daily would need the whole three-year table written
  both ways; the sizes above are enough to argue the choice.
- **Not decided here:** `dt` for `order_items` comes from a join, so a line
  whose order is missing from `orders` has no month. Lesson 5 handles that; bronze
  would write it to `dt=__HIVE_DEFAULT_PARTITION__`.
