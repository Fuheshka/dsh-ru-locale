#!/usr/bin/env python3
"""Extract DSH client UI locale dictionaries into a JSONL corpus.

Handles the shapes that actually occur in packages/*/*/src/client/**/locales.ts:
  * `export const NS = '<ns>'` plus `export const <locale> = {...}`
  * `export const dictionaries = { zh: {...}, en: {...}, ... }`   (contextMenu)
  * `...zoom<Locale>` spreads pulled from zoom/locales.ts           (pdf, image)
Non-literal values (shared constants, functions) are recorded without text.
"""
import json
import os
import re
import sys

ROOT = "/Users/fuheshka/Documents/GitHub/deepseek-harness"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "corpus.jsonl")
LOCALES = ("zh", "en", "ja", "es", "fr", "de", "ru", "pt")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def skip_string(src, i):
    quote = src[i]
    i += 1
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        i += 1
    raise ValueError("unterminated string")


def unquote(raw):
    body = raw[1:-1]
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            out.append({"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\", "`": "`"}.get(body[i + 1], body[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def block_bounds(src, start):
    depth = 0
    i = start
    while i < len(src):
        ch = src[i]
        if ch in "'\"`":
            i = skip_string(src, i)
            continue
        if src.startswith("//", i):
            i = src.find("\n", i)
            if i == -1:
                return len(src)
            continue
        if src.startswith("/*", i):
            i = src.find("*/", i) + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced block")


def parse_dict(src, start, end):
    """Parse a flat object literal into [(key, value|None, raw, spread)]."""
    entries = []
    i = start + 1
    while i < end - 1:
        ch = src[i]
        if ch in " \t\r\n,":
            i += 1
            continue
        if src.startswith("//", i):
            i = src.find("\n", i)
            if i == -1:
                break
            continue
        if src.startswith("/*", i):
            i = src.find("*/", i) + 2
            continue
        if src.startswith("...", i):
            j = i + 3
            while j < end and src[j] not in ",\n}":
                j += 1
            entries.append((None, None, src[i:j].strip(), True))
            i = j
            continue
        if ch in "'\"":
            key_end = skip_string(src, i)
            key = unquote(src[i:key_end])
            i = key_end
        else:
            m = re.match(r"[A-Za-z_$][\w$]*", src[i:])
            if not m:
                raise ValueError(f"bad key at {i}: {src[i:i+30]!r}")
            key = m.group(0)
            i += m.end()
        while i < end and src[i] in " \t\r\n":
            i += 1
        if i >= end or src[i] != ":":
            raise ValueError(f"missing colon after {key!r}")
        i += 1
        while i < end and src[i] in " \t\r\n":
            i += 1
        if i < end and src[i] in "'\"":
            val_end = skip_string(src, i)
            entries.append((key, unquote(src[i:val_end]), src[i:val_end], False))
            i = val_end
        else:
            j = i
            depth = 0
            while j < end:
                c = src[j]
                if c in "'\"`":
                    j = skip_string(src, j)
                    continue
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif c == "," and depth == 0:
                    break
                j += 1
            entries.append((key, None, src[i:j].strip(), False))
            i = j
    return entries


def find_dict(src, name):
    m = re.search(r"^export const %s\b\s*(?::[^=]+)?=\s*\{" % re.escape(name), src, re.M)
    if not m:
        return None
    start = src.index("{", m.end() - 1)
    return parse_dict(src, start, block_bounds(src, start))


def to_map(entries, spread_maps):
    out = {}
    literals = {}
    for key, value, raw, spread in entries:
        if spread:
            ref = raw[3:].strip()
            if ref in spread_maps:
                out.update(spread_maps[ref])
            continue
        out[key] = value
        literals[key] = value is not None
    return out, literals


def resolve_ns(locales_path, src):
    m = re.search(r"^export const NS\s*=\s*'([^']+)'", src, re.M)
    if m:
        return m.group(1)
    if "export const dictionaries = {" in src:
        literals = re.findall(r"locale\.register\(\s*'([^']+)'", src)
        if len(literals) == 1:
            return literals[0]
    d = os.path.dirname(locales_path)
    pkg = d
    while pkg != ROOT and not os.path.exists(os.path.join(pkg, "package.json")):
        pkg = os.path.dirname(pkg)
    for dp, _dn, fn in os.walk(os.path.join(pkg, "src")):
        for name in fn:
            if not name.endswith((".ts", ".tsx")):
                continue
            fp = os.path.join(dp, name)
            s = read(fp)
            for im in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*'([^']*locales(?:\.ts)?)'", s):
                target = os.path.normpath(os.path.join(dp, im.group(2)))
                if not target.endswith(".ts"):
                    target += ".ts"
                if target != locales_path:
                    continue
                for rm in re.finditer(r"locale\.register\(\s*([^,]+?)\s*,\s*\{([^}]*)\}", s):
                    if "ru" not in rm.group(2) and "zh" not in rm.group(2):
                        continue
                    expr = rm.group(1).strip()
                    if expr.startswith("'"):
                        return expr.strip("'")
                    dm = re.search(r"(?:export\s+)?const\s+%s\s*(?::[^=]+)?=\s*'([^']+)'" % re.escape(expr), s)
                    if dm:
                        return dm.group(1)
    return None


def emit(rows, ns, dicts, spread_maps=None):
    en = dicts.get("en")
    ru = dicts.get("ru")
    if en is None or ru is None:
        return False
    zh = dicts.get("zh") or {}
    for key, value in en.items():
        rows.append({
            "ns": ns,
            "key": key,
            "en": value,
            "ru": ru.get(key),
            "zh": zh.get(key),
        })
    return True


def main():
    zoom_path = os.path.join(ROOT, "packages/client/ui-sidebar-documentpreview/src/client/zoom/locales.ts")
    zoom_src = read(zoom_path)
    spread_maps = {}
    for locale in LOCALES:
        cap = locale.capitalize()
        entries = find_dict(zoom_src, "zoom" + cap)
        if entries is not None:
            spread_maps["zoom" + cap], _ = to_map(entries, {})

    files = []
    for dp, _dn, fn in os.walk(os.path.join(ROOT, "packages")):
        if "node_modules" in dp.split(os.sep):
            continue
        if "locales.ts" in fn and "/client/" in os.path.join(dp, "locales.ts").replace(os.sep, "/"):
            files.append(os.path.join(dp, "locales.ts"))
    settings = os.path.join(ROOT, "packages/client/locale/src/locales/settings.ts")
    if os.path.exists(settings):
        files.append(settings)
    files.sort()

    rows, problems = [], []

    # `common` namespace: one file per locale under the locale package.
    common_dir = os.path.join(ROOT, "packages/client/locale/src/locales")
    common = {}
    for locale in LOCALES:
        p = os.path.join(common_dir, f"{locale}.ts")
        if not os.path.exists(p):
            continue
        entries = find_dict(read(p), locale)
        common[locale] = None if entries is None else to_map(entries, spread_maps)[0]
    if not emit(rows, "common", common):
        problems.append("common: missing en or ru")

    for path in files:
        rel = os.path.relpath(path, ROOT)
        src = read(path)
        if rel.endswith("inspector/src/client/bridge/locales.ts"):
            continue
        if rel.endswith("client/locale/src/locales/settings.ts"):
            ns = "settings.locale"
        elif rel.endswith("zoom/locales.ts"):
            continue
        else:
            ns = resolve_ns(path, src)
            if ns is None and "export const dictionaries = {" in src:
                sibling = os.path.join(os.path.dirname(path), "index.ts")
                if os.path.exists(sibling):
                    literals = re.findall(r"locale\.register\(\s*'([^']+)'", read(sibling))
                    if len(literals) == 1:
                        ns = literals[0]
            if ns is None:
                problems.append(f"{rel}: no namespace")
                continue
        dicts = {}
        if "export const dictionaries = {" in src:
            root_start = src.index("{", src.index("export const dictionaries"))
            root_end = block_bounds(src, root_start)
            for locale in LOCALES:
                m = re.search(r"(?:^|[\s,])%s\s*:\s*\{" % locale, src[:root_end], re.M)
                if not m:
                    dicts[locale] = {}
                    continue
                start = src.index("{", m.end() - 1)
                dicts[locale], _ = to_map(parse_dict(src, start, block_bounds(src, start)), spread_maps)
        else:
            for locale in LOCALES:
                entries = find_dict(src, locale)
                dicts[locale] = None if entries is None else to_map(entries, spread_maps)[0]
        if not emit(rows, ns, dicts):
            problems.append(f"{rel}: missing en/ru dictionary")
            continue
        for row in rows:
            if "file" not in row and row["ns"] == ns:
                row.setdefault("file", rel)

    with open(OUT, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"rows: {len(rows)}  namespaces: {len({r['ns'] for r in rows})}  files: {len(files)}")
    print(f"no literal ru: {sum(1 for r in rows if r['ru'] is None)}")
    for p in problems:
        print("PROBLEM", p)


if __name__ == "__main__":
    sys.exit(main())
