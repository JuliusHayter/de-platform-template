"""Incrementally extract the orders table from PostgreSQL to bronze Parquet.

Delivery guarantee: at-least-once - the cursor is saved only after the batch is
written, so a crash re-reads the last batch rather than losing it. It sees new
rows only: an UPDATE to an old order, or a DELETE, never moves order_id past the
cursor (see docs/ingestion-failure-modes.md).

Cursor: order_id, with a strict ">". order_id is a unique, increasing key, so
unlike a date cursor there is no boundary row to re-read and none to lose.

Configuration is all environment, nothing is read from this file:
  PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD   libpq's own variables (PGPASSWORD has no default)
  BRONZE_URI    a gs:// bucket URI or a local folder, default "out"
  STATE_PATH    where the cursor lives, default ".state/extract_orders.json"
  BATCH_ROWS    rows per query and per file set, default 50000
  MAX_ATTEMPTS  connection attempts before giving up, default 5
"""

import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

BRONZE = os.environ.get("BRONZE_URI", "out")
OUT = f"{BRONZE}/bronze/orders_pg"
STATE = Path(os.environ.get("STATE_PATH", ".state/extract_orders.json"))
BATCH_ROWS = int(os.environ.get("BATCH_ROWS", "50000"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "5"))
# Only host, port, db and user have defaults; the password must be in the environment.
if "PGPASSWORD" not in os.environ:
    sys.exit("PGPASSWORD is not set")


def load_cursor():
    return json.loads(STATE.read_text())["order_id"] if STATE.exists() else 0


def save_cursor(order_id):
    # Write beside, then rename: a crash mid-write cannot leave a half-written state file.
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"order_id": order_id, "saved_at": datetime.now(timezone.utc).isoformat()}))
    tmp.replace(STATE)


def connect():
    """Retry with a growing delay (1s, 2s, 4s, ... plus jitter), then give up."""
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
            print(f"connection failed (attempt {attempt}/{MAX_ATTEMPTS}): {exc}; retrying in {delay:.1f}s", flush=True)
            time.sleep(delay)


def write(df):
    """Parquet files under dt=YYYY-MM/, the same key as bronze/orders."""
    df = df.assign(dt=pd.to_datetime(df["order_date"]).dt.strftime("%Y-%m"))
    filesystem, base = pafs.FileSystem.from_uri(OUT if "://" in OUT else os.path.abspath(OUT))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    for dt, part in df.groupby("dt"):
        folder = f"{base}/dt={dt}"
        filesystem.create_dir(folder, recursive=True)
        path = f"{folder}/part-{stamp}-{uuid.uuid4().hex[:6]}.parquet"
        pq.write_table(pa.Table.from_pandas(part.drop(columns="dt"), preserve_index=False), path,
                       filesystem=filesystem, compression="zstd")
        print(f"  wrote {len(part):6d} rows  dt={dt}", flush=True)


cursor = load_cursor()
print(f"cursor: order_id > {cursor}", flush=True)
total = 0
while True:
    # A fresh connection per batch keeps a long run from holding one open, and
    # makes every batch pass through the retry.
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE order_id > %s ORDER BY order_id LIMIT %s", (cursor, BATCH_ROWS))
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=[c.name for c in cur.description])
    if df.empty:
        break
    write(df)                                  # 1. the data is in bronze ...
    cursor = int(df["order_id"].max())
    save_cursor(cursor)                        # 2. ... only then does the cursor move
    total += len(df)
print(f"{total} new row(s); cursor now {cursor}", flush=True)
