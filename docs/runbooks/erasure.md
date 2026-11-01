# Runbook: erase one person

A customer asked to be erased. This is how to find everything that holds them, remove
it, and show that it is gone, written for somebody who was not in the room.

**Status of this runbook, 2026-11-01: tested once on one real identifier, partly.**
The tracing (steps 1 and 3) was run and measured. The deletions (steps 2 to 5) were
**not** performed, and the reasons are in "What the test did not do". An erasure reported
as done and not done is worse than one reported as blocked: the second gets fixed.

**Never write the identifier down.** Not in this file, a commit, an issue, a pull request
or a chat. It is what we are removing. Refer to a person by the short hash the trace script
prints (`sha256[:10]`) and by the date of the request. The tested identifier below is
`c14cf8cc24`.

## 0. Before you start

- **Who decides.** The group, in a pull request that names the hash, never the identifier.
  Check that the request comes from the person: erasing the wrong customer cannot be undone.
- **Pause the DAG** (`marketplace_daily`). Its `extract_tables` task rewrites the `*_pg` objects from
  the source on each run, which would put an erased person back (step 2).
- **Know your clock.** Section 5 lists copies that outlive a delete, with their retention. The
  request is only finished when the longest of them has expired or been dealt with.

## 1. Find them: every object, every table

```
python scripts/erasure_trace.py <buyer_id>                      # read-only
python scripts/erasure_trace.py <buyer_id> --dry-run-rewrite    # also filters locally, uploads nothing
```

`c_id` and `buyer_id` are the same identifier. The script starts from it, then follows the ids it
finds (order, address, card, review) into the tables that hold the person's data **without** carrying
the buyer id. Without that second hop you delete the order and leave the address.

Result on the tested identifier (measured, **169 seconds**): **21 objects, one in each of 21 table prefixes**.

| How they are found | Tables | Rows |
|---|---|---|
| By `buyer_id` / `c_id` | `buyer`, `customer`, `customer_payment`, `customer_shipping`, `customer_shipping_pg`, `subscription`, `review`, `review_pg`, `clickstream` | 1 each, except `clickstream` 2 |
| By `buyer_id`, twice | `orders`, `orders_pg` | 2 each: the same two orders, landed by the two paths |
| Through `order_id` | `order_items`, `order_items_pg`, `payment`, `shipment` | 2 each |
| Through `address_id` | `shipping_details`, `shipping_details_pg` | 1 each: street, zip, phone |
| Through `payment_id` | `payment_details` | 1: **card number, CVV, expiry and billing address** |
| Through `review_id` | `product_reviews`, `product_reviews_pg`, `seller_reviews` | 1 each |
| Found nothing | `wishlist_item`, `cart`, `returns`, `review_images`, `_dlq` | 0 |

Notice what this says: the person's card data (`secret`) is two hops from their id and is not removed
by deleting "the customer". That row is the one that matters most.

**Not covered by the script, and each of these needs a person:**

- The tables in `warehouse_julius` and the gold marts. The tester's account is refused on them
  (`Access Denied`), so they were not traced. `warehouse_julius` holds copies of order tables.
- The source: the PostgreSQL database and the CSV export bronze was built from.
- The Kafka topic that fed `clickstream`.
- Local files: `.state/` cursors, Airflow logs and volumes, `data/`, any Parquet a teammate downloaded.

## 2. Erase at the source first

Bronze is a copy. If the person stays in the PostgreSQL source, the next `extract_tables` run
overwrites each `*_pg` object from it and the person is back. Delete them in the source (and in any
backup of it), then pause or complete the steps below. `extract_orders` only appends new orders, so
it will not bring back old ones, but a full reload would.

The clickstream topic is the same: a retained message is re-consumed after an offset reset.

## 3. Silver and gold

Silver (staging and intermediate) is **views** over the bronze external tables. It stores nothing,
so there is nothing to delete there: the person disappears from silver the moment bronze changes,
except for **cached query results, which BigQuery keeps up to 24 hours**.

Gold (`fct_order_items`, `fct_daily_demand`, the dimensions) is **tables** and holds no buyer id, but it
holds the person's order lines (`order_id`, product, quantity, price, country). After bronze is corrected:

```
docker run --rm -v ~/.config/gcloud:/home/dbt/.config/gcloud:ro -e GCP_PROJECT_ID julius24h/albert-dbt:<tag> build
```

(the form used in `README.md` and `docs/reproduce.md`; take the current tag from `docs/reproduce.md`). It
rebuilds gold with `CREATE OR REPLACE`, so the lines vanish and revenue falls by the erased orders.
**Not run in the test**: the tester has no access to `l05_julius` (the dataset belongs to another group member).

## 4. Bronze: the procedure, honestly

There is no automation. A bronze object is a Parquet file; it cannot be edited in place. For each object
in the step 1 list:

1. Download it. Read it with the schema it already has.
2. Filter out the person's rows: by `buyer_id` / `c_id`, or by `order_id` / `address_id` / `payment_id` /
   `review_id` for the tables reached through another id.
3. Write a new Parquet file with the **same schema, compression (zstd) and partition path**
   (`dt=...`). Compare the schema before and after: a changed type breaks the external table.
4. Upload it over the old object (`gcloud storage cp`), which is a Class A operation.
5. Query the external table: the row count must have fallen by exactly the rows removed.

What it takes, **measured on 11 of the 21 objects** (`--dry-run-rewrite`, local, nothing uploaded):

| Measure | Value |
|---|---|
| Filter and rewrite one object | 0.5 to 1.3 seconds |
| Largest object touched | `review_pg`, 11.9 MB; `review`, 12.2 MB |
| Rows removed from each | 1 or 2 |
| Surprise | `orders/dt=2024-11` shrinks from 293,690 B to 203,983 B although only 2 of 10,019 rows were removed. The cause was not investigated (likely a different encoding); file size is therefore not a check, row counts are |

The computation is seconds. The work is writing and reviewing the upload job: **we estimate about two hours** to build and
test it once (an estimate, not a measurement; download and upload were not timed), **under a minute of compute** per person, but **one run per request**, and it re-reads
whole files, so ten requests a month would justify a different layout (partition or cluster by buyer, or
a deletion table applied at read time). Overwriting also costs the history: with no object versioning,
the old object is gone except for the soft-delete window (section 5).

## 5. The copies that survive a delete

Two of them stay behind a successful erasure, and **neither is a mistake**: both are durability features we turned on or accepted.

| Copy | Setting here | What you can do about it |
|---|---|---|
| **Cloud Storage soft delete** on the bronze bucket | **7 days** (`604800 s`), read on 2026-11-01. A replaced or deleted object stays restorable: `gcloud storage ls --soft-deleted`, `gcloud storage restore` | Shorten it **before** erasing, so the replaced objects expire sooner: `gcloud storage buckets update gs://data-engineering-a-groupe-julius-bronze --soft-delete-duration=<d>` (or `--clear-soft-delete`). That is a decision about our recovery window, so the group makes it. Whether objects already soft-deleted can be purged early was **not tested** |
| **BigQuery time travel** on `bronze_julius`, `l05_julius`, `warehouse_julius` | **168 hours** (7 days), the default | Can be lowered down to 48 hours on the dataset (`max_time_travel_hours`); a table rebuilt by dbt can be read `FOR SYSTEM_TIME AS OF` up to that window. BigQuery also keeps a fail-safe copy after time travel that we cannot reach or shorten (documented behaviour, not tested) |

Object versioning on the bronze bucket is **off** (checked), so no older generation of a file exists beyond
soft delete. The state bucket has versioning on and holds no person.

**Also holds the person, outside this table:** the source database and its backups; the Kafka topic;
laptops (`.state/`, Airflow logs and volumes, downloaded Parquet); the BigQuery job history (a query can have the
id in its text); and the Data Access audit log. Each needs its own owner and its own retention.

## 6. Prove it was done

1. Re-run `python scripts/erasure_trace.py <buyer_id>`. It must report **0 objects**.
2. Query the external tables and gold for the id and for the derived ids: 0 rows.
3. `gcloud storage ls --soft-deleted` on the touched prefixes shows the replaced generations and their
   expiry date. The request is complete on the latest of those dates, plus the time travel window.
4. A second person repeats 1 and 2 without being told the answer.
5. Write the proof down **without the identifier**: the hash, the date, the counts before and after, and
   the expiry dates. Keep it with the request.

## What the test did not do, and what did not work

Run on 2026-11-01, on one real identifier from the production data (`c14cf8cc24`).

- **No deletion was performed in bronze, the source or gold.** It would have overwritten real objects in a bucket
  without versioning, for a person who did not ask. The decision to run a real erasure belongs to the group.
- **Silver and gold were not rebuilt**: no access to `l05_julius` and `warehouse_julius` from the tester's account.
- **`warehouse_julius` was not traced**, so the list in step 1 is a lower bound.
- **The Data Access audit log could not be read**, so we cannot say who has read this person's rows. The
  Admin Activity log can be read; the data-access one returned nothing.
- **The trace was run twice**: a first throwaway script (176 s) and then the committed `scripts/erasure_trace.py` (169 s). Both found the same 21 objects, so the result is repeatable. The script was written after the first run, not before.
- **The wall-clock of a real run is unknown**, because download and upload were not measured.

## If you only read one line

We cannot complete this erasure today. The trace, the rewrite and the proof are in place; what stops it is the
source database, access to the gold dataset, and a decision on the soft-delete window. This is the runbook that
would finish it.
