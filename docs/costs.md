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
