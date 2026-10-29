"""Write the legacy CSV export as bronze Parquet (ADR-0002).

usage: bronze_export.py <csv_dir> <out_dir>

Every source column is kept as arrived. orders, order_items and payment gain a
partition column dt=YYYY-MM; the other tables are one file each.
"""
import sys
from pathlib import Path

import pandas as pd

csv_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
month = lambda s: pd.to_datetime(s).dt.strftime("%Y-%m")
orders = pd.read_csv(csv_dir / "orders.csv")
partition_by = {"orders": "order_date", "payment": "created_at"}

for f in sorted(csv_dir.glob("*.csv")):
    t = f.stem
    df = pd.read_csv(f)
    if t == "order_items":
        dates = orders.drop_duplicates("order_id").set_index("order_id").order_date
        df["dt"] = month(df.order_id.map(dates))
    elif t in partition_by:
        df["dt"] = month(df[partition_by[t]])
    if "dt" in df:
        df.to_parquet(out_dir / t, partition_cols=["dt"], compression="zstd",
                      basename_template="part-{i}.parquet")
    else:
        (out_dir / t).mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_dir / t / "part-0.parquet", compression="zstd")
    print(t, len(df))
