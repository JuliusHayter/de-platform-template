"""Find every place in bronze that holds one buyer, without changing anything.

Step 1 of docs/runbooks/erasure.md. Read-only: it lists objects and reads Parquet,
it never writes to the bucket.

    export BRONZE=data-engineering-a-groupe-julius-bronze
    python scripts/erasure_trace.py <buyer_id>
    python scripts/erasure_trace.py <buyer_id> --dry-run-rewrite

It prints counts and object paths, never the identifier or any column value: the
identifier is what we are trying to get rid of, so it must not end up in a log, a
pull request or a runbook. It prints a short hash instead, to tell two runs apart.

--dry-run-rewrite also filters the buyer out of every file that holds it and
writes the result to a temporary directory, to measure what a real erasure would
touch. Nothing is uploaded.

Needs pyarrow (the ingestion image has it) and `gcloud auth application-default login`.
About 3 minutes on the full bucket: it reads whole files, because Parquet tables
here are small and a scan is simpler than an index.
"""
import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import time

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from pyarrow import fs

BUCKET = os.environ.get("BRONZE", "data-engineering-a-groupe-julius-bronze")
ROOT = f"{BUCKET}/bronze"
gcs = fs.GcsFileSystem()

# (prefix, column) holding the buyer directly. c_id is the same identifier as buyer_id.
DIRECT = [
    ("buyer", "buyer_id"), ("customer", "c_id"), ("customer_payment", "c_id"),
    ("customer_shipping", "c_id"), ("customer_shipping_pg", "c_id"), ("subscription", "c_id"),
    ("wishlist_item", "buyer_id"), ("orders", "buyer_id"), ("orders_pg", "buyer_id"),
    ("review", "buyer_id"), ("review_pg", "buyer_id"), ("cart", "buyer_id"),
    ("returns", "buyer_id"), ("clickstream", "buyer_id"),
]


def parquet_files(prefix):
    selector = fs.FileSelector(f"{ROOT}/{prefix}", recursive=True)
    return [i for i in gcs.get_file_info(selector) if i.path.endswith(".parquet")]


def table(path, columns=None):
    return ds.dataset(path, filesystem=gcs, format="parquet").to_table(columns=columns)


def matches(prefix, column, values):
    """Rows and files of `prefix` where `column` is one of `values`."""
    wanted = pa.array([str(v) for v in values], pa.string())
    rows, found = 0, []
    for info in parquet_files(prefix):
        try:
            t = table(info.path, [column])
        except (pa.ArrowInvalid, KeyError):
            continue  # this file has no such column (e.g. a header-only table)
        n = pc.sum(pc.is_in(t[column].cast(pa.string()), value_set=wanted).cast(pa.int64())).as_py() or 0
        if n:
            rows += n
            found.append(info)
    return rows, found


def column_values(prefix, key, value, out_col):
    """Values of `out_col` on the rows of `prefix` where `key` == `value`."""
    got = set()
    for info in parquet_files(prefix):
        t = table(info.path, [key, out_col])
        for k, v in zip(t[key].to_pylist(), t[out_col].to_pylist()):
            if k == value:
                got.add(v)
    return got


def dry_run_rewrite(info, column, buyer, tmp):
    t0 = time.time()
    t = table(info.path)
    hit = pc.fill_null(pc.equal(t[column], buyer), False)
    kept = t.filter(pc.invert(hit))
    out = os.path.join(tmp, "out.parquet")
    pq.write_table(kept, out, compression="zstd")
    print(f"    dry run: {info.size:,} B, {t.num_rows:,} -> {kept.num_rows:,} rows, "
          f"new file {os.path.getsize(out):,} B, {time.time() - t0:.1f}s (not uploaded)")
    os.remove(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("buyer_id")
    ap.add_argument("--dry-run-rewrite", action="store_true")
    args = ap.parse_args()
    buyer = args.buyer_id
    t0 = time.time()
    print("buyer sha256[:10] =", hashlib.sha256(buyer.encode()).hexdigest()[:10], "| bucket =", BUCKET)
    tmp = tempfile.mkdtemp(prefix="erasure-dryrun-") if args.dry_run_rewrite else None
    touched = set()

    def report(prefix, column, values):
        rows, found = matches(prefix, column, values)
        print(f"{prefix:26s} {column:11s} rows={rows:4d} files={len(found)}")
        for info in found:
            touched.add(info.path)
            print("   ", info.path.replace(ROOT + "/", "bronze/"))
            if tmp and column in ("buyer_id", "c_id"):
                dry_run_rewrite(info, column, buyer, tmp)
        return rows

    print("--- directly, by buyer_id / c_id")
    for prefix, column in DIRECT:
        report(prefix, column, [buyer])

    print("--- reached through ids found above (these hold the person's data without the buyer id)")
    orders = column_values("orders", "buyer_id", buyer, "order_id") | column_values("orders_pg", "buyer_id", buyer, "order_id")
    for prefix in ("order_items", "order_items_pg", "payment", "shipment"):
        report(prefix, "order_id", orders)
    addresses = column_values("customer_shipping", "c_id", buyer, "address_id")
    for prefix in ("shipping_details", "shipping_details_pg"):
        report(prefix, "address_id", addresses)
    cards = column_values("customer_payment", "c_id", buyer, "payment_id")
    report("payment_details", "payment_id", cards)
    reviews = column_values("review", "buyer_id", buyer, "review_id")
    for prefix in ("review_images", "product_reviews", "seller_reviews", "product_reviews_pg"):
        report(prefix, "review_id", reviews)

    print("--- dead letter queue (raw text, may contain the id)")
    dead = 0
    for info in parquet_files("_dlq"):
        n = sum(1 for r in table(info.path, ["raw"])["raw"].to_pylist() if r and buyer in r)
        if n:
            dead += n
            touched.add(info.path)
            print("   ", info.path.replace(ROOT + "/", "bronze/"))
    print(f"_dlq raw                   rows={dead}")

    print(f"--- {len(touched)} objects hold this buyer or an id derived from it; {time.time() - t0:.0f}s")
    if tmp:
        shutil.rmtree(tmp)
        print("nothing was uploaded; temporary directory removed")
    print("NOT covered: the source database, the Kafka topic, BigQuery tables in warehouse_julius, "
          "local .state/ and Airflow logs. See docs/runbooks/erasure.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
