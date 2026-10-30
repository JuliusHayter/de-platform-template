"""Measure what each query costs against each table variant.

For every (query, variant): a dry run for the estimate, then a real run with the
cache off, then bytes processed and bytes billed read from the finished job.
Bytes processed is the number to compare; bytes billed is floored at 10 MiB.

usage: python measure.py        (needs the bq CLI, signed in, and the tables from 01 and 02)
"""
import json
import subprocess
import time
import uuid

DS = "data-engineering-a.warehouse_julius"
TODAY = "DATE '2026-09-14'"

REVENUE = f"""SELECT DATE_TRUNC(order_date, MONTH) AS month, ROUND(SUM(qty * price_at_purchase), 2) AS revenue
FROM `{DS}.{{items}}`
WHERE order_date > DATE_SUB({TODAY}, INTERVAL 12 MONTH) AND order_date <= {TODAY}
GROUP BY month ORDER BY month"""
TOP10 = f"""SELECT p_id, SUM(qty) AS units
FROM `{DS}.{{items}}`
WHERE order_date > DATE_SUB({TODAY}, INTERVAL 3 MONTH) AND order_date <= {TODAY}
GROUP BY p_id ORDER BY units DESC LIMIT 10"""
RATING = f"""SELECT pr.p_id, ROUND(AVG(r.rating), 2) AS avg_rating, COUNT(*) AS reviews
FROM `{DS}.{{review}}` AS r JOIN `{DS}.{{pr}}` AS pr USING (review_id)
GROUP BY pr.p_id HAVING COUNT(*) > 50"""
LOOKUP = f"SELECT SUM(qty) AS units FROM `{DS}.{{items}}` WHERE p_id = '{{p}}'"

CASES = [
    ("Q1 revenue by month", "untuned", REVENUE.format(items="order_items")),
    ("Q1 revenue by month", "partitioned (month)", REVENUE.format(items="order_items_p")),
    ("Q1 revenue by month", "partitioned (day)", REVENUE.format(items="order_items_day")),
    ("Q1 revenue by month", "partitioned (year)", REVENUE.format(items="order_items_year")),
    ("Q2 top 10 products", "untuned", TOP10.format(items="order_items")),
    ("Q2 top 10 products", "partitioned (month)", TOP10.format(items="order_items_p")),
    ("Q2 top 10 products", "partitioned + clustered", TOP10.format(items="order_items_pc")),
    ("Q2 top 10 products", "clustered only", TOP10.format(items="order_items_clustered")),
    ("Q3 rating per product", "untuned", RATING.format(review="review", pr="product_reviews")),
    ("Q3 rating per product", "clustered (join keys)", RATING.format(review="review_c", pr="product_reviews_c")),
]
for p in ("B0CHXWTSM6", "B0BM4GX6TT"):
    for variant, table in [("untuned", "order_items"), ("clustered only", "order_items_clustered"),
                           ("partitioned + clustered", "order_items_pc"), ("day + clustered", "order_items_day"),
                           ("year + clustered", "order_items_year")]:
        CASES.append((f"lookup {p}", variant, LOOKUP.format(items=table, p=p)))


def bq(*args, sql):
    return subprocess.run(["bq", "--location=europe-west1", "--format=json", "query", "--nouse_legacy_sql", *args],
                          input=sql, capture_output=True, text=True)


rows = []
for name, variant, sql in CASES:
    dry = bq("--dry_run", sql=sql)
    estimate = int(json.loads(dry.stdout)["statistics"]["query"]["totalBytesProcessed"])
    job = "m_" + uuid.uuid4().hex[:12]
    run = bq("--nouse_cache", "--maximum_bytes_billed=1073741824", f"--job_id={job}", sql=sql)
    if run.returncode:
        raise SystemExit(run.stderr)
    time.sleep(1)
    stats = json.loads(subprocess.run(["bq", "--location=europe-west1", "--format=json", "show", "-j", job],
                                      capture_output=True, text=True).stdout)["statistics"]["query"]
    rows.append((name, variant, estimate, int(stats["totalBytesProcessed"]), int(stats["totalBytesBilled"]),
                 stats.get("cacheHit", False)))
    print(*rows[-1], flush=True)

print("\n| Query | Variant | Estimate | Processed | Billed | Cache hit |\n|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(f"{c:,}" if isinstance(c, int) and not isinstance(c, bool) else str(c) for c in r) + " |")
