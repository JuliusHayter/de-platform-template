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

## Lesson 6: images

| Item | Quantity | Cost |
|---|---|---|
| Docker Hub, two public repositories | 153 MB and 311 MB compressed per tag | $0 (free plan) |
| If they were on Artifact Registry instead | three tags of each: 1.36 GiB, 0.86 GiB billed above the free 0.5 | $0.09 per month ([ADR-0006](adr/0006-image-tags.md)) |
| Local disk | ingestion 491 MB, dbt 1.06 GB uncompressed | not a cloud cost |

The images carry no data and run only when started, so there is no running cost
until lesson 7 schedules them. What a registry bills is tags nobody deleted, which
is why the retention policy exists.


## Lesson 9: attribution, a budget, one saving, the ledger

Written 2026-11-01. Three things limit what this section can claim, and they are
stated here rather than hidden:

- **No billing export for our project.** The only export-shaped table reachable is
  the generated demo bill in `l09_leonard`, which is invented. So the cost shape
  below comes from `INFORMATION_SCHEMA.JOBS_BY_USER`, as the project step allows.
- **That view only shows the queries of one account** (`JOBS_BY_USER`). The
  project-wide `JOBS` view is refused (`bigquery.jobs.listAll`), so it does not
  contain what teammates ran.
- **Prices were not re-read from the live pages.** Both Google pricing pages render
  their tables with JavaScript and could not be read on 2026-11-01, and the Cloud
  Billing Catalog API is not enabled on the project. Every unit price below is the
  one already dated 2026-10-29 at the top of this file. Re-check them in the console
  before quoting a cost outside this course.

### The label convention

Four keys on every resource we own, set in `infra/terraform/main.tf` (`local.base_labels`
plus a per-resource block), never in the console:

| Key | Values in use | Why it exists |
|---|---|---|
| `team` | `julius` | Who to ask about the cost. One value today; it is the key that matters the day a second team shares the project |
| `environment` | `prod` | So a development spike is not read as production. Everything is `prod` because we have no second environment, and that is itself a finding |
| `pipeline` | `marketplace-daily`, `warehouse-tuning`, `terraform-state` | Which workload, not which resource. Lets the DAG's cost be summed across a bucket and two datasets |
| `lesson` | `l02`, `l04`, `l05`, `l08` | When it was made. Tidying aid for this course, and the first key to drop in a real platform |

Four keys, because beyond about six people start leaving them out.

| Resource | `pipeline` | `lesson` | Labelled? |
|---|---|---|---|
| `data-engineering-a-groupe-julius-bronze` | `marketplace-daily` | `l02` | **Yes**, through Terraform |
| `data-engineering-a-groupe-julius-tfstate` | `terraform-state` | `l08` | **Yes, by hand** (`gcloud storage buckets update --update-labels`): Terraform does not manage this bucket |
| `bronze_julius` | `marketplace-daily` | `l04` | **Declared, not applied** (see below) |
| `l05_julius` | `marketplace-daily` | `l05` | **Declared, not applied** |
| `warehouse_julius` | `warehouse-tuning` | `l04` | **Declared, not applied** |

**Declared but not applied.** `terraform apply` labelled the bucket and was refused
on the three datasets: `403 Permission bigquery.datasets.update denied`. The datasets
were created by another group member who is their only owner. Until that person runs
`terraform apply`, `terraform plan` reports `0 to add, 3 to change, 0 to destroy`
and the datasets are unlabelled. This is the same shape of gap as the missing service
account in [`docs/infra.md`](infra.md): the configuration states the intent and the
permissions do not yet match it.

**`warehouse_julius` was missing from Terraform.** Lesson 8 declared only the datasets
the pipeline reads. Listing the project's datasets to build the ledger found the L04
measurement dataset, which was then imported (`1 to import` in the same plan).

### What is already unattributable

- **Everything before 2026-11-01.** Labels apply from the moment they are set and never
  backwards, so all spend up to now carries no `team` and cannot be recovered.
- **All query spend.** Dataset labels do not label the jobs that read them. Neither dbt nor
  the Airflow DAG passes a job label, so BigQuery query cost still lands on the project with
  no team. Fixing it is a `labels` entry in the dbt profile and in the DAG's BigQuery calls,
  not a Terraform change, and it is not done.
- **The three datasets until their owner applies.**
- **Nothing enforces any of this.** A resource created tomorrow from the console has no labels.

### A budget alert

**Not done, and it cannot be done from this account.** `gcloud billing budgets list
--billing-account=0192F3-70E18D-2F5B30` returns permission denied, and the project's
budget was created by the teaching team before anyone logged in.

To do in the billing console (Budgets & alerts, the project's existing budget, add an
alert threshold):

| Field | Value |
|---|---|
| Threshold | 50% and 100% of the budget amount |
| Notified | **TO FILL: name and address of the person who receives it** |

What it does not do: **it does not stop anything.** At 100% it sends an email to that
person and nothing else; spend can exceed the budget by any amount, and an alert sent to
a mailbox nobody reads is a budget with no alert. If we needed a cap, `maximum_bytes_billed`
on the scheduled queries refuses a query instead of reporting it (and breaks the pipeline
rather than the bill); a quota stops one API; disabling billing stops the whole project.

### Largest cost, and its shape

The bill is inside the free tier, so money reads zero and the units carry the answer.

Ordered by what each item would cost without the free allowances, at the prices dated above:

| Item | Quantity | Cost |
|---|---|---|
| Cloud Storage, Standard, `bronze` bucket | 108,337,114 B = 0.101 GiB | $0.0020 per month |
| BigQuery query bytes **billed** (my account, 31 days) | 160 MiB billed, for 2.6 MiB processed | $0.0011 at $7.50/TiB, free inside the first TiB |
| Cloud Storage, state bucket, all versions | 50,230 B | $0.000001 per month |

**The largest cost is Standard storage of the bronze bucket** (SKU "Standard Storage
europe-west1"), at about $0.002 a month. It is flat, growing with each load.

**The shape worth naming is the query bytes: a spike.** Zero-filled over the 31 days to
2026-11-01 (26 of the 31 days have no row at all, which is why the series was filled
against a date range before reading it):

| Day | Jobs | MiB processed | MiB billed |
|---|---|---|---|
| 2026-10-26 | 20 | 1.47 | 120.0 |
| 2026-10-29 | 2 | 0.0 | 0.0 |
| 2026-11-01 | 5 | 1.16 | 20.0 |
| every other day | 0 | 0 | 0 |

One spike on 2026-10-26, the day of the L04 measuring runs, and nothing since. **The
point in the table is the gap between the last two columns:** 20 queries processed
1.47 MiB and were billed 120 MiB, 80 times more, because BigQuery bills at least
10 MiB per query. Small queries are billed by their count, not their size. That matters
more here than any storage figure: at this size, the number of queries is the meter.

### One optimisation: the state bucket's accumulating versions

| What we measured | Object versions and bytes under `platform/` in the state bucket |
|---|---|
| Before, on 2026-11-01 | **22 versions, 50,230 B**: 18 versions of the lock file `default.tflock` (4,833 B) and 4 versions of `default.tfstate` (45,397 B) |
| The change | `infra/state-lifecycle.json` applied to the bucket: delete a non-current lock version one day after it stops being current; delete a state version once 20 newer ones exist |
| After | **To measure on 2026-11-03 with the same command** (below). Expected: the 4 state versions and at most 1 or 2 lock versions |
| Money saved | About $0.000001 a month. Nothing visible, and not the point |

```
gcloud storage ls -a -l gs://data-engineering-a-groupe-julius-tfstate/platform/
```

Every `terraform plan` and `apply` writes a lock object, and versioning keeps each one
forever, so the bucket grows with use and not with the platform. The lock has no value
once released. The state versions are the recovery path in
[ADR-0008](adr/0008-remote-state.md), so they are kept until 20 newer ones exist.

**What would tell us we were wrong:**

- On 2026-11-03 more than 2 lock versions remain: the rule's prefix or condition does not
  match (lifecycle runs asynchronously, normally within a day, so two days is enough).
- Fewer than 4 state versions remain: the rule is deleting the recovery path. Remove it at once.
- `terraform plan` stops working or reports `Error acquiring the state lock` that did not
  happen before: a lifecycle delete raced with a lock. Remove the first rule.

Honest caveat: this optimisation is real and measured in units, but it is worth almost
nothing. It was picked because it is the one we can both change and measure with the access
we have. The saving that would matter is in BigQuery (fewer, larger queries; dbt tests that
read tables rather than views), and neither can be measured from this account: the group's
tables return `Access Denied`.

## The ledger

One row per resource we own. Prices are those dated 2026-10-29 at the top of this file, not
re-read (see the limits above). Sizes marked * could not be re-measured today (access denied)
and are the figures recorded in the lesson named.

| Resource | What it is | What drives its cost | Unit price | Estimate |
|---|---|---|---|---|
| Bucket `data-engineering-a-groupe-julius-bronze` | Bronze layer, 27 tables as Parquet, 135+ objects | Stored GiB; Class A operations on every write; class change after 30, 90 and 365 days | Standard $0.020 per GiB-month; Class A $0.005 per 1,000 | 0.101 GiB = **$0.0020 per month**. Nearline, Coldline and Archive prices were not read |
| Bucket `data-engineering-a-groupe-julius-tfstate` | Terraform state, versioned | Stored GiB (all versions); operations on every plan | Standard $0.020 per GiB-month | 50,230 B = **about $0** |
| Dataset `bronze_julius` | External tables over the bronze files | Stores nothing. Each query pays for the bytes it reads | $7.50 per TiB, first TiB each month free | **$0 stored**; query cost counted under L04 |
| Dataset `l05_julius` | dbt silver and gold: five marts (tables) and twelve views | Stored GiB of the marts; bytes read by every query | $0.020 per GiB-month stored; $7.50 per TiB read | 57.8 MB* = **$0.001 per month** |
| Dataset `warehouse_julius` | L04 measurement copies of the same data | Stored GiB, eight copies | $0.020 per GiB-month | 0.25 GiB* = **$0.005 per month**, before BigQuery's free 10 GiB. Can be dropped once a grain is chosen ([L04](#lesson-4-the-warehouse)) |
| Docker Hub repositories `albert-ingestion`, `albert-dbt` | Container images | Nothing: public repositories on the free plan | $0 | **$0** ([ADR-0006](adr/0006-image-tags.md)) |
| Artifact Registry `dataeng` | The class's shared registry | Not ours; we push nothing to it | n/a | **$0 to us** |
| The Airflow stack and Kafka/PostgreSQL | Local containers on a laptop | Not a cloud cost | n/a | **$0** |
| Billing budget | Alert on the project | Free; it is the teaching team's | $0 | **$0** |

Total, as far as we can see: **about $0.008 a month**, almost all of it BigQuery storage
of the L04 copies. The ledger is complete only for what is labelled: the three datasets
become checkable by label the day they are labelled, and there may be other resources in the
project under our name that this account cannot list (service accounts, for one).
