# Bucket access: `gs://data-engineering-a-groupe-julius-bronze`

Every binding on the bucket, read with
`gcloud storage buckets get-iam-policy` on 2026-10-29. Uniform bucket-level
access is on, so there are no per-object ACLs. Becomes Terraform in lesson 8.

| Principal | Role | Scope | Why |
|---|---|---|---|
| `projectOwner:data-engineering-a` | `roles/storage.legacyBucketOwner`, `roles/storage.legacyObjectOwner` | this bucket | Default grant on a new bucket; the course admins and project owners manage it |
| `projectEditor:data-engineering-a` | `roles/storage.legacyBucketOwner`, `roles/storage.legacyObjectOwner` | this bucket | Default grant; every project editor, which includes the other groups' students, can write and delete here |
| `projectViewer:data-engineering-a` | `roles/storage.legacyBucketReader`, `roles/storage.legacyObjectReader` | this bucket | Default grant; every project viewer can read all of bronze, passwords and card data included |

These are the legacy defaults that Cloud Storage adds to every bucket. I added
none and removed none.

## Gap against the design

Bronze holds `customer.pwd` and `payment_details.card_no`/`cvv`
([data dictionary](../docs/data-dictionary.md)), and
[`docs/architecture.md`](../docs/architecture.md) says only the silver job
reads it. The bindings above do not deliver that: the whole project can read
the bucket and editors can overwrite it.

The intended bindings are:

| Principal | Role | Why |
|---|---|---|
| ingestion service account | `roles/storage.objectCreator` | Writes the export; cannot overwrite or delete, which keeps "nothing that arrived is lost" |
| silver service account | `roles/storage.objectViewer` | The only reader |
| group members | `roles/storage.objectViewer` | Verifying a load, removed once the pipeline is trusted |

Not applied. With my account (`iam.serviceAccounts.create` and
`getIamPolicy` on the project are denied) I cannot create the service accounts
or remove the project-level grants. This needs the teaching team or Terraform
in lesson 8.

Lifecycle: [`lifecycle.json`](lifecycle.json), applied and read back
identically. It has no delete action: bronze keeps everything and moves it to
cheaper classes.
