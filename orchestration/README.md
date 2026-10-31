# Orchestration

The DAG that runs the containerised ingestion and dbt jobs on a schedule.

| File | What |
|---|---|
| `dags/marketplace_daily.py` | The DAG: `extract_orders` and `extract_tables` in parallel, then `dbt_build` as the quality gate |

What it does, how each task stays safe to rerun, and the drills that prove it:
[`docs/orchestration.md`](../docs/orchestration.md). When it fails:
[`docs/runbooks/failed-run.md`](../docs/runbooks/failed-run.md). Why reruns are safe:
[ADR-0007](../docs/adr/0007-idempotency.md).

To run it locally, Airflow 3.3.2 is installed in a short folder outside the repository, with
`REPO_DAGS_DIR` pointing at `orchestration/dags/`. The setup is the course's setup page plus one
override file that mounts the Docker socket and this folder.
