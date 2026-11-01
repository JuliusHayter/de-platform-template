# Infrastructure as code

The platform from lessons 2 to 7 is declared in [`infra/terraform/`](../infra/terraform/).
Project `data-engineering-a`, region `europe-west1`, group `julius`. State is in
`gs://data-engineering-a-groupe-julius-tfstate/platform/`
([ADR-0008](adr/0008-remote-state.md)).

The check that matters, run on 2026-11-01 against the real project:

```
$ terraform plan
No changes. Your infrastructure matches the configuration.
```

## Why each resource exists

| Resource | Why it exists | Made by hand? |
|---|---|---|
| `google_storage_bucket.bronze` (`data-engineering-a-groupe-julius-bronze`) | The bronze landing zone from L02: raw Parquet from the operational database, three lifecycle rules (Nearline at 30 days, Coldline at 90, Archive at 365, prefix `bronze/`), no delete action | Created by hand in L02, **adopted** with an `import` block |
| `google_bigquery_dataset.bronze` (`bronze_julius`) | Holds the external tables over the bronze files, created by the SQL in `warehouse/` (L04) | Created by hand, **adopted** |
| `google_bigquery_dataset.dbt` (`l05_julius`) | Where dbt builds silver and gold (L05); the default dataset of the L07 DAG | Created by hand, **adopted** |
| `google_bigquery_dataset.warehouse` (`warehouse_julius`) | The L04 measurement copies of the same data (native, partitioned and clustered tables). **Missed in L08** and adopted in L09 when the ledger listed every dataset | Created by hand in L04, **adopted** in L09 |
| State bucket (`data-engineering-a-groupe-julius-tfstate`) | Holds Terraform's state, with object versioning on. Terraform cannot create the place it keeps its own state | **Yes, once**: `gcloud storage buckets create gs://data-engineering-a-groupe-julius-tfstate --location=europe-west1 --uniform-bucket-level-access`, then `gcloud storage buckets update ... --versioning`. In L09 it also got labels and a lifecycle rule (`infra/state-lifecycle.json`) by hand, because Terraform does not manage it |

Tables are not declared. The external tables come from the SQL in `warehouse/`
and the silver and gold tables from dbt; declaring them here too would give two
tools the same resource.

## What is not declared, and why

| Not declared | Why |
|---|---|
| Service account for the pipeline | **Tried and refused.** Applying a `google_service_account` (`pipeline-julius`) returned `403: Permission 'iam.serviceAccounts.create' denied on resource '//cloudresourcemanager.googleapis.com/projects/data-engineering-a'`. Our project does not grant it, on purpose (L10 is about why). The jobs still run as a person ([`ingestion-failure-modes.md`](ingestion-failure-modes.md)). The resource was removed from the configuration rather than left failing |
| Resource-level IAM (`google_storage_bucket_iam_member`, `google_bigquery_dataset_iam_member`) | The intended bindings in [`infra/iam.md`](../infra/iam.md) are for service accounts that do not exist. The bindings that do exist are the legacy project defaults (`projectOwner`, `projectEditor`, `projectViewer`), which Terraform cannot remove without the project-level role we lack. Declaring them would present the gap as if it were the design. L10 fixes it |
| Artifact Registry repository `dataeng` | One repository for the whole class (`DAT09-02 ... images des élèves`), not ours. Managing it from our state would make us the owner of a shared resource. Our images are on Docker Hub ([ADR-0006](adr/0006-image-tags.md)) |
| Dataset access lists (`access`) | Left unmanaged so Terraform does not rewrite the owner entries set when the datasets were created |
| Enabled APIs (33 on the project) | `google_project_service` needs project-level permission, and the teaching team enabled them. Not ours to declare |
| Dataset `julius_goat` | Has `julius` in its name and one external table, but nothing in this repository references it. Not adopted without knowing whether it is ours |

## Adoption: what we saw

- Plan before the import blocks: `Plan: 3 to add, 0 to change, 0 to destroy.` Terraform wanted to create things that already exist, because its state was empty.
- With `imports.tf`: `Plan: 3 to import, 0 to add, 0 to change, 0 to destroy.` Apply: `Resources: 3 imported, 0 added, 0 changed, 0 destroyed.`
- Then `No changes. Your infrastructure matches the configuration.` Our description matched on the first try, including the three `matches_prefix` lifecycle rules.
- Provider pinned by the committed `.terraform.lock.hcl`: `hashicorp/google 8.9.0`, constraint `~> 8.4`. Terraform CLI 1.17.0, `required_version >= 1.9`.
- `terraform.tfvars` and `.terraform/` are ignored, and `git log --all -- 'infra/terraform/*.tfstate'` finds nothing.

## A drift we caused and caught

A mechanism nobody has seen work is a claim, so we broke the bucket on purpose.

**First attempt: a label, which showed nothing.** We added a label with
`gcloud storage buckets update gs://data-engineering-a-groupe-julius-bronze --update-labels=owner=drift-test`
and `terraform plan` answered `No changes`. The google provider treats labels as
non-authoritative: it only compares the labels written in the configuration, so a
label added outside Terraform is invisible to it. A label is a bad drift test with
this provider, and a console label can sit on the bucket for months without a plan
ever reporting it. We removed the label.

**Second attempt: a lifecycle rule, which Terraform sees.** We replaced the rules
with `gcloud storage buckets update ... --lifecycle-file=...` where the Nearline
rule had `age: 60` instead of 30, then ran `terraform plan`:

```
Terraform will perform the following actions:

  # google_storage_bucket.bronze will be updated in-place
  ~ resource "google_storage_bucket" "bronze" {
        id                          = "data-engineering-a-groupe-julius-bronze"
        name                        = "data-engineering-a-groupe-julius-bronze"
        # (18 unchanged attributes hidden)

      ~ lifecycle_rule {
          - condition {
              - age                                     = 60 -> null
              - days_since_custom_time                  = 0 -> null
              - days_since_noncurrent_time              = 0 -> null
              - matches_prefix                          = [
                  - "bronze/",
                ] -> null
              - matches_storage_class                   = [] -> null
              - matches_suffix                          = [] -> null
              - num_newer_versions                      = 0 -> null
              - send_age_if_zero                        = false -> null
              - send_days_since_custom_time_if_zero     = false -> null
              - send_days_since_noncurrent_time_if_zero = false -> null
              - send_num_newer_versions_if_zero         = false -> null
              - size_above_bytes                        = 0 -> null
              - size_below_bytes                        = 0 -> null
              - with_state                              = "ANY" -> null
                # (3 unchanged attributes hidden)
            }
          + condition {
              + age                    = 30
              + matches_prefix         = [
                  + "bronze/",
                ]
              + matches_storage_class  = []
              + matches_suffix         = []
              + with_state             = (known after apply)
                # (3 unchanged attributes hidden)
            }

            # (1 unchanged block hidden)
        }

        # (4 unchanged blocks hidden)
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

What the output shows:

- **It never says "drift".** The words are `will be updated in-place`, exactly what it prints when we edit the file ourselves. The only clue is that nobody edited the file.
- **It moves back towards the configuration** (`age = 30`), because the configuration is what Terraform treats as true. It proposes to undo the change made outside.
- **It is noisy.** One number changed, and the whole `condition` block is removed and added again, with fourteen attributes going to `null`. The `+ condition` block is the one to read.

**Decision: we overwrote** (`terraform plan -out`, then `terraform apply` of that
saved plan: `0 added, 1 changed, 0 destroyed`). The 60 days was our own test,
made to see the mechanism work. Nobody depended on it, and returning to 30 lost
nothing. Reading the age back from the bucket gave `30`, and the next plan said
`No changes`.

**If it had been an emergency fix during an incident, we would have adopted it:**
find out who made the change and why, put the new value in `main.tf`, commit it
through a reviewed pull request, then apply so the repository learns what
production already does. Overwriting would delete somebody's fix silently, and in
an incident that is worse than an untidy configuration. Nothing in Terraform runs
by itself, so the control is to run `plan` on a schedule or on every pull request,
which makes the gap between the click and the discovery hours instead of weeks.

## Running it

```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars   # then fill in
gcloud auth application-default login
cd infra/terraform
terraform init
terraform plan        # read it: a "-/+" or "destroy" means stop
```

Apply only from a saved plan (`terraform plan -out=tf.plan`, then
`terraform apply tf.plan`), never with `-auto-approve`.

CI runs `terraform fmt -check -recursive`, `terraform init -backend=false` and
`terraform validate` on every pull request touching `infra/`
([`.github/workflows/terraform.yml`](../.github/workflows/terraform.yml)), with no
credentials. `plan` stays on our own machines.

## Not done

- No `plan` in CI: it needs a federated identity (Workload Identity Federation), which our project cannot configure.
- The state bucket carries the legacy project-default IAM (see [ADR-0008](adr/0008-remote-state.md)).
- Labels are declared and applied on every resource (the dataset owner applied the three datasets, which our account is refused). No budget alert from this account. See [`docs/costs.md`](costs.md).
