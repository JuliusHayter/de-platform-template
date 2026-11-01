# --- Bronze: the landing zone from L02 ---------------------------------------
resource "google_storage_bucket" "bronze" {
  name                        = "${var.project_id}-groupe-${var.group}-bronze"
  location                    = upper(var.region)
  uniform_bucket_level_access = true

  # Bronze holds the raw history ("nothing that arrived is lost"): Terraform
  # must refuse to delete it while it has objects.
  force_destroy = false

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
}

# Where dbt builds silver and gold (L05, and the default of the L07 DAG).
resource "google_bigquery_dataset" "dbt" {
  dataset_id                 = "l05_${var.group}"
  location                   = var.region
  delete_contents_on_destroy = false
}

# --- Identity for the pipeline: NOT declared ----------------------------------
# A google_service_account for the scheduled jobs was tried (account_id
# "pipeline-julius") and refused: 403 iam.serviceAccounts.create on the project.
# Our project does not grant that role on purpose (L10 audits IAM). The jobs
# still run as a person. See docs/infra.md. Resource-level IAM bindings are not
# declared either: no service account exists to bind, and the existing legacy
# bindings are project defaults that Terraform cannot remove from here.
