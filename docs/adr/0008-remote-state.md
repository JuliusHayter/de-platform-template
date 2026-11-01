# ADR-0008: Keep Terraform state in a versioned Cloud Storage bucket

- **Status:** accepted
- **Date:** 2026-11-01
- **Author:** Group Julius
- **Lesson:** L08

## Context

Terraform's state is the map from our configuration to real resource ids
([`docs/infra.md`](../infra.md)). Without it, `plan` cannot tell "create this"
from "this already exists". It is not a cache: deleting it orphans the resources.
It also holds whatever the provider returns, in clear text.

Facts that shaped the choice:

- Three people apply from three laptops, and none of them should hold the only copy.
- The project `data-engineering-a` is shared by the whole class, and we cannot
  set project-level IAM or create service accounts (the `403` on
  `iam.serviceAccounts.create` is recorded in [`docs/infra.md`](../infra.md)).
- Today the state describes one bucket and two datasets. It contains no password,
  key or card data; the sensitive data is in the bucket's objects, which the state
  does not hold.

## Options considered

| Option | Buys you | Costs you |
|---|---|---|
| Local state | Nothing to set up | One laptop holds the only copy and nobody else can apply. Lose the laptop and the next `apply` tries to create what exists (`409 already exists`) |
| **A `gcs` bucket (ours)** | Shared, versioned, locked while an apply runs, in the project we already pay attention to | A bucket Terraform cannot manage itself, created by hand once. Its access is the project default (see below) |
| Terraform Cloud | Locking, history, policy and a UI, managed | An account each, and our state on somebody else's platform. Nothing in this course needs what it adds |

## Decision

State lives in `gs://data-engineering-a-groupe-julius-tfstate`, under the prefix
`platform` (object `platform/default.tfstate`), in `europe-west1`, with uniform
bucket-level access and **object versioning on**. The `gcs` backend locks the
state during an apply. The bucket was made by hand, as the first and only manual
resource, with:

```
gcloud storage buckets create gs://data-engineering-a-groupe-julius-tfstate --location=europe-west1 --uniform-bucket-level-access
gcloud storage buckets update gs://data-engineering-a-groupe-julius-tfstate --versioning
```

## Who can read that bucket

Read on 2026-11-01 with `gcloud storage buckets get-iam-policy`:

| Principal | Role | Effect |
|---|---|---|
| `projectOwner`, `projectEditor` of `data-engineering-a` | `legacyBucketOwner`, `legacyObjectOwner` | Read, **overwrite and delete** the state |
| `projectViewer` of `data-engineering-a` | `legacyBucketReader`, `legacyObjectReader` | Read the state |

These are the defaults every new bucket gets. We added none and removed none, so
**every student with access to the project can read our state and every editor
can overwrite or delete it.** That is the same gap as on the bronze bucket
([`infra/iam.md`](../../infra/iam.md)), and for the same reason: we cannot change
project-level grants. What is exposed today is the shape of our platform (names and
ids of three resources), not secrets. That stops being true the day a resource that
returns a generated password or key is added, and it should block that resource.
L10 audits this; the intended fix is a binding for the group members only.

## What happens if somebody deletes the state file

Tested in reasoning, not by deleting ours: with versioning on, a delete only adds
a delete marker, and the 3 earlier versions of `default.tfstate` are still listed
by `gcloud storage ls -a gs://data-engineering-a-groupe-julius-tfstate/platform/`.
The bucket also has the default 7-day soft-delete window.

- **Deleted, versions kept (the case we prepared for):** restore the last good
  generation with `gcloud storage cp 'gs://.../platform/default.tfstate#<generation>' gs://.../platform/default.tfstate`,
  then `terraform plan` must say `No changes`. Minutes.
- **State and versions both gone:** the resources keep existing and keep costing,
  but Terraform no longer knows they are managed. The next `plan` says `3 to add`
  and an `apply` would fail on names already taken. The way back is `terraform import`
  for each resource, and `imports.tf` is kept in the repository for exactly this:
  three blocks, one `apply`. It is short only because the platform is small.
- **A truncated or corrupted state** is recovered the same way, from the previous version.

What it costs us to lose it is therefore: minutes with versioning, an evening of
imports without it. The versioning is not optional, and neither is keeping
`imports.tf` in step with `main.tf`.

## Consequences

- Everyone applies against the same state and a second concurrent `apply` is refused
  (`Error acquiring the state lock`). A crashed run can leave a lock: `force-unlock`
  only when nobody is applying.
- The backend block cannot use variables, so the bucket name is written in
  `versions.tf`. Another group copying this repository must change it.
- The state bucket is the one resource Terraform does not manage. If it is deleted,
  nothing in the repository recreates it except the two commands above.
- State is never committed: `.gitignore` excludes `*.tfstate*` and `.terraform/`, and
  `git log --all -- 'infra/terraform/*.tfstate'` finds nothing. That stops an accident,
  not a determined mistake, which is why the bucket's access matters.

## What would change my mind

- **A resource that returns a secret** (a generated key or password): the state would
  then need restricted access first, or the secret would have to stay out of Terraform.
- **Several environments or several teams applying:** then Terraform Cloud's policy and
  run history would be worth an account each.
- **L10 giving us the right to set bucket IAM:** restrict the state bucket to the group
  members, and declare that binding with `google_storage_bucket_iam_member`.
