# Infrastructure

The platform is declared as code in [`terraform/`](terraform/) (L08): the bronze
bucket with its lifecycle rules and the BigQuery datasets, adopted from what was
created by hand in L02-L05, with remote state in a versioned bucket.

- **What exists and why:** [`docs/infra.md`](../docs/infra.md), including what is
  deliberately *not* declared (service account refused with a 403, shared registry).
- **Where state lives:** [ADR-0008](../docs/adr/0008-remote-state.md).
- **Changes go through code**, then `terraform plan` read by a person, then a pull
  request. CI runs `fmt -check` and `validate` on every pull request touching `infra/`.
- [`lifecycle.json`](lifecycle.json) is the L02 file the bucket's lifecycle came from;
  `terraform/main.tf` now holds the same three rules.
- [`iam.md`](iam.md): the access audit. Still the project defaults; L10 tightens it.
- **L09** adds labels and budgets; **L10** tightens access.
