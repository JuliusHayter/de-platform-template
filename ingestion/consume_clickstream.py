"""Read clickstream events from Kafka and write them to partitioned Parquet in bronze.

Delivery guarantee: at-least-once - each batch is written to bronze before its
offsets are committed, so a crash between the two re-reads the batch (duplicates,
never loss).

Partitioned by event_time (the day the event happened), not emitted_at (the day
it reached Kafka): a late event then lands in the day it belongs to, so a day's
partition is only ever completed, never wrong. emitted_at stays in the row.

Every event is validated against clickstream.schema.json, picked by its
schema_version. An event that fails goes to the dead-letter path with the raw
message, the reason and the time; one bad row never stops the flow.

Configuration comes from the environment; there is no credential in this file.
OUT and DLQ may be local paths or gs:// URIs (Google credentials from the
environment, see docs/ingestion-failure-modes.md).
"""

import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
from confluent_kafka import Consumer
from jsonschema import Draft202012Validator

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "clickstream")
# No default: the group is where Kafka stores how far this consumer has read.
GROUP = os.environ["CONSUMER_GROUP"]
BUCKET = os.environ.get("BRONZE_URI", "out")
OUT = os.environ.get("OUT", f"{BUCKET}/bronze/clickstream")
DLQ = os.environ.get("DLQ", f"{BUCKET}/bronze/_dlq/clickstream")
BATCH = int(os.environ.get("BATCH", "200"))
# Seconds between writing and committing. 0 in normal use; a test hook that
# widens the window in which a kill produces duplicates.
PAUSE = float(os.environ.get("PAUSE_BEFORE_COMMIT", "0"))

# One validator per schema_version. A new version is a new file and a new line.
SCHEMA_DIR = Path(__file__).parent
VALIDATORS = {
    1: Draft202012Validator(json.loads((SCHEMA_DIR / "clickstream.schema.json").read_text())),
}

ITEM = pa.struct([("p_id", pa.string()), ("qty", pa.int64()), ("price", pa.float64())])
EVENT_SCHEMA = pa.schema([
    ("schema_version", pa.int64()), ("event_id", pa.string()), ("event_type", pa.string()),
    ("event_time", pa.string()), ("emitted_at", pa.string()),
    ("session_id", pa.string()), ("buyer_id", pa.string()),
    ("p_id", pa.string()), ("price", pa.float64()), ("qty", pa.int64()),
    ("order_id", pa.int64()), ("payment_method", pa.string()), ("amount", pa.float64()),
    ("currency", pa.string()), ("items", pa.list_(ITEM)),
])
DLQ_SCHEMA = pa.schema([
    ("raw", pa.string()), ("reason", pa.string()), ("received_at", pa.string()),
    ("topic", pa.string()), ("partition", pa.int32()), ("offset", pa.int64()),
])

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,        # committed by hand, after the write
})
consumer.subscribe([TOPIC])
good, bad = [], []
written = 0


def validate(raw):
    """Return the event, or raise ValueError saying why it is not acceptable."""
    try:
        event = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"not JSON: {exc}")
    if not isinstance(event, dict):
        raise ValueError("not a JSON object")
    validator = VALIDATORS.get(event.get("schema_version"))
    if validator is None:
        raise ValueError(f"unsupported schema_version: {event.get('schema_version')!r}")
    errors = sorted(validator.iter_errors(event), key=lambda e: list(e.path))
    if errors:
        raise ValueError("; ".join(f"{'/'.join(map(str, e.path)) or '<event>'}: {e.message}" for e in errors[:3]))
    datetime.fromisoformat(event["event_time"].replace("Z", "+00:00"))   # also rejects a bad date
    return event


def write(rows, schema, root, day_of):
    """One Parquet file per day under dt=YYYY-MM-DD/. dt lives in the path only."""
    by_day = {}
    for row in rows:
        by_day.setdefault(day_of(row), []).append(row)
    filesystem, base = pafs.FileSystem.from_uri(root if "://" in root else os.path.abspath(root))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    for dt, part in sorted(by_day.items()):
        folder = f"{base}/dt={dt}"
        filesystem.create_dir(folder, recursive=True)
        path = f"{folder}/part-{stamp}-{uuid.uuid4().hex[:6]}.parquet"
        pq.write_table(pa.Table.from_pylist(part, schema=schema), path,
                       filesystem=filesystem, compression="zstd")
        print(f"  wrote {len(part):4d} rows  {root}/dt={dt}/{path.rsplit('/', 1)[1]}", flush=True)


def flush():
    """Write everything buffered, then commit. In that order, on purpose."""
    global good, bad, written
    if not good and not bad:
        return
    if good:
        write(good, EVENT_SCHEMA, OUT, lambda e: e["event_time"][:10])
        written += len(good)
    if bad:
        write(bad, DLQ_SCHEMA, DLQ, lambda r: r["received_at"][:10])
        print(f"  {len(bad)} row(s) quarantined", flush=True)
    if PAUSE:
        print(f"  ... {PAUSE}s before committing the offset. Kill me now.", flush=True)
        time.sleep(PAUSE)
    consumer.commit(asynchronous=False)
    print(f"  offset committed   (rows written so far: {written})", flush=True)
    good, bad = [], []


def stop(*_):
    # No flush: the buffered rows were not committed, so they will be read again.
    consumer.close()
    sys.exit(0)


signal.signal(signal.SIGTERM, stop)
print(f"reading {TOPIC} from {BOOTSTRAP} as group {GROUP}\nwriting to {OUT}\n", flush=True)
try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            flush()                      # idle: write what we have
            continue
        if msg.error():
            print(f"  kafka error: {msg.error()}", flush=True)
            continue
        raw = msg.value().decode("utf-8", errors="replace")
        try:
            good.append(validate(raw))
        except ValueError as exc:
            bad.append({"raw": raw, "reason": str(exc),
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "topic": msg.topic(), "partition": msg.partition(),
                        "offset": msg.offset()})
        if len(good) + len(bad) >= BATCH:
            flush()
except KeyboardInterrupt:
    stop()
