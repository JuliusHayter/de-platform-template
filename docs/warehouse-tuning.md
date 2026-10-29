# Warehouse tuning

BigQuery project `data-engineering-a`, dataset `warehouse_julius` (europe-west1),
built from the bronze bucket. Every number here was measured on 2026-10-29 by
[`warehouse/measure.py`](../warehouse/measure.py), which runs each query with
the **cache off** and reads **bytes processed** from the finished job. Bytes
billed are not used: BigQuery bills at least 10 MiB per table read, and every
table here is smaller, so they would all look the same.

Costs use $7.50 per TiB (the price given for this project; see
[ADR-0004](adr/0004-warehouse-pricing.md)): `bytes / 2^40 * 7.50`.

The SQL is in [`warehouse/`](../warehouse): `01_native_tables.sql`,
`02_tuned_tables.sql`, `03_daily_demand_view.sql`, `04_monthly_demand_view.sql`.

## 1. What is loaded, and what is not

Bronze stays in the bucket. External tables in `bronze_julius` read the lesson 2
Parquet; the seven below are copied into native tables.

| Loaded (native) | Rows | Why |
|---|---|---|
| `orders` | 222,644 | Q1, Q2 and the star schema's date |
| `order_items` | 408,560 | Q1, Q2, daily demand. Joined to `orders` for `order_date`, which it does not have. |
| `review`, `product_reviews` | 111,322 each | Q3 |
| `product`, `customer_shipping`, `shipping_details` | 42,858 / 200,001 / 200,001 | Lesson 5's dimensions; loaded now while bronze is open |

The only change from bronze is a type: `order_date` arrives as a string and is
parsed to a `DATE` (0 nulls produced, range 2023-09-15 to 2026-09-14). The
exporter's `Unnamed: 0` column is kept, as `Unnamed__0`, because BigQuery cannot
hold the original name.

**Deliberately left external:**

- `customer`, `payment_details` and the other L02 tables no question needs yet.
  The first two still hold passwords and card data in the lesson 2 copies, and
  loading them into a second system would spread that.
- `bronze/*_pg/` and `bronze/clickstream/` (lesson 3). They are live and
  append-only, with different columns from the CSV tables; the numbers below
  use the fixed lesson 2 history so they can be compared with the course's.
  Silver will decide how they join in.

## 2. Tuning, and what each change was worth

`order_items` is 17,976,640 bytes in every variant; only the layout changes.

| Table | Change | Query | Bytes before | Bytes after | Ratio |
|---|---|---|---|---|---|
| order_items | partition by month | Q1 revenue by month | 9,805,440 | 3,373,224 | 2.9x |
| order_items | partition by day | Q1 | 9,805,440 | 3,256,368 | 3.0x |
| order_items | partition by year | Q1 | 9,805,440 | 5,223,096 | 1.9x |
| order_items | partition by month | Q2 top 10 products, last quarter | 11,439,680 | 1,000,888 | 11.4x |
| order_items | + cluster by `p_id` | Q2 | 1,000,888 | 1,000,888 | **1.0x** |
| order_items | cluster by `p_id` only | Q2 | 11,439,680 | 11,439,680 | **1.0x** |
| review, product_reviews | cluster on the join keys | Q3 rating per product | 4,007,592 | 4,007,592 | **1.0x** |
| order_items | partition by month + cluster | lookup of one rare product | 8,171,200 | 380,220 | 21.5x |
| order_items | partition by month + cluster | lookup of the best-seller | 8,171,200 | 8,171,160 | 1.0x |

### Grain: month

| Grain | Partitions | Average partition |
|---|---|---|
| day | 1,096 | 16,402 bytes |
| month | 37 | 485,855 bytes |
| year | 4 | 4,494,160 bytes |

I kept **month**. Day buys almost nothing over it for Q1 (3.0x against 2.9x) and
builds 1,096 partitions of 16 KB each, the over-partitioning failure of lesson 2
again. Year loses on Q1 (1.9x), since a twelve-month window has to read the whole
current and previous year.

### The changes that bought nothing

- **Clustering for Q2** is 1.0x, with or without partitioning. Q2 asks about all
  the products and filters on none, so there is no block to skip. Clustering
  skips blocks that cannot hold the value you filter on; it cannot help a
  question about every value. On the best-seller, which sells in all 37 months,
  the clustered table reads 8,171,160 bytes against 8,171,200 untuned.
- **Clustering for Q3** is 1.0x. Neither review table has a date to partition on,
  and clustering on the join keys saves nothing at 111,322 rows. Q3 bills 20,971,520 bytes, twice the floor, because it reads two
  tables.
- **A clustered-only table** (no partition) reads 8,171,200 bytes for the rare
  product, the same as untuned. At 18 MB it is a single block, so there is
  nothing to skip.

### A result I did not expect

For the rare product (4 order lines), the real bytes processed are:

| Layout | Bytes processed | Ratio to untuned |
|---|---|---|
| untuned | 8,171,200 | 1x |
| cluster only | 8,171,200 | 1x |
| month + cluster | 380,220 | 21.5x |
| day + cluster | 25,900 | 315x |
| year + cluster | 80 | 102,140x |

All four layouts return the same answer (16 units on 4 lines). I expected the
fine grains to win and the coarse one to do nothing, which is the opposite of the
year row. My hypothesis is that clustering prunes inside a partition, and a
4.5 MB year partition has enough blocks to prune while a 16 KB day partition is
a single block that has to be read whole; I did not test it. What I can say: the
**dry run cannot show this**. For clustered tables the estimate is an upper
bound (8,171,200 for all of them), and the real figure only appears on the
finished job. So the rule "the estimate equals the actual" holds for partition
pruning and fails for clustering.

## 3. The materialised view

`daily_demand` is the ML team's table: units and revenue per product per day,
partitioned and clustered like `order_items_pc`.

| | Rows | Per row |
|---|---|---|
| order lines | 408,560 | 1.00 |
| (product, day) | 356,981 | **1.14** |
| (product, month) | 165,141 | 2.47 |
| product | 41,323 | 9.89 |

The ratio is near 1: grouping by product and day removes 14% of the rows. The
view is 12,851,316 bytes; aggregating the untuned table reads 14,708,160. It
saves **1.14x** on a full read. I built it anyway, and I kept it, for two
reasons. The ML team needs the daily grain, so a coarser view is not a
substitute. And what it buys is not bytes but work: the aggregation is stored
and refreshed incrementally.

The part that matters is what I got wrong first. My first version had no
`PARTITION BY`, and for one month of data it read **9,995,468** bytes, 24 times
more than the same filter on the partitioned base table (422,800). Partitioned
and clustered like its base, the view reads **366,940**. A view that does not
inherit the partitioning is worse than no view.

The coarser option exists as `monthly_demand` (165,141 rows, 5,945,076 bytes,
2.2x smaller than daily), to show the ratio moving. Nothing reads it.

## 4. Three queries, costed

The three questions this project needs (lessons 4 and 5 build on them). "Today"
is `DATE '2026-09-14'`.

| # | Question | Untuned | Tuned | Cost, untuned | Cost, tuned | Ratio |
|---|---|---|---|---|---|---|
| Q1 | Revenue by month, last twelve months | 9,805,440 | 3,373,224 (month) | $0.000067 | $0.000023 | 2.9x |
| Q2 | Ten products with most units, last quarter | 11,439,680 | 1,000,888 (month) | $0.000078 | $0.000007 | 11.4x |
| Q3 | Average rating per product, over 50 reviews | 4,007,592 | 4,007,592 | $0.000027 | $0.000027 | 1.0x |

Everything rounds to nothing, and sits inside the free first TiB each month. The
ratios are what carry over to a table a thousand times bigger: Q2 would go from
about $0.08 to $0.007 a run. The SQL is in
[`warehouse/measure.py`](../warehouse/measure.py).

## 5. Why the numbers are still wrong

Q1 asked a second time, changing only which orders count:

| Definition | Orders | Revenue, 12 months |
|---|---|---|
| The export as it is | 74,417 | 13,065,805.92 |
| Originals only (`order_id <= 111322`) | 37,147 | 6,523,907.20 |

Half. Nothing in this page says which one is right, and no layer between the
bucket and these aggregates does either. That is silver, in lesson 5.

## 6. The cap

`maximum_bytes_billed` is set in three places:

| Where | Value | Why |
|---|---|---|
| `warehouse/measure.py`, on every query it runs | 1,073,741,824 (1 GiB) | The biggest query in this project bills 21 MB; 1 GiB is 50 times that, and stops a runaway at $0.007 |
| `warehouse/bigqueryrc` | the same | A default for anything run with `bq --bigqueryrc=warehouse/bigqueryrc query ...` |
| The console | not saved: Query settings, Advanced, Maximum bytes billed, per session | Console settings are per user and per tab, so they are not a control |

I could not set a project-wide default: that is a custom quota in the console
and my account has no access to it. So the cap is only as strong as the habit of
using the rc file, and a query run any other way is uncapped.

**What it looks like when it trips** (cap of 1,000,000 bytes, verbatim):

```
Query exceeded limit for bytes billed: 1000000. 10485760 or higher required.
```

The job ended with reason `bytesBilledLimitExceeded` and has no `totalBytesBilled`:
a refused query costs nothing. The smallest cap that can ever run is
10,485,760 bytes (10 MiB), the billing floor. I confirmed the rc file trips the
same way with a cap of 1,000,000, and that a lookup runs under a cap of
10,485,760.

## 7. Reproducing

```bash
bq --location=europe-west1 query --nouse_legacy_sql < warehouse/01_native_tables.sql
bq --location=europe-west1 query --nouse_legacy_sql < warehouse/02_tuned_tables.sql
bq --location=europe-west1 query --nouse_legacy_sql < warehouse/03_daily_demand_view.sql
python warehouse/measure.py
```

`01` needs the external tables in `bronze_julius` (one per bronze table, with
hive partitioning on `orders` and `order_items`).
