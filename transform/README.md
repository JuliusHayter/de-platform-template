# transform: the dbt project

Bronze to silver to gold in BigQuery (`europe-west1`), built with dbt Core 1.12
inside the course image, so nothing is installed locally.

```bash
# once: sign in (a browser opens), and set the two variables
gcloud auth application-default login
export GCP_PROJECT_ID=data-engineering-a

# from this folder
docker run --rm \
  -v "$PWD:/usr/app" -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  -e GCP_PROJECT_ID -e DBT_DATASET=l05_julius \
  charlestng/dbt-bigquery:1.12.1 deps

# then the same command with `build`, `source freshness`, or `docs generate`
```

`DBT_DATASET` is where dbt writes (default `l05_julius`). `profiles.yml` is in
this folder and holds no credential. A clean checkout needs those two variables
and nothing else.

| Folder | Layer | Built as | Why |
|---|---|---|---|
| `models/staging/` | one model per source, one named defect fixed each | view | See [ADR-0005](../docs/adr/0005-materialisations.md) |
| `models/intermediate/` | the joins that make decisions | view | |
| `models/marts/` | the star schema | table | |
| `tests/` | singular tests: the acceptance criteria that are not column checks | | [`docs/acceptance-criteria.md`](../docs/acceptance-criteria.md) |

`dbt_packages/`, `target/` and `logs/` are not committed.
