#!/usr/bin/env python3
"""Вычитка русского блока настроек плагина dsh-tidy-display.

Читает vendor/tidy/settings.jsonl, правит только корявые строки,
оставляет хорошие как есть, пишет out-vendor/tidy-settings.jsonl.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "vendor" / "tidy" / "settings.jsonl"
DST = BASE / "out-vendor" / "tidy-settings.jsonl"

# Только те ключи, где текущий русский действительно правится.
FIX = {
    "openDescription": (
        "По умолчанию выключено: чипы и упоминания файлов в тексте открываются "
        "в системном приложении. Включите, чтобы открывать их в правой боковой панели, "
        "как в официальном чате. «Показать» и «Открыть папку» работают через системный "
        "файловый менеджер, как и раньше."
    ),
    "glassDescription": (
        "По умолчанию выключено: обрамление режима чтения остаётся непрозрачным, "
        "как в текущем оформлении хоста. Включите, чтобы сквозь панель просвечивали "
        "обои и темы; чипы пути и счётчика проявляются только при наведении или фокусе."
    ),
    "bubbleDescription": (
        "По умолчанию включено: итоговые ответы помещаются в скруглённый пузырь, "
        "отделяющий их от фона; в режиме матового стекла он полупрозрачный. "
        "Выключите, чтобы ответы лежали на странице без пузыря."
    ),
    "pinTitle": "Закрепить рассуждения снизу",
    "pinDescription": (
        "Выкл.: свёрнутая карточка размышлений остаётся сверху. Вкл.: всегда "
        "прокручивается к последней строке, в том числе при потоковой выдаче; "
        "прокрутка вверх или выделение текста приостанавливает её."
    ),
    "foldTitle": "Автосворачивание процесса",
    "foldDescription": (
        "По умолчанию включено: прежние шаги сворачиваются, когда появляются новые "
        "размышления. Выключите, чтобы все размышления и инструменты оставались "
        "развёрнутыми."
    ),
    "railDescription": (
        "По умолчанию включено: навигационная дорожка на canvas по краю беседы — "
        "«рыбий глаз» при наведении со сводками, переход по клику, подсветка текущего "
        "хода. Выключено: в режиме чтения дорожек нет; режим беседы возвращается "
        "к штатной дорожке."
    ),
    "railStyleBar": "Линии",
    "railRingDescription": (
        "По умолчанию включено (как в настройках плагина): мягкий белый ореол "
        "под текущей и подсвеченной отметками, чтобы их было видно на пёстрых обоях."
    ),
    "takeoverDescription": (
        "По умолчанию включено: в режиме беседы эта дорожка заменяет штатный "
        "TurnNavigator у правого края (скрывается, а не удаляется). Выключите, "
        "чтобы вернуть режим беседы штатной дорожке — эта дорожка там уступает. "
        "Режим чтения всегда использует эту дорожку. На узкой ширине Harness "
        "скрывает штатную дорожку сам; этот переключатель возвращает её, когда выключен."
    ),
    "skillPurpose": (
        "Навык нужен, чтобы модель сама выбирала MCP Apps. Режим чтения уже "
        "показывает блоки mcp-app, когда модель их выводит."
    ),
    "skillPluginNote": (
        "Наличие пакета в репозитории плагина не устанавливает его в каталог "
        "навыков Harness."
    ),
    "skillInstall": (
        "Скопируйте всю папку generative-mcpapps (включая references и examples) "
        "в .dsh/skills или .agents/skills — в домашнем каталоге или в проекте, "
        "на выбор, — и нажмите «Проверить снова». Установки в один клик, которая "
        "работает на любом хосте, нет."
    ),
    "skillChecking": "Проверка…",
    "skillUnavailable": (
        "Не удалось запросить каталог навыков хоста. Скопируйте папку в .dsh/skills "
        "или .agents/skills (домашний каталог или проект) и нажмите «Проверить снова»."
    ),
}

PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}")
TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*>")


def main() -> None:
    rows = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    changed = []
    for row in rows:
        key = row["key"]
        ru = FIX.get(key, row["ru"])
        if ru != row["ru"]:
            changed.append(key)
        out.append({"ns": row["ns"], "key": key, "ru": ru})

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", encoding="utf-8") as fh:
        for item in out:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Проверки.
    assert len(out) == len(rows) == 39, (len(out), len(rows))
    for src, dst in zip(rows, out):
        assert src["ns"] == dst["ns"] and src["key"] == dst["key"], src["key"]
        assert PLACEHOLDER.findall(src["en"]) == PLACEHOLDER.findall(dst["ru"]), dst["key"]
        assert TAG.findall(src["en"]) == TAG.findall(dst["ru"]), dst["key"]

    print(f"строк: {len(out)}")
    print(f"изменено: {len(changed)} -> {', '.join(changed)}")
    for item in out:
        assert item["ru"].strip(), item["key"]
        assert "  " not in item["ru"], item["key"]
    print("проверки пройдены")


if __name__ == "__main__":
    main()
