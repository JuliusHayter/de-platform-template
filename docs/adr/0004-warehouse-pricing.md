# ADR-0004: Run the warehouse on demand, with a per-query byte cap

- **Status:** accepted
- **Date:** 2026-10-29
- **Author:** Julius Hayter
- **Lesson:** L04

## Context

[ADR-0001](0001-target-architecture.md) put silver and gold in a warehouse;
this project uses BigQuery in `europe-west1`. BigQuery bills in one of two ways:
**on demand**, per byte read, or **capacity** (editions), per slot-hour reserved
or autoscaled. The choice sets how an expensive query shows up on the bill.

The tables are small (the biggest, `order_items`, is 18 MB) and are measured in
[`warehouse-tuning.md`](../warehouse-tuning.md).

## Options considered

| Option | For | Against |
|---|---|---|
| **On demand** | No commitment; a project that sits idle costs nothing; the first TiB each month is free | One careless query on a big table has no ceiling of its own (a `SELECT *` on a public 3.5 TiB table is $26 from a single click) |
| Capacity, autoscaled (Standard edition) | A fixed ceiling on spend: you set the maximum slots | A minimum charge even for a one-second query; slots idle between jobs are still billed; needs a reservation to be set up and understood |
| Capacity, committed (Enterprise) | Cheapest per slot-hour at high steady use | One- or three-year commitment, for a workload that does not exist yet |

## The workload, in numbers

Estimated, since the project has run no real analyst load yet:

| | Per day | Bytes each | Per month |
|---|---|---|---|
| Analyst queries | 20 | 10 MB (Q1, Q2, Q3 above: 1 to 11 MB) | 6 GB |
| Daily-demand refresh for the ML team | 1 | 1 MB | 30 MB |
| Lesson 5 model builds | 10 | 60 MB (scans the four big tables) | 18 GB |
| **Total** | | | **about 24 GB, or 0.023 TiB** |

Concentration in time: working hours, with a build burst in the morning. No
night load. On demand, 24 GB is $0, since it is inside the free TiB.

## The crossover arithmetic

On demand costs $7.50 per TiB after the first free TiB (the price given for this
project; Google's public list showed $6.25 when I looked on 2026-10-29, and I
could not confirm which applies to `europe-west1`, so both are shown).

Capacity is priced per slot-hour. The pay-as-you-go list rates I found were
$0.04 (Standard) and $0.06 (Enterprise) per slot-hour. I assume autoscaling
moves in steps of 50 slots; I did not verify that, and it changes the numbers
below proportionally.

| Capacity usage | Monthly cost at $0.04 | On-demand TiB that costs the same | At $7.50 | At $6.25 |
|---|---|---|---|---|
| 50 slots, 1 hour a day | $60 | 8 TiB, plus the free one | 9 TiB | 10.6 TiB |
| 50 slots, 8 hours a day | $480 | 64 TiB, plus the free one | 65 TiB | 77.8 TiB |
| 50 slots, always on (730 h) | $1,460 | 194.7 TiB, plus the free one | 195.7 TiB | 234.6 TiB |

So a commitment starts to be cheaper somewhere above **9 TiB a month** for a
workload that runs an hour a day, and above **about 196 TiB** for one that never
stops. This project estimates **0.023 TiB**: 400 times below the lowest
crossover. With the workload a thousand times larger (23 TiB) on-demand would cost
about $165 a month, and the cheapest capacity line above ($60) would then win, if
50 slots could really do that work in an hour; I have no measurement of that.
The decision holds for today's volume, not for that one.

## Decision

**On demand**, with `maximum_bytes_billed` on every query
([`warehouse-tuning.md`](../warehouse-tuning.md), section 6).

What it costs me: the bill has no ceiling of its own. Capacity would cap spend
at the reservation; on demand caps nothing, and a careless query is billed for
what it reads. The per-query cap is the substitute, and it is weaker in three
ways I know of: it is set per query or per client, not for the project (I could
not set the project-wide custom quota); it limits one query, not the sum of a
day's; and the minimum it can take is 10 MiB.

## What would change my mind

Numbers I can watch, from `INFORMATION_SCHEMA.JOBS_BY_PROJECT` (which my account
cannot read; whoever owns the project can):

```sql
SELECT DATE_TRUNC(creation_time, MONTH) AS month,
       ROUND(SUM(total_bytes_billed) / POW(2, 40), 3) AS tib_billed
FROM `region-europe-west1`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE job_type = 'QUERY' AND statement_type != 'SCRIPT'
GROUP BY month ORDER BY month;
```

- **Monthly TiB billed above 5.** That is half of the lowest crossover above, and
  the point at which I would price an autoscaled reservation properly.
- **A single query billed above 100 GiB** (about $0.73 at on-demand rates), seen
  more than once: the cap is not doing its job and capacity's hard ceiling starts
  to look better.
- **Queries queuing or timing out at peak** (the morning build): on demand shares
  a pool of slots across the project (about 2,000 by Google's documented default,
  not checked today), and a build that waits would be
  the sign that a reserved slice is worth its price.
- **A second team on the same project** with its own workload: then a ceiling per
  team matters more than a price per byte.
