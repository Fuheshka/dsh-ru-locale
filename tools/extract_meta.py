#!/usr/bin/env python3
"""Extract plugin metadata locales (`locale/<lang>.json`) into a corpus."""
import json
import os
import sys

ROOT = "/Users/fuheshka/Documents/GitHub/deepseek-harness"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "meta-corpus.jsonl")


def flatten(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from flatten(value, path)
        elif isinstance(value, str):
            yield path, value


def main():
    rows = []
    for dp, dn, fn in os.walk(os.path.join(ROOT, "packages")):
        if "node_modules" in dp.split(os.sep):
            continue
        if "en.json" not in fn or "ru.json" not in fn:
            continue
        en_path = os.path.join(dp, "en.json")
        ru_path = os.path.join(dp, "ru.json")
        try:
            en = json.load(open(en_path, encoding="utf-8"))
            ru = json.load(open(ru_path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print("PROBLEM", en_path, exc)
            continue
        ru_flat = dict(flatten(ru))
        package = os.path.relpath(os.path.dirname(dp), ROOT)
        for key, value in flatten(en):
            rows.append({
                "ns": package,
                "key": key,
                "en": value,
                "ru": ru_flat.get(key),
                "file": os.path.relpath(en_path, ROOT),
            })
    with open(OUT, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} meta strings from {len({r['file'] for r in rows})} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
