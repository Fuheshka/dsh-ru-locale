#!/usr/bin/env python3
"""Сборка русского перевода плагина dsh-tidy-display (source == tidy-display)."""
import json
import re
import sys

SRC = "vendor/vendor-corpus.jsonl"
OUT = "out-vendor/tidy.jsonl"
SOURCE = "tidy-display"

# Переписанные строки. Всё, чего здесь нет, проверено и оставлено как есть.
FIX = {
    "common.expandLines": "Развернуть ещё: {n}",
    "view.reader": "Просмотр",
    "reader.fallbackError": "Сервис модели не отвечает или соединение прервано. Повторите попытку.",
    "reader.steering": "Направляющее сообщение",
    "reader.turnError": "Ход завершился с ошибкой",
    "reader.retryNotice": "Запрос к модели не удался, ожидается повтор. Подробности — в процессе.",
    "reader.commandError": "Команда завершилась с ошибкой",
    "reader.unknownNode": "Этот тип записи ещё не поддерживается в режиме просмотра: {kind}",
    "reader.sessionError": "Эту сессию сейчас нельзя прочитать: {message}",
    "reader.loading": "Загрузка сессии…",
    "reader.deepDiving": "Размышляет…",
    "reader.pendingQuestion": "Нужен ответ на вопрос",
    "reader.pendingConfirm": "Требуется подтверждение",
    "reader.pendingHint": (
        "Обработайте это в области действий ниже. "
        "Уведомление не сворачивается вместе с процессом."
    ),
    "reader.blockError": (
        "Это содержимое нельзя показать в режиме просмотра. "
        "Запись в исходной беседе не затронута."
    ),
    "reader.unknownBlock": (
        "Этот тип содержимого ещё не поддерживается в режиме просмотра; "
        "исходное содержимое сохранено."
    ),
    "reader.rawContent": "Посмотреть сырое содержимое",
    "reader.viewInChat": "Посмотреть в беседе",
    "reader.modelRetryRecord": "Запись повтора запроса к модели",
    "reader.copyFailed": "Не удалось скопировать. Выделите текст вручную",
    "reader.forkAria": "Ответвить новую сессию отсюда",
    "reader.forkTitle": "Ответвить новую сессию отсюда (Fork)",
    "reader.blockErrorDetail": "({detail})",
    "image.alt": "Изображение из беседы",
    "image.preview": "Предпросмотр изображения",
    "image.close": "Закрыть предпросмотр",
    "status.elapsedSec": "Заняло {n} с",
    "status.elapsedMin": "Заняло {m} мин {s} с",
    "status.awaitUser": "Ожидает вас",
    "status.subagents": "Субагентов: {count}",
    "status.thinking": "Размышляет",
    "status.processing": "Работает",
    "compaction.label": "Контекст истории сжат",
    "compaction.items": "Сжато записей контекста: {items}",
    "compaction.itemsTokens": (
        "Сжато записей контекста: {items} · освобождено около {tokens} токенов"
    ),
    "compaction.titleCollapse": "Свернуть сводку памяти",
    "compaction.titleExpand": "Развернуть, чтобы прочитать сводку, сформированную в этом узле",
    "compaction.toggleCollapse": "Скрыть сводку",
    "compaction.toggleExpand": "Показать сводку",
    "compaction.summaryHeader": "Сводка по предыдущей части диалога",
    "compaction.errorTitle": "Не удалось сжать контекст",
    "deliverables.more": "+ файлов: {count}",
    "deliverables.workspaceTitle": "Открыть папку рабочей области в файловом менеджере",
    "deliverables.openedExternal": "Открыто во внешнем приложении",
    "deliverables.revealTitle": "Показать папку с файлом ({folder})",
    "deliverables.revealAria": "Показать папку с файлом",
    "toolbar.autoFoldOn": "Автосворачивание вкл",
    "toolbar.autoFoldOff": "Автосворачивание выкл",
    "history.error": (
        "Не удалось загрузить историю. Повторите попытку. "
        "Уже загруженное не изменилось."
    ),
    "tool.writeReturned": (
        "Файловый инструмент вернул ответ. Ниже отправленное содержимое; "
        "полная запись — в разделе «Сырые данные»."
    ),
    "tool.codeNoOutput": "Код выполнен, вывода нет",
    "tool.receivedChars": "Получено символов ввода: {n}",
    "tool.webSearch": "Поиск в интернете",
    "tool.exitCode": "Код выхода: {code}",
    "tool.signal": "Сигнал: {signal}",
    "tool.resultRecorded": "Результат записан",
    "tool.rawNote": "Полная запись · только чтение · код внутри не выполняется",
    "reason.label": "Размышления",
    "reason.region": "Размышления на шаге {n}",
    "reason.regionScrollable": "Размышления на шаге {n}, с прокруткой",
    "reason.pauseAria": "Приостановить слежение за размышлением",
    "reason.resumeAria": "Продолжить следить за последним размышлением",
    "reason.follow": "Следить за последним",
    "reason.scrollableReading": "Прокрутка для чтения",
    "reason.collapseAria": "Свернуть размышления",
    "reason.expandAria": "Развернуть и прочитать размышления полностью",
    "disclosure.process": "Размышления и процесс",
    "fold.processDetail": "Подробности процесса этого хода",
    "turn.aborted": "Ход остановлен, сформированное содержимое сохранено.",
    "turn.blocked": "Ход заблокирован. Проверьте исходную беседу и область действий ниже.",
    "turn.maxTokens": "Вывод достиг лимита длины хода и может быть неполным.",
    "turn.error": "Ход не завершён. Ошибка ниже.",
    "turn.unknown": (
        "Ход завершился со статусом: {reason}. "
        "Проверьте полную запись в исходной беседе."
    ),
    "metrics.tokensTitle": "Расход токенов за этот ход",
    "metrics.usage": "Расход: {tokens}",
    "metrics.timingTitle": "Длительность и скорость этого хода",
    "metrics.dialogAria": "Обзор хода",
    "metrics.header": "Производительность и расход за ход",
    "metrics.timingSection": "Длительность и скорость генерации",
    "metrics.ttft": "Время до первого токена (TTFT)",
    "metrics.cacheRead": "Чтение из кэша",
    "metrics.thinkingTokens": "Размышления: {n}",
    "time.ranFor": "Заняло {duration}",
    "rail.olderTip": (
        "Нажмите, чтобы загрузить более ранние записи · "
        "полоса охватывает только загруженные ходы: {count}"
    ),
    "diff.linesAria": "{label} · добавлено строк: {added}, удалено: {removed}",
    "mcp.generating": "Генерация интерактивного компонента…",
    "mcp.generatingNamed": "Генерация интерактивного компонента ({title})…",
    "mcp.fillHint": "Перенесите результат в поле ввода и нажмите Enter, чтобы отправить",
    "read.window": "Показано строк: {shown} / {total}",
    "search.matches": "Совпадений: {shown} / {total} · файлов: {files}",
    "json.truncated": "Содержимое слишком длинное, усечено ({total} символов)",
}

PH = re.compile(r"\{[^{}]+\}")
rows = [json.loads(line) for line in open(SRC, encoding="utf-8") if line.strip()]
tidy = [r for r in rows if r.get("source") == SOURCE]

out = []
for r in tidy:
    ru = FIX.get(r["key"], r["ru"])
    out.append({"ns": r["ns"], "key": r["key"], "ru": ru})

# --- проверки ---
errors = []
if len(out) != len(tidy):
    errors.append(f"строк {len(out)}, ожидалось {len(tidy)}")
seen = set()
for r, o in zip(tidy, out):
    k = (o["ns"], o["key"])
    if k in seen:
        errors.append(f"дубль ключа {k}")
    seen.add(k)
    if (o["ns"], o["key"]) != (r["ns"], r["key"]):
        errors.append(f"ключ не совпал: {r['key']} -> {o['key']}")
    a = sorted(PH.findall(r["en"]))
    b = sorted(PH.findall(o["ru"]))
    if a != b:
        errors.append(f"{r['key']}: плейсхолдеры {a} != {b}")
    if not o["ru"].strip():
        errors.append(f"{r['key']}: пустой ru")

# типографика и термины
BAD = {
    "проход": "turn должен быть «ход»",
    "сеанс": "session должен быть «сессия»",
    "Под-агент": "subagent должен быть «субагент»",
    "развертыван": "нужно «развёртыван»",
    "（": "полноширинная скобка",
    "）": "полноширинная скобка",
    "...": "многоточие одним символом",
    "Пожалуйста": "«Пожалуйста» запрещено",
    "ты-форма:": "",
}
for o in out:
    for bad, why in BAD.items():
        if bad and bad in o["ru"]:
            errors.append(f"{o['key']}: «{bad}» — {why}")
    if re.search(r"(^|[^\w])ты([^\w]|$)", o["ru"]):
        errors.append(f"{o['key']}: ты-форма")

if errors:
    print("\n".join(errors))
    sys.exit(1)

with open(OUT, "w", encoding="utf-8") as f:
    for o in out:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")

print(f"ok: {len(out)} строк, изменено {len(FIX)}")
