# Costs

Monthly cost of what exists, from published Google Cloud Storage prices read on
2026-10-29 (the figures given in exercise 1): Standard storage $0.020 per
GiB-month, Class A operations $0.005 per 1,000. Not re-checked against the
live price page; do that before the FinOps work in lesson 9. Sizes are read from the bucket (`gcloud storage du`: 73,401,661 B in 135 objects).

## Lesson 2: bronze

| Item | Quantity | Cost |
|---|---|---|
| Storage, Standard, 27 tables as zstd Parquet | 73.4 MB = 0.068 GiB | $0.0014 per month |
| Write operations (Class A), one upload per object | ~135 objects | $0.0007, once |
| Lifecycle | After 30 days, objects move to Nearline, then Coldline, then Archive | Storage cost falls; a class change is itself a Class A operation |

For comparison, partitioning the three big tables by day instead would be
5,052 objects and 128 MB: $0.0026 a month and $0.025 in writes, once. The
writes are 10 times the monthly storage, and they recur on every full reload.

The over-partitioning test I ran for the ADR wrote 8,680 extra objects (since
deleted): about $0.043 in writes, against $0.0007 a month to store the
32 MB it held. That is roughly 80 times the monthly storage. Operations, not storage, are the meter that
over-partitioning moves.

## If the data were 100 times larger

About 6.8 GiB, so $0.14 a month in storage. Writes stay at ~13,500 objects
($0.07, once) only if partitions grow with the data; if they stay monthly,
each partition is 100 times bigger and the object count is unchanged. Storage
is still cheap. What would start to cost money is querying: BigQuery bills
bytes processed, so a layout that scans all of it on every question matters
more than the bucket.

## Not included yet

BigQuery queries (lesson 4), network egress, and the project's other
resources. Extend this file every lesson.

## Lesson 3: ingestion

Same prices and date as above (Standard $0.020 per GiB-month, Class A
$0.005 per 1,000, read 2026-10-29). Sizes read from the bucket with
`gcloud storage du` after the consumer run ended.

| Item | Quantity | Cost |
|---|---|---|
| `bronze/orders_pg/`, 224,968 orders as zstd Parquet | 3.85 MB in 38 objects | $0.00007 per month |
| `bronze/clickstream/`, about 11,000 events so far | 1.17 MB in 51 objects | $0.00002 per month |
| `bronze/_dlq/` | 2.7 KB in 1 object | negligible |
| `bronze/<table>_pg/`, six tables as one file each | 28.7 MB | $0.0005 per month |
| Whole bucket now | 107.1 MB, was 73.4 MB | $0.0020 per month |
| Writes for the new objects, about 100 | | $0.0005, once |

Storage is still not the cost. The consumer's cost is operations: every flush is
a Class A write. At `BATCH=200`, writing the topic's 24,807 events took 151
files; at 5,000 per batch it takes a handful. If the producers sent a hundred
times more events, a small batch would mean about a hundred times more writes
and files, while storage would stay in cents. Batch size, not data size, is the
setting that controls the bill.

Not counted: the BigQuery cost of querying these files (lesson 4), and the
laptop that runs Kafka and PostgreSQL, which is not a cloud cost.

## Lesson 4: the warehouse

BigQuery, `europe-west1`, same date. Storage at the active logical rate of
$0.020 per GiB-month (taken from the Standard storage price above; BigQuery's
own page was not checked, and its first 10 GiB each month are free). Queries at
$7.50 per TiB with the first TiB each month free (see
[ADR-0004](adr/0004-warehouse-pricing.md)).

| Item | Quantity | Cost |
|---|---|---|
| Native tables, `warehouse_julius` (7 loaded tables plus 8 tuned copies of them) | 0.25 GiB | $0.005 per month, before the free allowance |
| Materialised views (`daily_demand`, `monthly_demand`) | 18.8 MB | included above |
| The measuring script (about 30 runs, cache off) and the table builds | well under 1 GB read in total | $0, inside the free TiB |
| One billing floor | every table read bills 10 MiB | $0.00007 |

Storage is not the cost and queries are not either, at this size. What the tuned
copies cost is the same data stored eight times for the sake of the measurements;
once a grain is chosen, the other copies (`order_items_day`, `order_items_year`,
`order_items_clustered`) can be dropped. If the data were a hundred times larger,
Q2 untuned would read about 1.1 GB and cost about $0.008 a run; tuned, about
$0.0007. The cap (1 GiB per query, $0.007) would then start to bind on the
untuned version, which is its purpose.

## Lesson 5: dbt

Same prices and date as above.

| Item | Quantity | Cost |
|---|---|---|
| One full `dbt build` (five tables, 33 s) | about 73 MiB processed | $0.0005, inside the free TiB |
| Tests, 62 per build | each reads a few MB; fractions of a cent in total | $0 |
| Storage, `l05_julius` | the five marts: 57.8 MB (fct_daily_demand 28.6, fct_order_items 22.2, dim_product 6.9) | $0.001 per month |
| Twelve views | nothing stored | $0 to keep; every read of one scans bronze (see [ADR-0005](adr/0005-materialisations.md): 4.8x a table) |

Cost is in reads, not storage. The one decision that moves it is views against
tables: reading `fct_order_items` as a view over the external tables took 28.1 MB
for a query that reads 5.9 MB from the table. A hundred times the data and a mart
read fifty times a day would be the difference between $0.96 and $0.20 a day for
that one query; the 1 GiB cap would trip on the view first (2.8 GB a read).

