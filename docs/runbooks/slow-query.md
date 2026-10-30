# Runbook: a query got slow

For whoever is on call at 23:00 and did not build this. A query that took
seconds now takes minutes, or its cost jumped. Work down the list; each step
says what it rules out. Stop at the first step that explains it.

Everything lives in BigQuery, project `data-engineering-a`, region
`europe-west1`, dataset `warehouse_julius`. Open
https://console.cloud.google.com/bigquery and make sure the project picker says
`data-engineering-a`.

## Healthy numbers, to compare against

Measured 2026-10-29, cache off, on the tuned tables:

| Query | Bytes processed | Notes |
|---|---|---|
| Q1 revenue by month (`order_items_p`) | 3,373,224 | |
| Q2 top 10 products (`order_items_pc`) | 1,000,888 | |
| Q3 average rating | 4,007,592 | one stage, 29 ms, 58 slot-ms |
| Daily demand since August (`daily_demand`) | 366,940 | |

These tables are small enough that every query is done in well under a second. If
yours takes minutes, something is wrong with the query or the data, not the size.

## 0. Is it really slower? (2 minutes)

*Rules out: a comparison against a run that was never that fast.*

1. Find the fast run you are comparing against: open **Personal history** (bottom
   panel in the console), click that job, open **Job information**.
2. Look at **Bytes processed**. If it says **0 B** for a query that obviously
   reads a table, the fast run was served from cache. Nothing got slower; it was never
   that fast.
3. Run the slow query again with the cache off: **More, Query settings, untick
   "Use cached results", Save**. Compare against the healthy table above.

Stop here if the numbers match. Say so in the ticket and close it.

## 1. Did the query lose its partition filter? (3 minutes)

*Rules in: a changed query. Rules out: a change in the data.*

1. Open the job, **Job information**. Compare **Bytes processed** with the table
   above. A jump of 3x or more points here.
2. Read the SQL. Is there still a `WHERE order_date ...` on the table's
   partition column? Was it moved into a subquery, or compared with a value that
   comes from another table or from `CURRENT_DATE()` through a function the
   engine cannot work backwards from? A filter that depends on a value found
   while the query runs does not prune.
3. Paste the query into the editor and read the line at the top right ("This
   query will process N bytes"). Add the plain filter back and watch N fall.

*If N falls:* the query changed. Put the filter back.

## 2. Has the table grown past its partition grain? (3 minutes)

*Rules in: a data change. Rules out: a query change.*

Run:

```sql
SELECT table_name, COUNT(*) AS partitions,
       CAST(ROUND(AVG(total_logical_bytes)) AS INT64) AS avg_bytes
FROM `data-engineering-a.warehouse_julius.INFORMATION_SCHEMA.PARTITIONS`
WHERE table_name LIKE 'order_items_%'
GROUP BY table_name;
```

Healthy: `order_items_p` 37 partitions at 485,855 bytes on average. A partition
count that has doubled with the average halved means a finer grain than the data
suits; a partition average that has grown 10x means the month grain is now too
coarse for a one-day question. Either way, the fix is a new grain, not a retry.

## 3. Which stage is slow? (5 minutes)

*Rules in: a join, sort or aggregate that dominates. Rules out: a read problem.*

1. Open the job, click the **Execution details** tab (next to Job information,
   not "Execution graph").
2. In the stage table, find the stage whose **Elapsed** time is far above its
   neighbours. Write down its name (for example `S03: Join+`).
3. Compare **Records read** with **Records written** on that stage. If it reads
   millions and writes a fraction, the work is thrown away after being done:
   filter earlier, before the join.

## 4. Is one worker holding up the stage? (3 minutes)

*Rules in: skew. Rules out: "needs more machines".*

1. On the stage from step 3, click the arrow to expand it.
2. The stage lists timings for the average worker and for the slowest one (wait,
   read, compute, write). The slowest being 3x the average or more is skew: one key holds far more rows than the
   others. In this data that is the best-selling product, which appears in all 37
   months.
3. More slots will not help: the stage ends when its slowest worker does. Filter
   earlier, aggregate before the join, or split the hot key.

## 5. Did the data change shape? (5 minutes)

*Rules in: a change upstream. Rules out: a problem in this query.*

1. Take the same query on the same date range as a run you trust. In
   **Execution details**, compare **Records read** and **Records written** at
   the first and last stage with the earlier run.
2. If rows in or out moved a lot for the same range, the data is different:
   check the bucket (`gs://data-engineering-a-groupe-julius-bronze/bronze/`),
   `docs/ingestion-failure-modes.md` for the duplicate and late-event cases, and
   whether the ingestion jobs ran twice.

## 6. Is the materialised view being used? (2 minutes)

*Rules in: a stale or bypassed view.*

On a query that reads `daily_demand`, open **Job information** and check that
the bytes are near the table above. If a query that should hit the view reads
around 10 MB instead, the view was bypassed or lost its partitioning (an
unpartitioned copy read 9,995,468 bytes for one month). Check
`bq show data-engineering-a:warehouse_julius.daily_demand`: it must still say
`MONTH (field: order_date)` and `p_id`.

## When to stop and escalate

Escalate to the project owner, with the job id and what you checked, when:

- you have spent **30 minutes** and no step above explained it; or
- the query fails with `Query exceeded limit for bytes billed` and raising the
  cap is the only way through (the cap is a decision, not an obstacle: a query
  that needs more than 1 GiB on this project is a finding, not a retry); or
- the bytes billed over the day look large, which only the owner can check in
  `INFORMATION_SCHEMA.JOBS_BY_PROJECT`.

Do not delete tables or the view to see what happens.
