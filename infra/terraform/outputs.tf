output "bronze_bucket" {
  description = "The bronze bucket URL."
  value       = google_storage_bucket.bronze.url
}

output "datasets" {
  description = "The BigQuery datasets Terraform manages."
  value = [
    google_bigquery_dataset.bronze.dataset_id,
    google_bigquery_dataset.dbt.dataset_id,
    google_bigquery_dataset.warehouse.dataset_id,
  ]
}

output "policy_tags" {
  description = "Policy tag ids, the strings a column's schema must carry to be classified."
  value = {
    pii_contact    = google_data_catalog_policy_tag.pii_contact.name
    pii_identifier = google_data_catalog_policy_tag.pii_identifier.name
    secret         = google_data_catalog_policy_tag.secret.name
  }
}
