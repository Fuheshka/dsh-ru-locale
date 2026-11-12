#!/usr/bin/env python3
"""Report Russian coverage for every plugin installed in the DSH profile.

The language pack is a moving target: plugins get installed, DSH updates, new
strings appear. This script answers one question — "what do I still see in
English or Chinese?" — by scanning the installed client bundles for locale
registrations and comparing them with the namespaces the pack ships.

Usage:
    python3 tools/coverage.py              # profile desktop, the installed pack
    python3 tools/coverage.py --profile desktop --pkg ../pkg
    python3 tools/coverage.py --json       # machine-readable

Exit code is 0 always: this is a report, not a gate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PKG = HERE.parent / "pkg"

CANDIDATES = ("client/client.js", "lib/client.js", "client.js", "lib/client-host.js")
REGISTER = re.compile(
    r"""locale\.register\(\s*(?:"([^"]+)"|'([^']+)'|([A-Za-z_$][\w$]*))""",
)
CONST_NS = re.compile(r"""const\s+{name}\s*=\s*(?:"([^"]+)"|'([^']+)')""")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
HAN = re.compile(r"[\u4e00-\u9fff]")


def pack_namespaces(pkg: Path) -> dict[str, int]:
    """Namespace → key count, read straight out of the built client bundle."""
    client = pkg / "client.js"
    if not client.exists():
        return {}
    text = client.read_text(encoding="utf-8")
    start = text.find("const DICT = ")
    if start < 0:
        return {}
    start = text.index("{", start)
    depth = 0
    in_string: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char == '"':
            in_string = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : index + 1]
                try:
                    payload = json.loads(blob)
                except json.JSONDecodeError:
                    return {}
                return {ns: len(keys) for ns, keys in payload.items() if isinstance(keys, dict)}
    return {}


def bundle_of(package: Path) -> Path | None:
    for relative in CANDIDATES:
        candidate = package / relative
        if candidate.is_file():
            return candidate
    return None


def namespaces_of(bundle: Path) -> list[str]:
    text = bundle.read_text(encoding="utf-8", errors="replace")
    found: list[str] = []
    for match in REGISTER.finditer(text):
        literal, single, identifier = match.groups()
        namespace = literal or single
        if namespace is None and identifier is not None:
            declaration = CONST_NS.search(text, 0, match.start())
            if declaration is None:
                declaration = re.search(
                    r"""const\s+"""
                    + re.escape(identifier)
                    + r"""\s*=\s*(?:"([^"]+)"|'([^']+)')""",
                    text,
                )
            if declaration is not None:
                namespace = declaration.group(1) or declaration.group(2)
        if namespace and namespace not in found:
            found.append(namespace)
    return found


def installed_packages(profile: Path) -> list[Path]:
    modules = profile / "node_modules"
    if not modules.is_dir():
        return []
    packages: list[Path] = []
    for entry in sorted(modules.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name.startswith("@"):
            packages.extend(sorted(p for p in entry.iterdir() if p.is_dir()))
        elif entry.is_dir() and not entry.is_symlink():
            packages.append(entry)
        elif entry.is_symlink() and entry.is_dir():
            packages.append(entry)
    return packages


def _bridged(row: dict) -> bool:
    """The pack cannot carry this namespace, but the bundle ships its own Russian."""
    return bool(row.get("bundle_has_cyrillic")) and row.get("namespace") == "betterSidebar"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="desktop")
    parser.add_argument("--home", default=os.path.expanduser("~/.dsh"))
    parser.add_argument("--pkg", default=str(DEFAULT_PKG))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    profile = Path(args.home) / "profiles" / args.profile
    pkg = Path(args.pkg).resolve()
    covered = pack_namespaces(pkg)

    rows = []
    for package in installed_packages(profile):
        bundle = bundle_of(package)
        if bundle is None:
            continue
        declared = namespaces_of(bundle)
        if not declared:
            continue
        text = bundle.read_text(encoding="utf-8", errors="replace")
        has_cyrillic = bool(CYRILLIC.search(text))
        has_han = bool(HAN.search(text))
        # Plugins may keep extra languages in a lazily loaded chunk next to the
        # bundle (dsh-better-sidebar ships ru in lib/client-locale.js).
        if not has_cyrillic:
            for chunk in sorted(package.glob("lib/client-*.js")) + sorted(package.glob("client/*.js")):
                if chunk == bundle:
                    continue
                if CYRILLIC.search(chunk.read_text(encoding="utf-8", errors="replace")):
                    has_cyrillic = True
                    break
        for namespace in declared:
            rows.append(
                {
                    "plugin": package.name,
                    "namespace": namespace,
                    "keys": covered.get(namespace, 0),
                    "state": "covered" if namespace in covered else "missing",
                    "bundle_has_cyrillic": has_cyrillic,
                    "bundle_has_han": has_han,
                }
            )

    if args.json:
        print(json.dumps({"pack": {"namespaces": len(covered), "strings": sum(covered.values())}, "rows": rows}, ensure_ascii=False, indent=1))
        return 0

    print(f"Пакет: {pkg}")
    print(f"Словарей в пакете: {len(covered)}, строк: {sum(covered.values())}\n")
    print(f"{'плагин':<34} {'namespace':<26} {'ключей':>7}  статус")
    print("-" * 84)
    missing = 0
    for row in sorted(rows, key=lambda r: (r["state"] != "missing", r["plugin"])):
        if row["state"] == "covered":
            status = "русский есть"
        elif _bridged(row):
            status = "через шим (словарь плагина)"
        else:
            status = "НЕТ ПЕРЕВОДА"
            missing += 1
        print(f"{row['plugin']:<34} {row['namespace']:<26} {row['keys']:>7}  {status}")
    if missing:
        print(f"\nБез перевода: {missing} namespace — добавить в tools/vendor/vendor-corpus.jsonl и пересобрать.")
    else:
        print("\nВсе плагины с реестром локали покрыты пакетом.")
    print(
        "\nПлагины без locale.register сюда не попадают: у них собственный переключатель\n"
        "языка или английские подписи, и пакет до них не достаёт.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
