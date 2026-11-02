# These resources were created by hand in L02-L05. An import block tells
# Terraform "this address IS that existing thing": only the state changes.
# Kept after the apply as a record of how the adoption happened.

import {
  to = google_storage_bucket.bronze
  id = "data-engineering-a-groupe-julius-bronze"
}

import {
  to = google_bigquery_dataset.bronze
  id = "projects/data-engineering-a/datasets/bronze_julius"
}

import {
  to = google_bigquery_dataset.dbt
  id = "projects/data-engineering-a/datasets/l05_julius"
}

# Added in L09: the L04 dataset that L08 did not declare.
import {
  to = google_bigquery_dataset.warehouse
  id = "projects/data-engineering-a/datasets/warehouse_julius"
}
