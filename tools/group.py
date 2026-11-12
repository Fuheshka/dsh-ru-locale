#!/usr/bin/env python3
"""Split the corpus into balanced per-namespace groups for parallel translation."""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "corpus")
TARGET = 250  # strings per group

rows = [json.loads(line) for line in open(os.path.join(HERE, "corpus.jsonl"), encoding="utf-8")]
by_ns = defaultdict(list)
order = []
for row in rows:
    if row["ns"] not in by_ns:
        order.append(row["ns"])
    by_ns[row["ns"]].append(row)

# Never-visible / trivial namespaces still get translated, they just sort last.
groups, current, size = [], [], 0
buckets = []
for ns in order:
    weight = len(by_ns[ns])
    if weight >= 300:
        buckets.append([ns])
    else:
        buckets.append([ns])
# greedy fill: process namespaces biggest first, open a new group when full
buckets.sort(key=lambda b: -len(by_ns[b[0]]))
groups = []
for ns_list in buckets:
    ns = ns_list[0]
    placed = False
    for group in groups:
        if group["size"] + len(by_ns[ns]) <= TARGET:
            group["ns"].append(ns)
            group["size"] += len(by_ns[ns])
            placed = True
            break
    if not placed:
        groups.append({"ns": [ns], "size": len(by_ns[ns])})

groups.sort(key=lambda g: -g["size"])
os.makedirs(OUT_DIR, exist_ok=True)
manifest = []
for index, group in enumerate(groups, start=1):
    name = f"group-{index:02d}"
    path = os.path.join(OUT_DIR, f"{name}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for ns in group["ns"]:
            for row in by_ns[ns]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest.append({"group": name, "ns": group["ns"], "rows": group["size"]})
    print(f"{name}: {group['size']:4d} rows  {', '.join(group['ns'])}")

with open(os.path.join(HERE, "groups.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=1)
print(f"\n{len(groups)} groups, {len(rows)} rows")
