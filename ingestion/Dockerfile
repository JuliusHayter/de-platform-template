# The ingestion jobs: extract_orders.py (default), extract_tables.py and
# consume_clickstream.py. Build from the REPOSITORY ROOT so the root .dockerignore
# applies:  docker build -f ingestion/Dockerfile -t albert-ingestion:<tag> .

# Pinned at both ends: the exact Python patch release and the Debian it sits on.
FROM python:3.12.12-slim-bookworm

# No .pyc files in a filesystem that is thrown away; unbuffered output so a
# crashed container's logs are not empty.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BRONZE_URI=/data \
    STATE_PATH=/data/.state/extract_orders.json

WORKDIR /app

# The manifest on its own, before the code, so a code change does not reinstall
# pandas and pyarrow.
COPY ingestion/requirements.lock ./
# One layer. A fixed uid so file ownership on a mounted volume is predictable.
RUN pip install --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 10001 ingest \
    && mkdir /data && chown ingest /data

COPY ingestion/extract_orders.py ingestion/extract_tables.py \
     ingestion/consume_clickstream.py ingestion/clickstream.schema.json ./

# Nothing here needs root.
USER ingest
# Exec form: the process is PID 1 and receives the stop signal directly.
CMD ["python", "extract_orders.py"]
