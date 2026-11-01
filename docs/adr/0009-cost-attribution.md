# ADR-0009: Attribute cost with labels applied by Terraform, in one project

- **Status:** accepted
- **Date:** 2026-11-01
- **Author:** Group Julius
- **Lesson:** L09

## Context

Asked what the pipeline costs, we could not answer by query. Nothing carried a label,
and a bill that cannot say whose cost it is gives 30% of its total to "nobody" (the
demo bill in L09). Labels apply from the moment they are set and never backwards, so
every day without them is permanent.

Facts that shaped the choice:

- Everything we own is in `data-engineering-a`, a project shared by the whole class. We
  cannot create projects, and we cannot set organisation-level policy or tags.
- The platform is declared in Terraform since [ADR-0008](0008-remote-state.md), so one
  edit can label every resource, reviewed as a pull request.
- Our spend is inside the free tier. The decision has to work on quantities, not money
  (see [`docs/costs.md`](../costs.md)).
- Observed limits: we are refused `bigquery.datasets.update` on datasets another group
  member owns, we cannot read the billing export, and we cannot edit the budget.

## Options considered

| Option | Buys you | Costs you |
|---|---|---|
| **Labels on every resource (ours)** | One project, one bill, attribution by query. Applied through the code we already review | Labels apply forward only, and nothing enforces them: a resource made in the console has none. Query cost is not labelled unless each job carries a label |
| A project per team | Attribution for free, and a hard boundary for access and for quotas | A project to provision per team, which we cannot do here. Data shared across teams gets awkward |
| Tags instead of labels | Inheritance down the hierarchy, and a policy can require them | Organisation-level setup we do not have |
| Split the bill by hand | Nothing to set up | Somebody's afternoon, every month, and it is always wrong |

## Criteria

- **Can we do it with the permissions we have?** Rules out projects per team and tags.
- **Does it survive the next resource?** Only something in the code review path does.
- **Does it answer "who do I ask"?** A key per question, not a spreadsheet.

## Decision

Four labels on every resource: `team`, `environment`, `pipeline` and `lesson`
(reasons and values in [`docs/costs.md`](../costs.md)). They are set in
`infra/terraform/main.tf` from one `base_labels` local plus a per-resource block, and
never in the console. The state bucket, which Terraform does not manage, is labelled by
hand and says so.

## Consequences

- **Easier:** the answer to "what does the pipeline cost" becomes a `GROUP BY` on the
  `pipeline` label once the billing export reaches us. `terraform plan` shows a missing
  or changed label in review.
- **Harder:** the gaps are ours to watch. Applying labels needs the rights of each resource's
  owner: the three datasets were refused to us and labelled by their owner. Query spend carries no
  label until dbt and the DAG pass one. Spend before 2026-11-01 stays unattributable for good.
- **Not enforced:** a person can still create an unlabelled resource. Nothing here stops that.

## What I would do differently with ten teams

Not more labels. Past about six keys people stop applying them, and the keys do not
fix the real problem, which is that nothing makes anyone use them.

- **One project per team, from Terraform, with its own budget.** The boundary then
  holds for cost, quota and access at once, and the bill splits by project with no label
  discipline at all. Labels stay for the finer cut inside a project (pipeline).
- **Tags required by organisation policy**, so a resource cannot be created without a
  `team`. This is the enforcement that labels lack.
- **A check in CI that fails a pull request** adding a Terraform resource with no
  `labels` block. Cheap, and it covers the case policy does not.
- **A view per team on the billing export**, as in the L09 demo, so each team queries only
  its own rows.
- **Job labels in dbt and in every scheduled query**, because compute is where the money
  goes at scale and a dataset label does not reach it.

## What would change my mind

- **If the organisation gave us tags and policy:** use them instead of labels.
- **If the billing export showed that most cost is in a few resources:** a project for
  those, and labels for the rest.
- **If nobody ever queries the cost by label:** the convention is decoration, and the
  four keys should drop to the two that someone actually reads.
