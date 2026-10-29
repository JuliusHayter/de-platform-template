# Ingestion failure modes

What each pipeline does when something goes wrong, tested where I could. Two
pipelines exist: the **extractor** (`ingestion/extract_orders.py`, incremental
batch from PostgreSQL) and the **consumer** (`ingestion/consume_clickstream.py`,
Kafka streaming). Change data capture was only run by hand in exercise 1 (a
replication slot read with SQL); no pipeline reads it. There is no Airbyte
connector (see [ADR-0003](adr/0003-ingestion-modes.md)).

"Tested" means I caused it and looked at the result; the rest is reasoning from
the code and is labelled so.

| Failure | Handled? | By what | What happens if it occurs |
|---|---|---|---|
| New rows | Yes | Extractor: `WHERE order_id > cursor`. Consumer: reads every new message | Tested: after the initial load, a second run read only the 24 orders created since, starting at cursor + 1. |
| Updates to existing rows | **Not handled** (extractor) | Nothing. Only change data capture sees them, and no CDC pipeline exists | Tested: I moved `order_date` of order 1 by a day; the next sync read 24 rows and order 1 was not among them. Bronze keeps the old date and nothing reports an error. Clickstream events are never updated. |
| Deletes | **Not handled** | Nothing | Reasoned, and seen in the exercise's slot: the log records the delete, a cursor query cannot, since no row is left to read. A deleted order stays in bronze as if it still existed. |
| Source down (PostgreSQL) | Partly | Extractor retries 5 times with a growing delay (1 s, 2 s, 4 s, ...), then exits with an error | Tested with a wrong port, 3 attempts: it retried twice, then gave up with a non-zero exit. The cursor did not move, so nothing is lost. **Not handled:** nothing restarts it, so until L07's scheduler a human must notice. |
| Source down (Kafka) | Partly | The Kafka client reconnects by itself | Reasoned: `poll` returns errors that the consumer prints and carries on. Nothing alerts on a topic that stays silent. Not tested. |
| Malformed row | Yes | Consumer validates every event against `clickstream.schema.json` and quarantines failures to `bronze/_dlq/` | Tested: I sent a non-JSON line, an event without `price` and one with `schema_version` 2. All three landed in `_dlq` with raw text, reason, topic, partition, offset and time; the consumer kept going. **Not handled:** nobody reads the DLQ, so a quarantined row stays there until someone looks. |
| Schema change | Partly | Consumer: an unknown `schema_version` or an extra field is rejected to the DLQ. Extractor: none | Tested for the consumer (the version 2 event above). If the producer adds a field to version 1, every such event is rejected: loud, but it empties the stream until the schema file is updated. The extractor runs `SELECT *`, so a new column silently appears in new files only, and a renamed or dropped column silently disappears. Not tested. |
| Duplicate after a restart | **Not handled** (by design) | Consumer writes before it commits, so duplicates are the price of never losing a batch. Extractor saves its cursor after the write | Tested: I killed the consumer between write and commit; the restart gave 9 files, 1,403 rows, 1,203 distinct `event_id`, **200 duplicates**: one flush of 200 rows. Bronze keeps them; silver must deduplicate on `event_id`. The extractor can repeat its last batch only if it dies between the write and the cursor save. Not tested. |
| Credential expires | **Not handled** | Nothing renews or warns | Tested by accident: my Google credentials expired during this work and writing to the bucket failed with `invalid_grant`. The consumer crashes at the write, before committing, so it loses nothing and re-reads on restart. A rotated PostgreSQL password makes the extractor exhaust its retries and exit. In both cases the pipeline stops and stays stopped. |
| Bucket write fails | Partly | The exception ends the process before the offset or cursor is saved | Reasoned, same mechanism as the line above: nothing is lost, the batch is read again. No retry on the write itself. |
| Late event | Yes | Partition by `event_time`, not `emitted_at` | Reasoned: a late event lands in the day it happened. That day may already have been read by a downstream job (lesson 7). |
| Small files | **Not handled** | `BATCH` and `BATCH_ROWS` settings only | Tested: `BATCH=200` wrote 151 files for 24,807 events; `order_id` batches of 50,000 scattered over 36 months gave 191 files for the orders load, 38 with one batch. Lesson 2's over-partitioning cost, paid again. |

## Where the credentials live

Nothing is in the repository; `.gitignore` blocks `.env*`, `*credentials*.json`
and key files, and the pipelines read everything from the environment.

| Credential | Where | Who can read it |
|---|---|---|
| PostgreSQL password (`PGPASSWORD`) | Environment of the shell that starts the extractor. The company stack's local default is in its own repository, not here. The extractor exits if it is unset. | Whoever can start a process on my machine |
| Google Cloud access for the bucket | Application Default Credentials, `~/.config/gcloud/application_default_credentials.json`, created by `gcloud auth application-default login` as my own user | My account only; it expires and has to be renewed by hand |
| Kafka | None: the local broker has no authentication | Anything that can reach `localhost:9092` |
| Cursor and consumer-group state | `.state/` (ignored by git) and the Kafka group `clickstream-group-bronze` | Not secrets |

This is a development setup. In production the PostgreSQL password would come
from a secret store, and the pipelines would run as a service account instead
of my own user; the service accounts could not be created with my permissions
(see [`infra/iam.md`](../infra/iam.md)).
