# Ingestion

Pipelines that fill the bronze layer. Python 3.12+, `pip install -r requirements.txt`.

| File | What | Guarantee |
|---|---|---|
| `bronze_export.py` | CSV export to partitioned Parquet (L02, by hand) | n/a |
| `extract_orders.py` | `orders` from PostgreSQL, incremental on `order_id`, to `bronze/orders_pg/` | at-least-once, new rows only |
| `extract_tables.py` | Six more tables, full refresh, to `bronze/<table>_pg/`; secret columns never selected | at-least-once, idempotent |
| `check_secrets_excluded.py` | Reads the output back and fails if a secret column is present | |
| `consume_clickstream.py` | Kafka topic `clickstream` to `bronze/clickstream/`, bad events to `bronze/_dlq/` | at-least-once |
| `clickstream.schema.json` | JSON Schema of an event (version 1), enforced by the consumer | |

All configuration is environment variables; the first lines of each script list
them. Nothing secret is in this folder; see
[`docs/ingestion-failure-modes.md`](../docs/ingestion-failure-modes.md) for where
credentials live.

```bash
# against the company stack, writing to the group bucket
gcloud auth application-default login      # once; expires
export BRONZE_URI=gs://data-engineering-a-groupe-julius-bronze
export PGPASSWORD=...                      # the company database's password

python ingestion/extract_orders.py
python ingestion/extract_tables.py
python ingestion/check_secrets_excluded.py
CONSUMER_GROUP=clickstream-group-bronze BATCH=1000 python ingestion/consume_clickstream.py
```

Leave `BRONZE_URI` unset to write under `./out` instead. The extractor keeps its
cursor in `.state/` (ignored by git); delete that file to read everything again.
There is no Airbyte connection here: see
[ADR-0003](../docs/adr/0003-ingestion-modes.md).

## Image

`Dockerfile` packages the three jobs, built from the repository root:
`docker build -f ingestion/Dockerfile -t albert-ingestion:<tag> .`
`requirements.txt` holds the exact direct dependencies; `requirements.lock` is the
full tree the image installs. After changing `requirements.txt`, regenerate the lock
inside the base image so it matches what the image will really install:

```bash
docker run --rm -v "$PWD/ingestion:/w" python:3.12.12-slim-bookworm \
  sh -c 'pip install -q -r /w/requirements.txt && pip freeze --all | grep -v "^pip=="' > ingestion/requirements.lock
```
