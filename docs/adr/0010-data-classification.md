# ADR-0010: Grant access by data class, enforce it where the engine allows, and say where it does not

- **Status:** accepted
- **Date:** 2026-11-01
- **Author:** Group Julius
- **Lesson:** L10

## Context

Bronze holds `customer.pwd`, `payment_details.card_no` and `cvv`, names, phones and
street addresses ([data dictionary](../data-dictionary.md)). Nothing in the platform
knew that. The bronze bucket is readable by every `projectViewer` of the shared project,
the whole class ([`infra/iam.md`](../../infra/iam.md)), and a query for a phone number
worked for every group member since lesson 4 without anyone granting it.

What we measured while trying to fix that, in `data-engineering-a` on 2026-11-01:

- **The sensitive columns are in bronze, and bronze is not tagged.** `bronze_julius` is plain
  external tables over Parquet in Cloud Storage. BigQuery refused a policy tag on one:
  *"Policy tags are not supported on plain external tables. Use a BigLake table instead."*
- **A tag can be applied and still protect nothing from a given reader.** On a synthetic table we tagged
  three columns, the schema returned the tags, and the query still ran. The reading account holds
  `datacatalog.categories.fineGrainedGet` on the tag with no binding on the tag itself, so the
  permission is inherited from above it. We could not find out from where.
- **Silver is views and gold holds no person.** `stg_shipping_details` already drops street, zip
  and phone, and no gold column identifies anyone (see [`governance.md`](../governance.md)).
- **We cannot change project-level IAM or create service accounts**, so the role a
  "machine consumer" would use does not exist.

## Options considered

| Option | Buys you | Costs you |
|---|---|---|
| **Classify columns, grant on the class (ours)** | One rule survives new tables: a new `phone` column is handled by tagging it, not by editing a grant. Auditable: the list of what is sensitive is a file | Two grants to reason about (the data role and the tag role). A tag silently protects nothing if misconfigured, and some storage cannot carry one |
| A view per consumer | Exactly the right shape for each reader, no tagging | A view to maintain per consumer, forever, and each one a place where a column can be added by mistake. Does not stop the view's owner reading the base table |
| A dataset (or bucket) per sensitivity level | Simple, coarse, hard to get wrong. A grant on a dataset is easy to read | The same data copied twice and two things to keep in step. It splits by *table*, not by *column*, so a table with one phone column moves wholesale |
| Trust people not to query it | Nothing to build | It is not a control. The audit log will eventually show who did |

## Criteria

- **Does one rule survive the next table?** Only classification does. A view or a dataset has to be remade.
- **Can we do it with the permissions we have?** Rules out the machine-role part of every option, equally.
- **Does it fail loudly or silently?** Classification can fail silently (a tag nobody is refused by);
  that is the criterion it scores worst on, and it is why verification is part of the decision.
- **Does it match where our sensitive data really is?** Bronze, which the tag cannot reach today.

## Decision

**Classify every column into six classes** (`public`, `internal`, `pii.identifier`, `pii.contact`,
`secret`, `unclassified`), keep the list in [`docs/governance.md`](../governance.md), and give three of
them policy tags in a Terraform-declared taxonomy. Grant access by class in the access matrix, with a
written route for every "no".

**Enforce where the engine allows, and use the layers where it does not.** Gold has no personal data
and silver is views: the layer boundary already does what a dataset-per-sensitivity would, for free.
The tag is for tables BigQuery can protect (native and BigLake). The bronze bucket is protected by who may
read the bucket, which is IAM on a resource, not a column tag.

**Say what is not enforced.** [`governance.md`](../governance.md) section 4 lists every gap, so that a
reader of the classification is never led to believe a column is protected because it is classified.

## Consequences

- **Easier:** answering "show me your classification and your access matrix" with a file; adding a column
  is one row and one tag; the cost of a new consumer is a row in the matrix, not a new view.
- **Harder:** the tag and the data role must both be right, and a taxonomy delete is a one-call way to
  unprotect every tagged column while the schemas keep pointing at it (shown in the demo, not by us). Treat
  `roles/datacatalog.categoryAdmin` as a privileged role.
- **Not true today:** no column of the group's datasets carries a tag. The decision is the model; the
  enforcement on bronze is still to do, and the matrix says "no" to roles that the platform cannot yet refuse.
- **Verification is part of the decision.** Reading a schema proves intent. The only check is to read the
  column with an account that should be refused. We have not seen that refusal yet (see the context).

## What would change my mind

- **If BigLake tables over bronze were possible for us** (a BigQuery connection and a bucket role for its
  service account): tag the bronze columns, and the model above holds end to end.
- **If every account in the project turns out to hold `fineGrainedGet`**: tags would protect nothing from
  the people we worry about, and a dataset or bucket per sensitivity level (coarse, IAM on a resource) would
  be the control, with tags as documentation only.
- **If a second team shares the platform with different needs per column:** then a view per consumer, on top
  of the classification, becomes worth its upkeep.
- **At ten teams,** the classification stays and the grants move from people to groups, with the owner a
  named person per domain rather than "the group".
