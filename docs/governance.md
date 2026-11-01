# Data classification and access

How every column in the platform is classified, who may read each class, and how
much of that is actually enforced. Written 2026-11-01. The honest part is the
last section: a classification that is on paper and not in the platform is a
wish, and this document says which is which.

Related: [ADR-0010](adr/0010-data-classification.md), [erasure runbook](runbooks/erasure.md),
[`infra/iam.md`](../infra/iam.md), [data dictionary](data-dictionary.md).

## 1. The classes

Six classes. Each is named for what the data **is**, never for who may see it:
the audience changes with a reorganisation, the data does not.

| Class | Policy tag | What belongs in it | Count |
|---|---|---|---|
| `public` | none | Product catalogue: what any visitor sees | 11 |
| `internal` | none | No personal content: amounts, dates, quantities, status codes | 68 |
| `pii.identifier` | `pii-identifier` | A pseudonymous id that points to a person in another table (`buyer_id`, `c_id`, `session_id`, `seller_id`). Alone it names nobody; joined, it re-identifies | 25 |
| `pii.contact` | `pii-contact` | Directly identifies or contacts a person: name, email, phone, street, city, zip, billing address | 10 |
| `secret` | `secret` | Credentials and payment data: `pwd`, `card_no`, `cvv`, `expiry_date`. Must never leave bronze | 4 |
| `unclassified` | none, on purpose | Free text and anything we cannot vouch for. Treated as if it were `pii.contact` until read | 6 |

The three policy tags exist in the taxonomy `julius-marketplace-classification`
(europe-west1, `FINE_GRAINED_ACCESS_CONTROL` activated), declared in
[`infra/terraform/main.tf`](../infra/terraform/main.tf).

**Who decides.** The group owns every column today ("nobody" is what we had before
this step). Adding a class, moving a column between classes or granting a tag to a
role is decided by the group in a reviewed pull request, and the reason goes in the
commit message. A grant for one person is a request (section 3), not a decision made
in a console.

## 2. Every column

124 columns in 29 bronze tables, from the [data dictionary](data-dictionary.md)
(the bronze `*_pg` copies carry the same columns and the same classes as the table
they copy; the exporter's `Unnamed: 0` index and the partition column `dt` are
`internal` and not repeated). Owner is "the group" for all of them: it is a role that can
answer questions about the column, which is the point, and it should become a named
person per domain when there is more than one team.

| Column | Class | Owner | Why |
|---|---|---|---|
| `_dlq/clickstream.raw` | unclassified | the group | Free text or uncertain: may contain anything (The message as received; a client may have sent anything) |
| `_dlq/clickstream.reason` | internal | the group | No personal content |
| `_dlq/clickstream.received_at` | internal | the group | No personal content |
| `_dlq/clickstream.topic` | internal | the group | No personal content |
| `_dlq/clickstream.partition` | internal | the group | No personal content |
| `_dlq/clickstream.offset` | internal | the group | No personal content |
| `buyer.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `carrier.carrier_id` | internal | the group | No personal content |
| `carrier.carrier_name` | internal | the group | No personal content |
| `cart.cart_id` | internal | the group | No personal content |
| `cart.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `cart.total_qty` | internal | the group | No personal content |
| `cart.total_price` | internal | the group | No personal content |
| `cart_items.cart_id` | internal | the group | No personal content |
| `cart_items.p_id` | internal | the group | No personal content |
| `cart_items.qty` | internal | the group | No personal content |
| `category.category_id` | public | the group | Product catalogue, shown to any visitor |
| `category.name` | public | the group | Product catalogue, shown to any visitor |
| `category.c_desc` | public | the group | Product catalogue, shown to any visitor |
| `clickstream.schema_version` | internal | the group | No personal content |
| `clickstream.event_id` | internal | the group | No personal content |
| `clickstream.event_type` | internal | the group | No personal content |
| `clickstream.event_time` | internal | the group | No personal content |
| `clickstream.emitted_at` | internal | the group | No personal content |
| `clickstream.session_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `clickstream.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `clickstream.p_id` | internal | the group | No personal content |
| `clickstream.price` | internal | the group | No personal content |
| `clickstream.qty` | internal | the group | No personal content |
| `clickstream.order_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `clickstream.payment_method` | internal | the group | No personal content |
| `clickstream.amount` | internal | the group | No personal content |
| `clickstream.currency` | internal | the group | No personal content |
| `clickstream.items` | internal | the group | No personal content |
| `customer.c_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `customer.fname` | pii.contact | the group | Directly identifies or contacts a person (First name) |
| `customer.lname` | pii.contact | the group | Directly identifies or contacts a person (Last name) |
| `customer.phone` | pii.contact | the group | Directly identifies or contacts a person (Phone number (leading zeros lost in export)) |
| `customer.email` | pii.contact | the group | Directly identifies or contacts a person (Email address) |
| `customer.pwd` | secret | the group | Credential or payment data; never leaves bronze (Stored password) |
| `customer_payment.payment_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `customer_payment.c_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `customer_payment.is_default` | internal | the group | No personal content |
| `customer_shipping.address_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `customer_shipping.c_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `customer_shipping.is_default` | internal | the group | No personal content |
| `daily_deals.p_id` | internal | the group | No personal content |
| `daily_deals.deal_date` | internal | the group | No personal content |
| `daily_deals.discount` | internal | the group | No personal content |
| `discount.discount_id` | internal | the group | No personal content |
| `discount.discount_name` | internal | the group | No personal content |
| `discount.d_desc` | unclassified | the group | Free text or uncertain: may contain anything |
| `discount.discount_amt` | internal | the group | No personal content |
| `order_items.order_id` | internal | the group | No personal content |
| `order_items.p_id` | internal | the group | No personal content |
| `order_items.qty` | internal | the group | No personal content |
| `order_items.price_at_purchase` | internal | the group | No personal content |
| `orders.order_id` | internal | the group | No personal content |
| `orders.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `orders.discount_id` | internal | the group | No personal content |
| `orders.payment_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `orders.order_date` | internal | the group | No personal content |
| `payment.transaction_id` | internal | the group | No personal content |
| `payment.order_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `payment.payment_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `payment.amount` | internal | the group | No personal content |
| `payment.method` | internal | the group | No personal content |
| `payment.status` | internal | the group | No personal content |
| `payment.created_at` | internal | the group | No personal content |
| `payment_details.payment_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `payment_details.card_no` | secret | the group | Credential or payment data; never leaves bronze (Full card number) |
| `payment_details.cvv` | secret | the group | Credential or payment data; never leaves bronze (Card security code) |
| `payment_details.expiry_date` | secret | the group | Credential or payment data; never leaves bronze (Card expiry) |
| `payment_details.billing_address` | pii.contact | the group | Directly identifies or contacts a person (Billing address) |
| `product.p_id` | public | the group | Product catalogue, shown to any visitor |
| `product.p_name` | public | the group | Product catalogue, shown to any visitor |
| `product.p_desc` | public | the group | Product catalogue, shown to any visitor |
| `product.price` | public | the group | Product catalogue, shown to any visitor |
| `product.qty` | public | the group | Product catalogue, shown to any visitor |
| `product.category_id` | public | the group | Product catalogue, shown to any visitor |
| `product_images.p_id` | public | the group | Product catalogue, shown to any visitor |
| `product_images.p_image` | public | the group | Product catalogue, shown to any visitor |
| `product_reviews.review_id` | internal | the group | No personal content |
| `product_reviews.p_id` | internal | the group | No personal content |
| `returns.return_id` | internal | the group | No personal content |
| `returns.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `returns.p_id` | internal | the group | No personal content |
| `returns.order_id` | internal | the group | No personal content |
| `review.review_id` | internal | the group | No personal content |
| `review.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `review.r_desc` | unclassified | the group | Free text or uncertain: may contain anything (Free text) |
| `review.title` | unclassified | the group | Free text or uncertain: may contain anything (Free text) |
| `review.rating` | internal | the group | No personal content |
| `review.seller_product_flag` | internal | the group | No personal content |
| `review_images.review_id` | internal | the group | No personal content |
| `review_images.review_img` | unclassified | the group | Free text or uncertain: may contain anything (Photo link) |
| `seller.seller_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `seller.seller_type` | internal | the group | No personal content |
| `seller.seller_name` | unclassified | the group | Free text or uncertain: may contain anything (Seller name; empty in the export, so typed as a float) |
| `seller_products.seller_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `seller_products.p_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `seller_reviews.review_id` | internal | the group | No personal content |
| `seller_reviews.seller_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `shipment.shipping_id` | internal | the group | No personal content |
| `shipment.order_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `shipment.p_id` | internal | the group | No personal content |
| `shipment.carrier_id` | internal | the group | No personal content |
| `shipment.shipment_type` | internal | the group | No personal content |
| `shipment.status` | internal | the group | No personal content |
| `shipment.est_delivery_date` | internal | the group | No personal content |
| `shipment.actual_delivery_date` | internal | the group | No personal content |
| `shipping_details.address_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `shipping_details.street_address` | pii.contact | the group | Directly identifies or contacts a person (Street) |
| `shipping_details.city` | pii.contact | the group | Directly identifies or contacts a person (Locality) |
| `shipping_details.state` | pii.contact | the group | Directly identifies or contacts a person (Locality) |
| `shipping_details.zip` | pii.contact | the group | Directly identifies or contacts a person (Locality) |
| `shipping_details.country` | internal | the group | No personal content |
| `shipping_details.phone` | pii.contact | the group | Directly identifies or contacts a person (Contact phone) |
| `subscription.subscription_id` | internal | the group | No personal content |
| `subscription.c_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |
| `subscription.start_date` | internal | the group | No personal content |
| `subscription.end_date` | internal | the group | No personal content |
| `wishlist_item.product_id` | internal | the group | No personal content |
| `wishlist_item.buyer_id` | pii.identifier | the group | Pseudonymous id; joins to a person elsewhere |

### Free-text columns, marked honestly

Never assumed clean. These are `unclassified`, and anything that reads them should treat
them as `pii.contact`:

- `review.r_desc`, `review.title`: customers type whatever they like (names, phone numbers, addresses).
- `review_images.review_img`: a photo link; a photo may show a person or an address.
- `seller.seller_name`: empty in the export, but sellers may be individuals.
- `discount.d_desc`: a description column that landed empty and cannot be vouched for.
- `_dlq/clickstream.raw`: the message as received; whatever a client sent is in there.

### Silver and gold

Silver (staging and intermediate) is **views** over the bronze external tables and holds
no data of its own. `stg_shipping_details` drops `street_address`, `zip` and `phone`
before anything is built on it, so the `pii.contact` columns of shipping do not reach silver.
`buyer_id` does (`stg_orders`, `stg_review`, `int_orders`, `int_order_items`) as `pii.identifier`.
Gold (`fct_order_items`, `fct_daily_demand`, `dim_product`, `dim_date`, `dim_country`) is
tables and holds **no identifier of a person**: `fct_order_items` keeps `order_id`, `p_id`,
`qty`, price, date and the buyer's country, and `fct_daily_demand` aggregates it. Every gold column
is `internal` or `public`. This is the most useful property of the platform for access:
the people who need numbers can be given gold and never touch bronze.

## 3. The access matrix

Read = may select the class. Roles are job functions, not people.

| Role | public | internal | pii.identifier | pii.contact | secret | unclassified |
|---|---|---|---|---|---|---|
| Analyst | read | read | no | no | no | no |
| Engineer (pipeline) | read | read | read | read, logged | no | read |
| ML service account | read | read | no | no | no | no |
| Auditor | metadata and logs only | metadata and logs only | metadata only | metadata only | metadata only | metadata only |

What to do instead of a "no" (a rule with no exception path gets routed around):

| Role | The "no" | What they do when they genuinely need it |
|---|---|---|
| Analyst | `pii.identifier`, `pii.contact`, `secret`, `unclassified` | Ask for a gold model that answers the question. Gold has no person in it. If it does not, open an issue from the task template saying which question and which column; the group decides in a pull request |
| ML service account | the same | Features come from gold. A feature that needs a person-level id is a design review, not a grant |
| Engineer | `secret` | Nobody reads `secret`. It is not ingested into silver at all ([data dictionary](data-dictionary.md)); a fix to a payment problem is done on the payment provider's side |
| Anyone | any class | A time-limited grant on the tag, requested in an issue, approved by the group, removed after |

## 4. What is enforced, and what is not

This section is the deliverable. Everything above is the intent; this is the platform.

| Intent | In the platform today | Verdict |
|---|---|---|
| Three classes of PII exist as policy tags | Taxonomy and 3 tags created and applied with Terraform; `FINE_GRAINED_ACCESS_CONTROL` is on | **Done** |
| Tagged columns refuse readers without the tag role | Tags were applied to the columns of a synthetic test table (the schema returns them). **Reads were still allowed**: the author's account holds `datacatalog.categories.fineGrainedGet` on the tag without any binding on the tag itself, so the permission comes from a level above it. The source could not be identified: the project policy cannot be read and the Resource Manager API is not enabled | **Not verified by being refused.** Open |
| The PII of the platform is tagged | **No column of the group's datasets carries a tag.** The columns that matter are in `bronze_julius`, which are plain external tables over Cloud Storage, and BigQuery refuses a tag on them: *"Policy tags are not supported on plain external tables. Use a BigLake table instead."* (tested). Silver is views, gold has no PII | **Gap.** Needs BigLake tables (a BigQuery connection and a role on the bucket for its service account, which our permissions do not allow) |
| Bronze readable only by the silver job | The bucket still grants read to every `projectViewer` of the project, the whole class, with `pwd` and card data inside ([`infra/iam.md`](../infra/iam.md)). We decided not to remove that grant now: removing it would block any teammate who is only a viewer, and the project step's "narrowed grant" is therefore **not met** | **Gap, decided.** See below |
| The ML service account cannot read `pii.contact` | No service account exists: creating one is refused (`403 iam.serviceAccounts.create`, see [`infra.md`](infra.md)) | **Gap** |
| Who read it is answerable | The Admin Activity log is readable. The BigQuery **Data Access** log returned nothing for the author's account, which points to a missing private-logs role, not to an empty log | **Gap** |
| Labels from L09 are kept | Untouched; `terraform plan` shows `No changes` on them | **Done** |

**The grant that should be narrowed, and why it is not.** The bronze bucket grants
`legacyBucketReader` and `legacyObjectReader` to `projectViewer:data-engineering-a`.
It exists because Cloud Storage adds it to every new bucket. It is broader than its reason:
the only reader bronze needs is the silver job, and the extractors that write it. We would
narrow it to the group's members on `roles/storage.objectViewer` and remove the viewer
default. We did not, because the project cannot be read to see who is only a viewer, and an
unexpected block on a Monday morning is a worse outcome than a documented gap. To do it:
`gcloud storage buckets remove-iam-policy-binding gs://data-engineering-a-groupe-julius-bronze --member=projectViewer:data-engineering-a --role=roles/storage.legacyObjectReader`
and the same for `roles/storage.legacyBucketReader`; to undo, `add-iam-policy-binding`.

**What would break if a column of ours were tagged on a Monday morning.** The dbt build
reads `bronze_julius` through the person who runs it. If a column read by a model carried
a tag and the running account lacked the reader role on it, `dbt build` would fail at that
model. Today the models that read the tagged-class columns are `stg_orders`, `stg_review`
and `stg_customer_shipping` (all `buyer_id` or `c_id`, `pii.identifier`), so tagging
`pii-identifier` on bronze would stop the DAG's `dbt_build` task. That is the audit to run
before tagging, with the Data Access log: it lists what reads the dataset.

### How to verify the refusal (needs a second account)

Reading a schema proves intent, not protection. The author's account cannot be refused (see the table above), so
the check has to be run by **a teammate who does not hold the tag role**. A synthetic two-row table with three
tagged columns was left for this in `l10_leonard.shipping_test` (fake data only, no real person):

```
bq query --use_legacy_sql=false --nouse_cache 'SELECT street_address, phone FROM `data-engineering-a.l10_leonard.shipping_test`'
```

- **Refused** (`Access Denied: ... neither fine-grained reader nor masked get permission ... policy tag "julius-marketplace-classification : pii-contact"`):
  enforcement works for that account. Record the exact error here and in the pull request.
- **Rows returned:** that account also holds the permission from above the tag. Count how many accounts do. If it
  is everyone in the class, the tags protect nothing from the people we worry about, and ADR-0010's
  "what would change my mind" applies.

Then delete the test dataset: `bq rm -r -f -d data-engineering-a:l10_leonard`.

## 5. Not classified yet

- **Query job text and results** in BigQuery's job history: a query can carry an identifier in its text. Not inventoried.
- **Local state of the pipeline** (`.state/` cursors, Airflow logs and volumes on a laptop): outside the cloud, outside this document.
- **The Docker Hub images**: they hold code, not data, and are not classified.
- **Data created by other groups in the shared project** that happens to share a name with ours (e.g. `julius_goat`): not ours to classify until we know whether it is.
