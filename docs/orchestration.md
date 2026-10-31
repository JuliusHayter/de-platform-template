# Orchestration

The pipeline runs as one Airflow DAG, `marketplace_daily`
([`orchestration/dags/marketplace_daily.py`](../orchestration/dags/marketplace_daily.py)),
on `@daily`. It runs the two images from lesson 6, pinned
(`julius24h/albert-ingestion:2026-10-30-5185b2e`, `julius24h/albert-dbt:2026-10-30-5ed84e8`),
through the host's Docker.

```
extract_orders ──┐
                 ├──> dbt_build   (the quality gate)
extract_tables ──┘
```

Every number below was measured on 2026-10-31 by `l07_teammate.sh`, run on one
team member's machine with Airflow 3.3.2. Raw outputs were kept in the Airflow folder
(`measurements/`) and are quoted, not retyped. The drills ran with a retry delay of
15 s so they would finish; the committed DAG defaults to 120 s.

## What it does not do yet

Said first, because it is the most important limit of this pipeline:

- **`dbt_build` does not read what the extract tasks write.** The dbt sources are the
  lesson 2 external tables over `bronze/<table>/`. The extractors write to
  `bronze/orders_pg/` and `bronze/<table>_pg/`, which no dbt model reads. So the DAG runs
  end to end, but the marts it builds are from the static export. Repointing the sources
  (or adding a step that merges `_pg` into them) is the next piece of work.
- **The schedule was not waited for.** The DAG is `@daily`. Airflow creates DAGs paused, and one
  `airflow dags unpause marketplace_daily` (or the toggle in the UI) turns the schedule on; it was
  left paused after the drills. To avoid waiting
  until midnight UTC, one run was started by hand with `airflow dags trigger` (it ran
  through the scheduler and the worker, and ended `success`), and the drills used
  `airflow dags test`, which runs inline.
- **The period does not select data.** `extract_orders` reads past a cursor and
  `extract_tables` copies whole tables, so `PERIOD` is passed for the log and nothing else.
  A back-fill therefore repeats the same work; that is what makes it safe here.

## Idempotency: why running each task twice is safe

| Task | What it writes | Why running it twice is safe |
|---|---|---|
| `extract_tables` | `bronze/<table>_pg/part-0.parquet` for six tables | **Overwrites one object path.** The second run replaces the first byte for byte; there is no second file. Measured: `product_pg` held 42859 rows after run 1 and 42859 after run 2. |
| `extract_orders` | new files in `bronze/orders_pg/dt=YYYY-MM/` | **A cursor on `order_id` (`>`), saved after the write**, in a file on a mounted volume. A rerun reads only orders past the cursor. Measured: 260486 rows after run 1 and 260486 after run 2. **Not fully idempotent:** if the container dies between the write and the cursor save, the rerun writes that batch twice; and if the cursor file is lost the whole table is written again (see below). |
| `dbt_build` | `fct_*`, `dim_*` tables and the staging/intermediate views in the dbt dataset | **`CREATE OR REPLACE`**: dbt replaces each table in full. Measured: revenue was 35355484.83 after run 1 and 35355484.83 after run 2. |

BigQuery does not enforce uniqueness, so no mechanism above relies on a primary key. The
decision, the alternatives and the task I am least sure of are in
[ADR-0007](adr/0007-idempotency.md).

Last line the second `extract_orders` printed: `0 new row(s); cursor now 260522`.

## Retries and the alert

Every task retries twice (`dbt_build` once), `retry_delay` 120 s (twice that for
dbt). The extractors already retry their own connection five times with a growing delay,
so Airflow's delay is deliberately longer than the thing it retries: a rerun a few seconds
later would meet the same outage.

The alert is `on_failure_callback`, which fires once, after the last retry. It appends a line
to `alerts.log` in the Airflow folder and, if a Slack webhook was configured, posts it to
Slack. **Who sees it: Alexandro Bizeul.** The drill ran with that role as the recipient;
to name a person, set `ALERT_OWNER` in the Airflow `.env` (it appears in each alert line as
`owner=...`) and write the name here. What they are expected to do: open
[`runbooks/failed-run.md`](runbooks/failed-run.md) and start at step 1.

Drill A: the extract tasks were pointed at an image tag that does not exist
(`ingestion_tag=does-not-exist`). Result: the tasks failed after their retries and 2
alert line(s) were written, one per failed task and not one per attempt. Whether a person
saw it: **not confirmed by a person (the script ran unattended)**.

```
    2026-10-31T14:59:12+00:00 ALERT marketplace_daily.extract_orders period=2026-10-31 failed after 3 tries; owner=the on-call team member
    2026-10-31T14:59:14+00:00 ALERT marketplace_daily.extract_tables period=2026-10-31 failed after 3 tries; owner=the on-call team member
```

## The quality gate, and proof that it stops the pipeline

The gate is `dbt build`: each model is tested as it is built, and everything downstream
of a failure is skipped.

Drill B. A poison row was added to bronze: one extra Parquet file in
`bronze/order_items/` repeating the line `(order_id=1, p_id=B097R46CSY)`. It is designed
against the test `unique_combination_of_columns` on `(order_id, p_id)` in the staging and
intermediate models. dbt wrote to a scratch dataset, so the group's marts were not touched.

| Variant | What ran | Marts afterwards |
|---|---|---|
| Clean | the DAG, no poison | revenue **35355484.83** over 368227 lines |
| Alarm only | `dbt run`, then `dbt test`, poison present | revenue **35355528.79** over 368228 lines. Tests: `Done. PASS=55 WARN=4 ERROR=3 SKIP=0 NO-OP=0 REUSED=0 TOTAL=62`. First failing: `dbt_utils_unique_combination_of_columns_fct_order_items_order_id__p_id` |
| Lock | the DAG with `dbt build` as the gate, poison present | revenue **35355484.83** over 368227 lines. Gate: `Done. PASS=49 WARN=3 ERROR=1 SKIP=26 NO-OP=0 REUSED=0 TOTAL=79`. First failing: `dbt_utils_unique_combination_of_columns_stg_order_items_order_id__p_id`. Nodes skipped: 26 |
| Reset | clean rebuild after removing the poison | revenue 35355484.83 |

With run-then-test the bad row **reached the marts**: revenue went from 35355484.83 to 35355528.79. With dbt build as the gate it did **not**: revenue stayed at 35355484.83.

The alert for the gated run:

```
    2026-10-31T15:02:17+00:00 ALERT marketplace_daily.dbt_build period=2026-10-31 failed after 2 tries; owner=the on-call team member
```

The poison file was deleted afterwards and the scratch dataset dropped.

## Back-fill

Range: 2026-10-28 to 2026-10-30 (three runs; `--dry-run` listed 3 run(s)).

```
        - reprocess_behavior = None
        - run_on_latest_version = True
    Runs to be attempted:
    +---------------------------+-----------------+------------------+
    | logical_date              | partition_key   | partition_date   |
    +===========================+=================+==================+
    | 2026-10-28 00:00:00+00:00 |                 |                  |
    +---------------------------+-----------------+------------------+
    | 2026-10-29 00:00:00+00:00 |                 |                  |
    +---------------------------+-----------------+------------------+
    | 2026-10-30 00:00:00+00:00 |                 |                  |
    +---------------------------+-----------------+------------------+
```

| | `bronze/orders_pg` rows | `product_pg` rows |
|---|---|---|
| Prediction, written before | 260486 | 42859 |
| Before the back-fill | 260486 | 42859 |
| After | 260486 | 42859 |

Reasoning for the prediction: the period does not select data (above), the cursor is already
past every order, and the company's load generator was paused, so three runs add nothing.
The prediction held: 260486 rows before and 260486 after. Run states afterwards: 3 success, 0 failed.

The three back-fill runs did not run one after the other: their task logs end within the same
second (`extract_orders` in each, then `extract_tables`, then `dbt_build`), so they ran at the same
time. A back-fill has its own concurrency limit and does not obey the DAG's `max_active_runs=1`.
All three read the same cursor and found nothing new, which is why the count did not move.
With new orders arriving, three concurrent extractions would each have written them (hazard 1
below). The prediction held for that reason, and it would not have held on a busy day.

## Two hazards found while running it

**1. Two runs at once write everything twice.** In a first attempt of this drill the DAG was
unpaused before the measurements. Airflow immediately started a scheduled run of its own while
a manual `airflow dags test` run was extracting. Both read the cursor file at the start, both
found nothing there, and both extracted every order: `bronze/orders_pg/` ended with 445,563
rows for 259,014 orders in the source, in 72 files. `max_active_runs=1` did not prevent it,
because one of the two runs was started by `airflow dags test`. The attempt was stopped, the
prefix emptied and the drills redone with the DAG kept paused until the two steps that need the
scheduler. Anything that can start a second run (a manual trigger on top of a schedule, a
back-fill during a daily run) has the same exposure.

**2. A cursor in a local file does not travel.**
`extract_orders` keeps its cursor in a file on the machine that runs it. A new machine starts
at cursor 0 and writes every order again next to the earlier copy. Here, `bronze/orders_pg/` already held 43 file(s) written by an earlier cursor (lesson 3, or an earlier attempt of this drill), and the script emptied it before measuring. Nothing reads `orders_pg` yet, so no figure was wrong, but the cursor should
live somewhere shared (a bucket object, or a BigQuery table) before this reads anywhere that matters.
