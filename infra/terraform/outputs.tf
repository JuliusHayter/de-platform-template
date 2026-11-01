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
