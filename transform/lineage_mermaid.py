"""Print the dbt lineage graph as Mermaid, from target/manifest.json.

usage: python lineage_mermaid.py > graph.mmd   (run `dbt docs generate` or `dbt build` first)
"""
import json
from pathlib import Path

m = json.loads((Path(__file__).parent / "target" / "manifest.json").read_text())
nodes = {**m["nodes"], **m["sources"]}
layer = lambda uid, n: "src" if uid.startswith("source.") else n["name"].split("_")[0]
keep = {u: n for u, n in nodes.items() if u.startswith("source.") or (u.startswith("model.") and n["resource_type"] == "model")}

print("flowchart LR")
for kind, title in [("src", "Bronze (sources)"), ("stg", "Staging (views)"), ("int", "Intermediate (views)")]:
    print(f"  subgraph {kind}[{title}]")
    for u, n in keep.items():
        if layer(u, n) == kind:
            print(f"    {n['name']}[{n['name']}]")
    print("  end")
print("  subgraph marts[Marts (tables)]")
for u, n in keep.items():
    if layer(u, n) in ("fct", "dim"):
        print(f"    {n['name']}[{n['name']}]")
print("  end")
for u, n in keep.items():
    if u.startswith("source."):
        continue
    for parent in n["depends_on"]["nodes"]:
        if parent in keep:
            print(f"  {keep[parent]['name']} --> {n['name']}")
