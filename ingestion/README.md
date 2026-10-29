# Ingestion

Pipelines that fill the bronze layer. Python 3.12+, `pip install -r requirements.txt`.

| File | What | Guarantee |
|---|---|---|
| `bronze_export.py` | CSV export to partitioned Parquet (L02, by hand) | n/a |
| `extract_orders.py` | `orders` from PostgreSQL, incremental on `order_id`, to `bronze/orders_pg/` | at-least-once, new rows only |
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
CONSUMER_GROUP=clickstream-group-bronze BATCH=1000 python ingestion/consume_clickstream.py
```

Leave `BRONZE_URI` unset to write under `./out` instead. The extractor keeps its
cursor in `.state/` (ignored by git); delete that file to read everything again.
There is no Airbyte connection here: see
[ADR-0003](../docs/adr/0003-ingestion-modes.md).

In L06 each job gets its Dockerfile here.
