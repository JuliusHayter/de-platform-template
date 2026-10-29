"""Copy the tables lessons 4 and 5 need from PostgreSQL to bronze, secrets left behind.

Delivery guarantee: at-least-once, and idempotent - each table is a full refresh
that overwrites one file, so a re-run replaces it and cannot duplicate rows.

This is the hand-written stand-in for a connector (route 3). The secret columns
are never selected: EXCLUDED is applied to the column list, so the query asks
PostgreSQL for everything except them and they never reach this process, let
alone bronze. That is weaker than deselecting them in a connector's UI, because
here the guarantee lives in code a later edit can change (for example to
SELECT *), and nothing but a test (see below) would notice.

Environment: PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD (no default for the
password), BRONZE_URI (gs:// URI or local folder, default "out"), MAX_ATTEMPTS.
Output: bronze/<table>_pg/part-0.parquet

usage: extract_tables.py [table ...]    (default: the six tables below; orders is extract_orders.py)
"""

import os
import random
import sys
import time

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

# orders is not here: extract_orders.py owns bronze/orders_pg/ and reads it incrementally.
DEFAULT_TABLES = ["order_items", "review", "product_reviews", "product",
                  "customer_shipping", "shipping_details"]
# Never selected, whatever table asks for them.
EXCLUDED = {("customer", "pwd"), ("payment_details", "card_no"), ("payment_details", "cvv"),
            ("payment_details", "expiry_date")}   # expiry is card data too: the data dictionary says secret
BRONZE = os.environ.get("BRONZE_URI", "out")
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "5"))
if "PGPASSWORD" not in os.environ:
    sys.exit("PGPASSWORD is not set")


def connect():
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return psycopg.connect(
                host=os.environ.get("PGHOST", "localhost"), port=os.environ.get("PGPORT", "5432"),
                dbname=os.environ.get("PGDATABASE", "marketplace"),
                user=os.environ.get("PGUSER", "postgres"), connect_timeout=5)
        except psycopg.OperationalError as exc:
            if attempt == MAX_ATTEMPTS:
                sys.exit(f"giving up after {attempt} attempts: {exc}")
            delay = 2 ** (attempt - 1) + random.random()
            print(f"connection failed (attempt {attempt}/{MAX_ATTEMPTS}); retrying in {delay:.1f}s", flush=True)
            time.sleep(delay)


def extract(conn, table):
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position", (table,))
        columns = [c for (c,) in cur.fetchall() if (table, c) not in EXCLUDED]
        if not columns:
            sys.exit(f"no such table: {table}")
        skipped = [c for t, c in EXCLUDED if t == table]
        cur.execute(psycopg.sql.SQL("SELECT {} FROM {}").format(
            psycopg.sql.SQL(", ").join(map(psycopg.sql.Identifier, columns)), psycopg.sql.Identifier(table)))
        df = pd.DataFrame(cur.fetchall(), columns=columns)
    root = f"{BRONZE}/bronze/{table}_pg"
    filesystem, base = pafs.FileSystem.from_uri(root if "://" in root else os.path.abspath(root))
    filesystem.create_dir(base, recursive=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), f"{base}/part-0.parquet",
                   filesystem=filesystem, compression="zstd")
    print(f"{table}: {len(df)} rows, {len(columns)} columns" + (f", left out {skipped}" if skipped else ""), flush=True)


with connect() as conn:
    for table in sys.argv[1:] or DEFAULT_TABLES:
        extract(conn, table)
