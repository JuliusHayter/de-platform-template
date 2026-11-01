# --- Cost attribution labels (L09) --------------------------------------------
# Four keys on every resource, applied through Terraform and never in the
# console. Labels apply from the moment they are set and never backwards: spend
# before 2026-11-02 stays unattributable. Reasons for each key: docs/costs.md.
locals {
  base_labels = {
    team        = var.group # who to ask about the cost
    environment = "prod"    # so a dev spike is not read as production
  }
}

# --- Bronze: the landing zone from L02 ---------------------------------------
resource "google_storage_bucket" "bronze" {
  name                        = "${var.project_id}-groupe-${var.group}-bronze"
  location                    = upper(var.region)
  uniform_bucket_level_access = true

  # Bronze holds the raw history ("nothing that arrived is lost"): Terraform
  # must refuse to delete it while it has objects.
  force_destroy = false

  labels = merge(local.base_labels, {
    pipeline = "marketplace-daily"
    lesson   = "l02"
  })

  # Same three rules as infra/lifecycle.json. There is no Delete action.
  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
    condition {
      age            = 30
      matches_prefix = ["bronze/"]
    }
  }

  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
    condition {
      age            = 90
      matches_prefix = ["bronze/"]
    }
  }

  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
    condition {
      age            = 365
      matches_prefix = ["bronze/"]
    }
  }
}

# --- BigQuery datasets --------------------------------------------------------
# Only the datasets, not the tables inside: the external tables are created by
# the SQL in warehouse/ and the dbt tables by dbt. Dataset ACLs are left
# unmanaged on purpose (see docs/infra.md).

# Holds the external tables over the bronze Parquet files (L04).
resource "google_bigquery_dataset" "bronze" {
  dataset_id                 = "bronze_${var.group}"
  location                   = var.region
  delete_contents_on_destroy = false

  labels = merge(local.base_labels, {
    pipeline = "marketplace-daily"
    lesson   = "l04"
  })
}

# Where dbt builds silver and gold (L05, and the default of the L07 DAG).
resource "google_bigquery_dataset" "dbt" {
  dataset_id                 = "l05_${var.group}"
  location                   = var.region
  delete_contents_on_destroy = false

  labels = merge(local.base_labels, {
    pipeline = "marketplace-daily"
    lesson   = "l05"
  })
}

# The L04 measurement copies (native, partitioned and clustered tables of the
# same data). Missed by L08, which only declared what the pipeline reads: found
# while listing the project's datasets for the L09 ledger.
resource "google_bigquery_dataset" "warehouse" {
  dataset_id                 = "warehouse_${var.group}"
  location                   = var.region
  delete_contents_on_destroy = false

  labels = merge(local.base_labels, {
    pipeline = "warehouse-tuning"
    lesson   = "l04"
  })
}

# --- Identity for the pipeline: NOT declared ----------------------------------
# A google_service_account for the scheduled jobs was tried (account_id
# "pipeline-julius") and refused: 403 iam.serviceAccounts.create on the project.
# Our project does not grant that role on purpose (L10 audits IAM). The jobs
# still run as a person. See docs/infra.md. Resource-level IAM bindings are not
# declared either: no service account exists to bind, and the existing legacy
# bindings are project defaults that Terraform cannot remove from here.

# --- Data classification (L10) ------------------------------------------------
# A taxonomy and its policy tags: the filing scheme for ADR-0010. Tags are named
# for what the data IS, never for who may see it. A tag protects nothing until a
# column carries it (the column's schema names the tag), and a table the
# pipeline rebuilds loses it unless the build re-applies it: see
# docs/governance.md for what is and is not tagged, and why.
#
# The taxonomy must be in the datasets' location (europe-west1). The display name
# is unique per project and location, and the project is shared, hence the group.
resource "google_data_catalog_taxonomy" "classification" {
  region       = var.region
  display_name = "${var.group}-marketplace-classification"
  description  = "Column classes for the ${var.group} marketplace platform (ADR-0010)."

  # Without FINE_GRAINED_ACCESS_CONTROL the taxonomy is created and enforces nothing.
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]
}

resource "google_data_catalog_policy_tag" "pii_contact" {
  taxonomy     = google_data_catalog_taxonomy.classification.id
  display_name = "pii-contact"
  description  = "Directly identifies or contacts a person: name, email, phone, street, zip, billing address."
}

resource "google_data_catalog_policy_tag" "pii_identifier" {
  taxonomy     = google_data_catalog_taxonomy.classification.id
  display_name = "pii-identifier"
  description  = "A pseudonymous id that points to a person in another table: buyer_id, c_id, session_id. Joining it re-identifies."
}

resource "google_data_catalog_policy_tag" "secret" {
  taxonomy     = google_data_catalog_taxonomy.classification.id
  display_name = "secret"
  description  = "Credentials and payment data: pwd, card_no, cvv, expiry_date. Must never leave bronze."
}
