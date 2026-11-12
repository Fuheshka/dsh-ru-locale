#!/usr/bin/env python3
"""Build the upstream patch: replace the shipped Russian text in the DSH checkout.

Stages modified copies of every source file under stage/ and emits a unified diff
that applies from the repository root with `git apply`. Only values of existing
`ru` dictionary entries are rewritten; keys, order, comments, spreads, non-literal
values and every other locale stay byte-identical.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

ROOT = extract.ROOT
STAGE = os.path.join(HERE, "..", "stage")
PATCH = os.path.join(HERE, "..", "dsh-ru-locale.patch")


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def translations():
    out = {}
    for name in sorted(os.listdir(os.path.join(HERE, "out"))):
        if name.endswith(".jsonl"):
            for row in load_jsonl(os.path.join(HERE, "out", name)):
                out[(row["ns"], row["key"])] = row["ru"]
    for row in load_jsonl(os.path.join(HERE, "overrides.jsonl")):
        out[(row["ns"], row["key"])] = row["ru"]
    return out


def meta_translations():
    out = {}
    for name in sorted(os.listdir(os.path.join(HERE, "out-meta"))):
        if name.endswith(".jsonl"):
            for row in load_jsonl(os.path.join(HERE, "out-meta", name)):
                out[(row["ns"], row["key"])] = row["ru"]
    return out


def find_dict_body(src, name):
    """Return (open_brace, close_brace) for `export const <name>[: Type] = {`."""
    import re
    match = re.search(r"^export const %s\b[^=]*=\s*\{" % re.escape(name), src, re.M)
    if not match:
        raise ValueError(f"no dictionary {name}")
    open_brace = src.index("{", match.end() - 1)
    return open_brace, extract.block_bounds(src, open_brace) - 1


def entry_spans(src, open_brace, close_brace):
    """Yield (key, value_start, value_end, is_literal) for one object literal."""
    spans = []
    i = open_brace + 1
    while i < close_brace:
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
            while i < close_brace and src[i] not in ",\n":
                i += 1
            continue
        if ch in "'\"":
            key_end = extract.skip_string(src, i)
            key = extract.unquote(src[i:key_end])
            i = key_end
        else:
            j = i
            while i < close_brace and (src[i].isalnum() or src[i] in "_$"):
                i += 1
            if j == i:
                raise ValueError(f"cannot parse key near {src[i:i+40]!r}")
            key = src[j:i]
        while i < close_brace and src[i] in " \t\r\n":
            i += 1
        if i >= close_brace or src[i] != ":":
            raise ValueError(f"missing colon after {key!r}")
        i += 1
        while i < close_brace and src[i] in " \t\r\n":
            i += 1
        if i < close_brace and src[i] in "'\"":
            value_end = extract.skip_string(src, i)
            spans.append((key, i, value_end, True))
            i = value_end
        else:
            depth = 0
            j = i
            while j < close_brace:
                c = src[j]
                if c in "'\"`":
                    j = extract.skip_string(src, j)
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
            spans.append((key, i, j, False))
            i = j
    return spans


def quote_like(original, text):
    quote = original[0]
    body = (text
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            .replace(quote, "\\" + quote))
    return quote + body + quote


import re  # noqa: E402


def rewrite(src, dict_name, lookup):
    """Rewrite literal values of one dictionary; returns (new_src, changed, unknown)."""
    open_brace, close_brace = find_dict_body(src, dict_name)
    edits, unknown, changed = [], [], 0
    for key, start, end, literal in entry_spans(src, open_brace, close_brace):
        text = lookup(key)
        if text is None:
            unknown.append(key)
            continue
        if not literal:
            raw = src[start:end].strip()
            # A local constant reference (e.g. PLAN_NEXT_ACTION_EN) keeps English
            # copy in this locale; replace it with the reviewed literal.
            if re.fullmatch(r"[A-Z][A-Z0-9_]+", raw):
                edits.append((start, end, quote_like("'", text)))
                changed += 1
            continue
        current = extract.unquote(src[start:end])
        if current == text:
            continue
        edits.append((start, end, quote_like(src[start:end], text)))
        changed += 1
    for start, end, replacement in sorted(edits, reverse=True):
        src = src[:start] + replacement + src[end:]
    return src, changed, unknown


def namespace_for(path, src):
    rel = os.path.relpath(path, ROOT)
    if rel.endswith("client/locale/src/locales/settings.ts"):
        return "settings.locale"
    common_dir = os.path.join(ROOT, "packages/client/locale/src/locales")
    if os.path.dirname(path) == common_dir and os.path.basename(path) in {f"{loc}.ts" for loc in extract.LOCALES}:
        return "common"
    ns = extract.resolve_ns(path, src)
    if ns is None and "export const dictionaries = {" in src:
        sibling = os.path.join(os.path.dirname(path), "index.ts")
        if os.path.exists(sibling):
            import re
            literals = re.findall(r"locale\.register\(\s*'([^']+)'", extract.read(sibling))
            if len(literals) == 1:
                ns = literals[0]
    return ns


def stage_write(rel, text):
    target = os.path.normpath(os.path.join(STAGE, rel))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(text)
    return target


def main():
    table = translations()
    meta = meta_translations()
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    files = []
    for dp, _dn, fn in os.walk(os.path.join(ROOT, "packages")):
        if "node_modules" in dp.split(os.sep):
            continue
        if "locales.ts" in fn and "/client/" in os.path.join(dp, "locales.ts").replace(os.sep, "/"):
            files.append(os.path.join(dp, "locales.ts"))
    files.append(os.path.join(ROOT, "packages/client/locale/src/locales/settings.ts"))
    common_ru = os.path.join(ROOT, "packages/client/locale/src/locales/ru.ts")
    if os.path.exists(common_ru):
        files.append(common_ru)
    files.sort()

    total_changed = 0
    touched = 0
    unresolved = []
    for path in files:
        rel = os.path.relpath(path, ROOT)
        src = extract.read(path)
        if rel.endswith("inspector/src/client/bridge/locales.ts") or rel.endswith("zoom/locales.ts"):
            continue
        ns = namespace_for(path, src)
        if ns is None:
            unresolved.append(f"{rel}: namespace")
            continue
        if "export const dictionaries = {" in src:
            # nested shape: rewrite the `ru:` member only
            start = src.find("ru: {")
            body_open = src.index("{", start)
            body_close = extract.block_bounds(src, body_open) - 1
            fake_src = src[:body_open] + "{" + src[body_open + 1:]
            spans = entry_spans(src, body_open, body_close)
            edits = []
            for key, s0, e0, literal in spans:
                text = table.get((ns, key))
                if text is None or not literal:
                    continue
                if extract.unquote(src[s0:e0]) == text:
                    continue
                edits.append((s0, e0, quote_like(src[s0:e0], text)))
            for s0, e0, repl in sorted(edits, reverse=True):
                src = src[:s0] + repl + src[e0:]
            if edits:
                stage_write(rel, src)
                touched += 1
                total_changed += len(edits)
            continue

        lookup = lambda key, ns=ns: table.get((ns, key))  # noqa: E731
        new_src, changed, unknown = rewrite(src, "ru", lookup)
        if unknown:
            unresolved.append(f"{rel}: {len(unknown)} keys without translation, e.g. {unknown[:3]}")
        if changed:
            stage_write(rel, new_src)
            touched += 1
            total_changed += changed

    # desktop shell: native menus, tray and dialogs
    shell_path = os.path.join(ROOT, "apps/desktop/src/locale.ts")
    if os.path.exists(shell_path):
        shell_src = extract.read(shell_path)
        shell_table = {}
        for row in load_jsonl(os.path.join(HERE, "out-shell", "shell-01.jsonl")):
            shell_table[row["key"]] = row["ru"]
        shell_new, shell_changed, shell_unknown = rewrite(shell_src, "ru", lambda key: shell_table.get(key))
        if shell_unknown:
            unresolved.append(f"apps/desktop/src/locale.ts: {len(shell_unknown)} keys untranslated")
        if shell_changed:
            stage_write(os.path.relpath(shell_path, ROOT), shell_new)
            touched += 1
            total_changed += shell_changed

    # small host-owned strings: literal replacements, verified present exactly once
    host_edits = [
        ("packages/experimental/cua/src/locales.ts",
         "Управляйте разрешениями приложений для всех сеансов на странице плагина.",
         "Управляйте разрешениями приложений для всех сессий на странице плагина."),
        ("packages/experimental/cua/src/locales.ts",
         "Разрешить для этого сеанса",
         "Разрешить для этой сессии"),
        ("packages/experimental/cua/tests/application-access.spec.ts",
         "ru: 'Разрешить для этого сеанса'",
         "ru: 'Разрешить для этой сессии'"),
        ("packages/experimental/cua-macos/src/permission-guide.ts",
         "accessibility: 'Доступность'",
         "accessibility: 'Универсальный доступ'"),
        ("packages/experimental/cua-macos/src/permission-guide.ts",
         "'Откройте Системные настройки > Конфиденциальность и безопасность > {permission}.'",
         "'Откройте «Системные настройки» → «Конфиденциальность и безопасность» → {permission}.'"),
        ("packages/web/web-deepseek-api/src/search.ts",
         "учётную запись DeepSeek текущего разговора",
         "аккаунт DeepSeek текущей сессии"),
        ("packages/web/web-deepseek-api/src/fetch.ts",
         "учётную запись DeepSeek текущего разговора",
         "аккаунт DeepSeek текущей сессии"),
        ("packages/web/web-search-deepseek/src/provider.ts",
         "Требуется учётная запись DeepSeek или ключ API.",
         "Нужен аккаунт DeepSeek или ключ API."),
    ]
    host_cache = {}
    host_count = 0
    for rel, old, new in host_edits:
        text = host_cache.get(rel)
        if text is None:
            if rel not in {os.path.relpath(p, ROOT) for p in []} and not os.path.exists(os.path.join(ROOT, rel)):
                unresolved.append(f"{rel}: missing for host edit")
                continue
            text = extract.read(os.path.join(ROOT, rel))
        occurrences = text.count(old)
        if occurrences != 1:
            unresolved.append(f"{rel}: host edit matched {occurrences}x: {old[:40]!r}")
            host_cache[rel] = text
            continue
        host_cache[rel] = text.replace(old, new)
        host_count += 1
    for rel, text in host_cache.items():
        if text != extract.read(os.path.join(ROOT, rel)):
            stage_write(rel, text)
            touched += 1

    # zoom dictionaries live in their own file and are spread into two namespaces
    zoom_path = os.path.join(ROOT, "packages/client/ui-sidebar-documentpreview/src/client/zoom/locales.ts")
    zoom_src = extract.read(zoom_path)
    zoom_lookup = lambda key: table.get(("sidebarPdf", key)) or table.get(("sidebarImage", key))  # noqa: E731
    zoom_new, zoom_changed, _ = rewrite(zoom_src, "zoomRu", zoom_lookup)
    if zoom_changed:
        stage_write(os.path.relpath(zoom_path, ROOT), zoom_new)
        touched += 1
        total_changed += zoom_changed

    # plugin metadata: rewrite ru.json preserving key order and 2-space indent
    meta_changed = 0
    for (package, key), text in meta.items():
        pass
    for dp, _dn, fn in os.walk(os.path.join(ROOT, "packages")):
        if "node_modules" in dp.split(os.sep) or "ru.json" not in fn or "en.json" not in fn:
            continue
        ru_path = os.path.join(dp, "ru.json")
        package = os.path.relpath(os.path.dirname(dp), ROOT)
        with open(ru_path, encoding="utf-8") as fh:
            document = json.load(fh)
        dirty = False
        node = document.get("meta")
        if isinstance(node, dict):
            for field in ("title", "description"):
                if field not in node:
                    continue
                value = meta.get((package, f"meta.{field}"))
                if value is not None and value != node[field]:
                    node[field] = value
                    dirty = True
        if dirty:
            stage_write(os.path.relpath(ru_path, ROOT), json.dumps(document, ensure_ascii=False, indent=2) + "\n")
            touched += 1
            meta_changed += 1

    # unified diff, a/ and b/ prefixes so `git apply -p1` works from the root
    lines = []
    staged = []
    for dp, _dn, fn in os.walk(STAGE):
        for name in fn:
            staged.append(os.path.join(dp, name))
    for staged_path in sorted(staged):
        rel = os.path.relpath(staged_path, STAGE)
        original = os.path.join(ROOT, rel)
        with open(original, "rb") as fh:
            a = fh.read().decode("utf-8")
        with open(staged_path, "rb") as fh:
            b = fh.read().decode("utf-8")
        if a == b:
            continue
        import difflib
        diff = difflib.unified_diff(
            a.splitlines(keepends=True), b.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", n=2,
        )
        lines.extend(diff)
    with open(PATCH, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print(f"files touched: {touched}")
    print(f"client strings changed: {total_changed}")
    print(f"meta ru.json changed: {meta_changed}")
    print(f"patch: {os.path.relpath(PATCH, HERE)} ({os.path.getsize(PATCH) // 1024} KiB, {len(lines)} lines)")
    for item in unresolved[:20]:
        print("UNRESOLVED", item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
