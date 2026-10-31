# Runbook: a pipeline run failed

For whoever is on call at 3am and did not build this. The DAG is `marketplace_daily`; it
extracts from PostgreSQL and then runs `dbt build`. Airflow is at http://localhost:8080
(8080 unless that port was taken when it was installed)
on the machine that runs it (user `airflow`, password `airflow` locally).

## 1. How do I know something is wrong?

- A line appears in `alerts.log` in the Airflow folder (and in Slack, if configured):

```
    2026-10-31T14:59:12+00:00 ALERT marketplace_daily.extract_orders period=2026-10-31 failed after 3 tries; owner=the on-call team member
    2026-10-31T14:59:14+00:00 ALERT marketplace_daily.extract_tables period=2026-10-31 failed after 3 tries; owner=the on-call team member
```

  It fires **once per failed task, after the last retry**, never on a retry. So a task that
  failed twice and then worked sends nothing; if you got one, the task is really down.
- The Airflow home page shows the DAG's last run red.

Alerts go to **the on-call team member**.

## 2. What do I look at first?

1. Airflow, **Dags**, `marketplace_daily`, the red run, the **Graph**. Note which task is red.
   `dbt_build` is the only task that is red *on purpose* when data is bad; the extract tasks
   are red when something is broken.
2. Click the red task, then **Logs**. Read the last 30 lines. The error is almost always
   in the last few.
3. For `dbt_build`, find the line `FAIL <n> <test name>`: the name tells you which table and
   which rule. Everything under it marked `SKIP` was not built, so the marts still hold the
   last good build.

## 3. The three things that usually break

All three happened during this week's work.

| What broke | What the log says | What to do |
|---|---|---|
| **Credentials expired** | `invalid_grant` or `Reauthentication failed` in a task, or in the dbt log | On the machine: `gcloud auth application-default login`. Then clear the task. Google credentials are mounted read-only into the task containers, so nothing needs rebuilding |
| **The source is down or moved** | `connection failed (attempt n/5)` from `extract_*`, or `could not translate host name "db"` | Is the company stack up? `docker ps` must show `albert-marketplace-db-1`. If the database moved, `PGHOST` in the Airflow `.env` is wrong. The extractor already retried five times; Airflow retried twice more |
| **An image tag no longer exists** | `manifest unknown` / `not found` when the task starts, within a second | Open Docker Hub for `julius24h/albert-ingestion` and `albert-dbt`; the tags in use are in the DAG and in `docs/reproduce.md`. If a tag was pruned, set the Variable `ingestion_tag` / `dbt_tag` (Admin, Variables) to one that exists. The retention policy in ADR-0006 keeps the three newest |

## 4. Is it safe to just re-run it?

Mostly yes. Clear the failed task (select it in the Graph, **Clear task**) or the whole run.
Per task, from [`docs/orchestration.md`](../orchestration.md):

- **`extract_tables`: yes.** It overwrites the same files.
- **`dbt_build`: yes.** It replaces its tables.
- **`extract_orders`: yes, with one caution.** It reads past a saved cursor, so a rerun does not
  duplicate. But if the failure was the container *dying* mid-write, the rerun can write that
  batch twice, and if the cursor file in `state/.state/` was deleted it will write every order
  again. Nothing reads `bronze/orders_pg/` yet, so the cost today is storage, not a wrong number.
  Before clearing `extract_orders` after a crash, look at `state/.state/extract_orders.json`:
  it must exist.

**Do not clear a run that failed because of the quality gate** until you know why it failed.
That failure is the pipeline working: a test refused to let bad data replace the marts.
Re-running it will fail the same way. Find the failing test (step 2), find the rows, fix or
remove them in bronze, then re-run.

## 5. Who do I tell, and when do I stop?

- **Tell the on-call team member** as soon as you have read the log, with: the DAG run id, the task,
  the last line of the error. Do not wait to fix it first.
- **Stop and escalate** when: you have been through steps 1 to 4 for 30 minutes; or the failing
  test is on a mart (`fct_*`, `dim_*`) and the cause is not obvious; or the failure is
  credentials and `gcloud auth application-default login` does not fix it.
- **Never** delete a table, a bucket object or a Variable to "see what happens".

## What the fire drill taught me that is not above

- The retry delay is deliberately long (120 s). During the drill it was 15 s so it
  would finish; with the real value a failing task takes about 120 x 2 s longer before it alerts,
  so do not expect an alert in the first minutes.
- A run where **nothing is red but nothing changed** is not covered by any alert here: an
  extract that reads zero new rows succeeds. Lesson 9's measurements are the answer to that.
