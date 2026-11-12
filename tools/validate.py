#!/usr/bin/env python3
"""Validate translated groups against the source corpus."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
OUT = os.path.join(HERE, "out")

TOKEN_RE = re.compile(r"\{\w+\}|(?<![A-Za-z0-9/])/[A-Za-z][\w-]*(?:=[\w-]+| (?:on|off))?|\b[a-z]+_[a-z_]+\b")

FORBIDDEN = [
    (r"сеанс", "«сеанс» вместо «сессия»"),
    (r"рабочее пространство|рабочего пространства|рабочем пространстве", "«рабочее пространство» вместо «рабочая область»"),
    (r"предустановк", "«предустановка» вместо «пресет»"),
    (r"развертыв", "«развертывание» без ё"),
    (r"учетн", "«учетн-» без ё"),
    (r"Гугл|Бинг", "транслит вместо Google/Bing"),
    (r"\bты\b|\bтвой\b|\bтвоя\b|\bтебе\b", "обращение на «ты»"),
    (r"(?<![\w-])(переименуй|попробуй|сожми|удали|выбери|открой|нажми|перетащи|введи|укажи|проверь)(?![\w-])", "ты-форма императива"),
    (r"\bПожалуйста\b", "«Пожалуйста» в UI"),
    (r"Вы\b(?![\w-])", "«Вы» с большой буквы"),
    (r"  +", "двойной пробел"),
    (r"^\s|\s$", "пробелы по краям"),
    (r"[\u200b\ufeff]", "невидимый символ"),
    (r"\.\.\.", "три точки вместо …"),
    (r"\"", "прямые кавычки"),
]

GLOSSARY = [
    (r"\bsessions?\b", r"сесси", "session → сессия"),
    (r"\bworkspaces?\b", r"рабоч", "workspace → рабочая область"),
    (r"\bpresets?\b", r"пресет", "preset → пресет"),
    (r"\btools?\b", r"инструмент|tool|Tool", "tool → инструмент"),
    (r"\bplugins?\b", r"плагин", "plugin → плагин"),
    (r"\bskills?\b", r"навык", "skill → навык"),
    (r"\bsubagents?\b", r"субагент", "subagent → субагент"),
    (r"\bproviders?\b", r"провайдер", "provider → провайдер"),
    (r"\bprompts?\b", r"промпт", "prompt → промпт"),
    (r"\baccounts?\b", r"аккаунт", "account → аккаунт"),
    (r"\bcredentials?\b", r"учётн|учетн", "credentials → учётные данные"),
    (r"\bpermissions?\b", r"разрешени", "permission → разрешение"),
    (r"\bgoals?\b", r"цель|цели|целью", "goal → цель"),
    (r"\bdeliverables?\b", r"результат", "deliverable → результат"),
    (r"\btrajectory\b", r"траектор", "trajectory → траектория"),
    (r"\breasoning\b", r"рассужден", "reasoning → рассуждения"),
    (r"\bqueue\b", r"очеред|очередь", "queue → очередь"),
    (r"\battachment\b", r"вложени", "attachment → вложение"),
    (r"\bfolders?\b", r"папк", "folder → папка"),
    (r"\bupload(?:s|ing|ed)?\b", r"загруз|загруж", "upload → загрузка"),
    (r"\bdownload(?:s|ing|ed)?\b", r"скачива|скачан|загруз", "download → скачивание"),
    (r"\btheme\b", r"тем", "theme → тема"),
    (r"\bshortcuts?\b", r"клавиш|сочетани", "shortcut → сочетание клавиш"),
]

ALLOWED_LATIN = set("""
DeepSeek DSH Harness Cordis Forge Live Share Computer Use MCP API CLI UI URL HTTP HTTPS
JSON YAML Markdown npm pnpm npx Git GitHub GitLab Bash PowerShell Node Node.js Python React
TypeScript OAuth CORS SSE WebSocket PTY SQLite Claude Code Codex Gemini OpenAI Anthropic
Google Bing ZeroSSL Linux macOS Windows Docker SSH ID KB MB GB KB KB PR README RU EN
""".split())


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


PLACEHOLDER_RE = re.compile(r"\{\w+\}")


def prose_en(en):
    """English text with placeholders removed, used for term checks."""
    return PLACEHOLDER_RE.sub(" ", en or "")


def cyrillic_free(text):
    return not re.search(r"[А-Яа-яЁё]", text or "")


def check_group(name):
    src_path = os.path.join(CORPUS, f"{name}.jsonl")
    out_path = os.path.join(OUT, f"{name}.jsonl")
    src = load(src_path)
    if not os.path.exists(out_path):
        return {"group": name, "ok": False, "fatal": "missing output file", "count": 0}
    out = load(out_path)
    problems = []
    stats = {"group": name, "ok": True, "expected": len(src), "got": len(out), "issues": []}
    if len(src) != len(out):
        stats["ok"] = False
        stats["issues"].append(f"line count {len(out)} != {len(src)}")
    src_pairs = [(r["ns"], r["key"]) for r in src]
    out_pairs = [(r["ns"], r["key"]) for r in out]
    if src_pairs != out_pairs:
        missing = [p for p in src_pairs if p not in set(out_pairs)]
        extra = [p for p in out_pairs if p not in set(src_pairs)]
        stats["ok"] = False
        stats["issues"].append(f"key mismatch missing={missing[:3]} extra={extra[:3]}")
    out_map = {p: r for p, r in zip(out_pairs, out)}
    for s in src:
        pair = (s["ns"], s["key"])
        o = out_map.get(pair)
        if o is None:
            continue
        ru = o.get("ru")
        en = s.get("en")
        if not isinstance(ru, str) or ru.strip() == "":
            problems.append((pair, "пустой текст", en, ru))
            continue
        if en:
            a = sorted(TOKEN_RE.findall(en))
            b = sorted(TOKEN_RE.findall(ru))
            if a != b:
                problems.append((pair, f"плейсхолдеры {a} != {b}", en, ru))
        for pattern, reason in FORBIDDEN:
            if re.search(pattern, ru):
                problems.append((pair, f"запрет: {reason}", en, ru))
        en_prose = prose_en(en)
        for en_pat, ru_pat, reason in GLOSSARY:
            if re.search(en_pat, en_prose, re.I) and not re.search(ru_pat, ru, re.I):
                problems.append((pair, f"глоссарий: {reason}", en, ru))
        en_dot = bool(en) and en.rstrip().endswith(".")
        ru_dot = ru.rstrip().endswith(".")
        if en and en_dot != ru_dot and len(ru) > 20:
            problems.append((pair, "пунктуация: точка в конце расходится с en", en, ru))
        if en and len(en) > 12:
            ratio = len(ru) / len(en)
            if ratio > 2.6 or ratio < 0.35:
                problems.append((pair, f"длина ru/en = {ratio:.2f}", en, ru))
        en_words = [w for w in re.findall(r"[a-z]{3,}", en_prose)]
        if ru == en and len(en_words) >= 2:
            problems.append((pair, "не переведено", en, ru))
        stripped = PLACEHOLDER_RE.sub(" ", ru)
        stripped = re.sub(r"\b[A-Za-z][\w.-]*@[\w.-]+", " ", stripped)
        latin = [w for w in re.findall(r"[A-Za-z][A-Za-z.+#-]{1,}", stripped)
                 if w not in ALLOWED_LATIN and w.lower() == w]
        if latin and en_words:
            problems.append((pair, f"английский текст в ru: {sorted(set(latin))[:5]}", en, ru))
    stats["issues"].extend(f"{p[0][0]}/{p[0][1]}: {p[1]}" for p in problems)
    stats["samples"] = [
        {"ns": p[0][0], "key": p[0][1], "why": p[1], "en": p[2], "ru": p[3]} for p in problems[:6]
    ]
    stats["problem_count"] = len(problems)
    if len(problems) > max(5, len(src) * 0.08):
        stats["ok"] = False
    return stats


def main():
    names = sorted(f[:-6] for f in os.listdir(CORPUS) if f.endswith(".jsonl"))
    report = [check_group(n) for n in names]
    with open(os.path.join(HERE, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    for r in report:
        flag = "OK " if r.get("ok") else "BAD"
        print(f"{flag} {r['group']}: {r.get('got')}/{r.get('expected')} rows, "
              f"{r.get('problem_count', 0)} issues")
        for issue in r.get("issues", [])[:6]:
            print("      ", issue)
    total = sum(r.get("problem_count", 0) for r in report)
    print(f"\ntotal issues: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
