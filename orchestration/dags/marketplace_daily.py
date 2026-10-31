"""Albert's Marketplace, daily: extract from PostgreSQL, then build and test with dbt.

Structure only. No pandas, no query and nothing slow at import time: the scheduler
re-parses this file on a timer, and work done here slows it for everybody.

Every job is the image from lesson 6, pinned to a tag, run through the host's
Docker. The tags can be swapped without editing this file, with the Airflow
Variables `ingestion_tag` and `dbt_tag`; the dbt output dataset with `dbt_dataset`.
That is how the drills in docs/orchestration.md break things on purpose.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

import pendulum
from airflow.sdk import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# These are the HOST's paths, not this container's: a DockerOperator task asks the
# host's Docker daemon to start a container, and the daemon resolves every mount.
HOST_DIR = os.environ["HOST_DIR"]
GCLOUD_DIR = os.environ["GCLOUD_DIR"]
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
BRONZE_URI = os.environ.get("BRONZE_URI", "gs://data-engineering-a-groupe-julius-bronze")
RETRY_DELAY = timedelta(seconds=int(os.environ.get("RETRY_DELAY_SECONDS", "120")))
ALERT_LOG = "/opt/airflow/alerts/alerts.log"

# Jinja, rendered just before each task runs.
INGEST_IMAGE = "julius24h/albert-ingestion:{{ var.value.get('ingestion_tag', '2026-10-30-5185b2e') }}"
DBT_IMAGE = "julius24h/albert-dbt:{{ var.value.get('dbt_tag', '2026-10-30-5ed84e8') }}"
DBT_DATASET = "{{ var.value.get('dbt_dataset', 'l05_julius') }}"
# A run started with the Trigger button or `airflow dags trigger` has no logical date, so no data interval:
# data_interval_start is not even defined in its context and `| ds` fails to render (observed:
# "'data_interval_start' is undefined"). `default(..., true)` falls back to the day the run was created.
PERIOD = "{{ (data_interval_start | default(dag_run.run_after, true)) | ds }}"

# Read-only: a task has no business editing the gcloud config.
ingest_gcloud = Mount(source=GCLOUD_DIR, target="/home/ingest/.config/gcloud", type="bind", read_only=True)
dbt_gcloud = Mount(source=GCLOUD_DIR, target="/home/dbt/.config/gcloud", type="bind", read_only=True)
# The extractor keeps its cursor here, so it survives the container.
state_mount = Mount(source=f"{HOST_DIR}/state", target="/data", type="bind")


def alert(context):
    """Runs once, when a task has failed for the last time. Not on every retry."""
    ti = context["task_instance"]
    owner = os.environ.get("ALERT_OWNER", "nobody")
    line = (
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} ALERT "
        f"{ti.dag_id}.{ti.task_id} period={context['data_interval_start']:%Y-%m-%d} "
        f"failed after {ti.try_number} tries; owner={owner}"
    )
    print(line, flush=True)
    try:
        with open(ALERT_LOG, "a") as f:
            f.write(line + "\n")
    except OSError as exc:  # an alert must never fail the callback
        print(f"could not write {ALERT_LOG}: {exc}", flush=True)
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        try:
            req = urllib.request.Request(
                webhook, data=json.dumps({"text": line}).encode(), headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:  # noqa: BLE001
            print(f"could not post to Slack: {exc}", flush=True)


ingest_env = {
    "PGHOST": "db",
    "PGPASSWORD": os.environ.get("PGPASSWORD", ""),
    "BRONZE_URI": BRONZE_URI,
    "PERIOD": PERIOD,   # for the log; these two jobs read by cursor / full refresh, not by day
    "BATCH_ROWS": "500000",   # one query for the first full load, so it writes ~36 files, not hundreds
}

with DAG(
    dag_id="marketplace_daily",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,   # two runs would race on the same cursor and the same marts
    default_args={
        "retries": 2,
        "retry_delay": RETRY_DELAY,
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": alert,
    },
    tags=["albert", "l07"],
) as dag:

    # Incremental on order_id; new files each run. The cursor is saved after the write.
    extract_orders = DockerOperator(
        task_id="extract_orders",
        image=INGEST_IMAGE,
        command="python extract_orders.py",
        network_mode="albert-marketplace_default",
        environment=ingest_env,
        mounts=[state_mount, ingest_gcloud],
        auto_remove="success",
        mount_tmp_dir=False,
    )

    # Full refresh of six tables; each table is one object, overwritten.
    extract_tables = DockerOperator(
        task_id="extract_tables",
        image=INGEST_IMAGE,
        command="python extract_tables.py",
        network_mode="albert-marketplace_default",
        environment=ingest_env,
        mounts=[state_mount, ingest_gcloud],
        auto_remove="success",
        mount_tmp_dir=False,
    )

    # The quality gate. `dbt build` tests each model as it is built and skips
    # everything downstream of a failure, so a bad row stops the marts from being
    # replaced. `dbt run` then `dbt test` would only report it afterwards.
    dbt_build = DockerOperator(
        task_id="dbt_build",
        image=DBT_IMAGE,
        command="build",
        environment={"GCP_PROJECT_ID": GCP_PROJECT_ID, "DBT_DATASET": DBT_DATASET, "PERIOD": PERIOD},
        mounts=[dbt_gcloud],
        retries=1,
        retry_delay=RETRY_DELAY * 2,
        auto_remove="success",
        mount_tmp_dir=False,
    )

    [extract_orders, extract_tables] >> dbt_build
