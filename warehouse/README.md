# Warehouse

SQL and the measuring script for the BigQuery warehouse. The numbers, the
reasoning and the cap are in [`docs/warehouse-tuning.md`](../docs/warehouse-tuning.md).

| File | What |
|---|---|
| `01_native_tables.sql` | Bronze copied into native tables in `warehouse_julius` |
| `02_tuned_tables.sql` | The partitioned and clustered variants, kept to measure them |
| `03_daily_demand_view.sql` | The materialised view the ML team reads |
| `04_monthly_demand_view.sql` | A coarser view, to show the collapse ratio moving |
| `measure.py` | Dry-runs and runs each query with the cache off; prints bytes processed |
| `bigqueryrc` | Default `maximum_bytes_billed` for the `bq` CLI |

The external tables the SQL reads (`bronze_julius.*_external`) are created with
`CREATE EXTERNAL TABLE ... format = 'PARQUET'` over `bronze/<table>/*` in the
bucket, with hive partitioning on `orders` and `order_items`.
