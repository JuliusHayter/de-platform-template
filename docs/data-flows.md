# Data flows

One row per flow: where the data comes from, what it is, who uses it, how often
it moves, and in which format.

| # | Source | Data | Consumer | Frequency | Format | Notes |
|---|---|---|---|---|---|---|
| 1 | Web shop (checkout) | Orders, lines, payments, stock | PostgreSQL database | Continuous | Database writes | |
| 2 | Web shop (reviews) | Ratings, review texts, photo links | PostgreSQL database | Continuous | Database writes | |
| 3 | PostgreSQL database | Orders, customers, products | Analysts | On demand | SQL queries | Runs directly against the operational database |
| 4 | PostgreSQL database | Selected tables | Spreadsheets | Nightly | CSV export | Opened and reconciled by hand |
| 5 | (Wanted) daily demand | Units per product, country, day | ML team | Daily | Does not exist yet | No pipeline produces this today |

## Under the matrix, answer

- **Which flows carry personal data?**
  Flows 1, 2, 3 and 4 all touch the same operational database, so they carry
  personal data: flow 1 includes payment details and stored card data next to
  the order, flow 2 ties review text and photos to a reviewer, and flows 3 and
  4 expose the `customers` table (and whatever else sits in "selected tables")
  directly to analysts and spreadsheets. Only flow 5 would avoid this, since
  its grain (product, country, day) has no customer-level data to carry — but
  it doesn't exist yet.

- **Which consumers read directly from a system that also serves customers?**
  Analysts (flow 3) and the nightly spreadsheet export (flow 4) both read
  straight from the same PostgreSQL database that the web shop writes to in
  real time (flows 1 and 2). That database serves live checkout and review
  traffic, so analytical queries and exports add load to, and share secrets
  with, a system customers depend on.

- **Where could the same figure be computed twice, in two different ways?**
  Between flows 3 and 4: analysts running ad hoc SQL on demand and the nightly
  CSV export both derive figures (e.g. order counts or revenue) from the same
  tables, but independently and at different times. Each handles duplicate
  orders in its own way, so the same figure can disagree depending on which
  path produced it.
