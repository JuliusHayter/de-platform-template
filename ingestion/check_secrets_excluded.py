"""Prove the secret columns never reach bronze: run the extractor on the two
tables that hold them, then read the Parquet back and fail if any is present.

usage: PGPASSWORD=... python check_secrets_excluded.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

SECRET = {"customer": ["pwd"], "payment_details": ["card_no", "cvv", "expiry_date"]}
here = Path(__file__).parent
with tempfile.TemporaryDirectory() as out:
    subprocess.run([sys.executable, here / "extract_tables.py", *SECRET],
                   env={**os.environ, "BRONZE_URI": out}, check=True)
    for table, secrets in SECRET.items():
        columns = pq.read_schema(f"{out}/bronze/{table}_pg/part-0.parquet").names
        leaked = [c for c in secrets if c in columns]
        print(f"{table}: columns {columns}" + (f"  LEAKED {leaked}" if leaked else "  ok"))
        if leaked:
            sys.exit(1)
print("no secret column reached the output")
