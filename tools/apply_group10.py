#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply reviewed Russian strings for corpus/group-10.jsonl -> out/group-10.jsonl."""
import json

SRC = "corpus/group-10.jsonl"
DST = "out/group-10.jsonl"

CHANGES = [
    # ---------------- cuaPermissions ----------------
    ("cuaPermissions", "approvalRiskTitle", "Риски Computer Use"),
    ("cuaPermissions", "approvalRiskNotice",
     "Агент получает доступ только к приложениям, которые вы разрешили, и может читать их содержимое и управлять ими в фоновом режиме.\n"
     "\n"
     "В онлайн-играх, мессенджерах и других приложениях могут действовать ограничения на автоматизацию. Нарушение их правил может привести к приостановке или блокировке аккаунта в этом приложении.\n"
     "\n"
     "Продолжайте на свой страх и риск. Чтобы в любой момент остановить автоматизированное управление, нажмите «Остановить» в DeepSeek Harness."),
    ("cuaPermissions", "title", "Разрешить Computer Use"),
    ("cuaPermissions", "applicationsTitle", "Управление приложениями, доступными Computer Use"),
    ("cuaPermissions", "setupTitle", "Настройте Computer Use перед началом работы"),
    ("cuaPermissions", "setupBody",
     "Computer Use включён. Переключитесь в режим PTC и предоставьте разрешения «Универсальный доступ» и «Запись экрана». Откройте сведения о плагине, чтобы завершить настройку."),
    ("cuaPermissions", "setupQueryFailed",
     "Computer Use включён, но проверить системные разрешения не удалось. Откройте сведения о плагине, чтобы увидеть ошибку, и повторите попытку."),
    ("cuaPermissions", "defaultTitle", "Режим по умолчанию для новых сессий"),
    ("cuaPermissions", "defaultBody", "Computer Use работает только в режиме PTC."),
    ("cuaPermissions", "defaultConfirm", "Сделать PTC по умолчанию"),
    ("cuaPermissions", "defaultSet", "PTC — режим по умолчанию"),
    ("cuaPermissions", "defaultUnavailable",
     "Не удалось прочитать режим по умолчанию. Проверьте его в настройках."),
    ("cuaPermissions", "defaultNotSaved", "Режим по умолчанию не сохранён. Попробуйте ещё раз."),
    ("cuaPermissions", "defaultFailed", "Не удалось изменить режим по умолчанию: {message}"),
    ("cuaPermissions", "persistentBody",
     "Переменные и объекты приложения сохраняются между вызовами инструментов. Переключение перезапускает среду выполнения PTC."),
    ("cuaPermissions", "persistentConfirm", "Включить постоянный режим"),
    ("cuaPermissions", "persistentSet", "Постоянный режим включён"),
    ("cuaPermissions", "persistentUnavailable",
     "Не удалось прочитать режим выполнения PTC. Проверьте его в настройках."),
    ("cuaPermissions", "persistentNotSaved",
     "Режим выполнения PTC не сохранён. Попробуйте ещё раз."),
    ("cuaPermissions", "persistentFailed", "Не удалось изменить режим выполнения PTC: {message}"),
    ("cuaPermissions", "accessibility", "Универсальный доступ"),
    ("cuaPermissions", "accessibilityUse",
     "Читать элементы управления интерфейса, нажимать и вводить текст."),
    ("cuaPermissions", "screenRecordingUse", "Захватывать выбранное окно приложения."),
    ("cuaPermissions", "accessibilityPermission",
     "В системных настройках разрешите {application} читать элементы управления интерфейса, нажимать и вводить текст."),
    ("cuaPermissions", "screenRecordingPermission",
     "В системных настройках разрешите {application} захватывать окна приложений."),
    ("cuaPermissions", "permissionHint",
     "Разрешения «Универсальный доступ» и «Запись экрана» настраиваются в системных настройках."),
    ("cuaPermissions", "settings", "Открыть системные настройки"),
    ("cuaPermissions", "allowedApps", "Всегда разрешённые приложения"),
    ("cuaPermissions", "blockedApps", "Запрещённые приложения"),
    ("cuaPermissions", "retryApproval", "Разрешить повторный запрос"),
    ("cuaPermissions", "retryAllowed",
     "При следующем выборе приложения запрос появится снова; доступ не предоставлен"),
    ("cuaPermissions", "noApps", "Нет всегда разрешённых или запрещённых приложений."),
    ("cuaPermissions", "requested", "Следуйте инструкциям внизу окна «Системные настройки»"),
    ("cuaPermissions", "applicationsFailed", "Не удалось загрузить доступ к приложению: {message}"),
    ("cuaPermissions", "iconsFailed", "Не удалось загрузить значки приложений: {message}"),
    ("cuaPermissions", "failed", "Не удалось обновить разрешения: {message}"),

    # ---------------- session-inspector ----------------
    ("session-inspector", "tab.title", "Журнал сессии"),
    ("session-inspector", "tab.description",
     "Анализ необработанных журналов и сгруппированных сообщений чата текущей сессии на боковой панели."),
    ("session-inspector", "view.presentation", "Представление"),
    ("session-inspector", "picker.instructions",
     "Наведите указатель в основном чате, чтобы увидеть предпросмотр, затем нажмите, чтобы выбрать. Esc отменяет."),
    ("session-inspector", "picker.noChat", "Сначала откройте эту сессию в основном чате."),
    ("session-inspector", "filter.title", "Фильтр по типу"),
    ("session-inspector", "filter.input", "Ключевое слово типа"),
    ("session-inspector", "filter.placeholder", "Введите фрагмент, например delta"),
    ("session-inspector", "filter.candidates", "Подсказки типов"),
    ("session-inspector", "filter.loading", "Поиск подсказок…"),
    ("session-inspector", "filter.failed", "Не удалось загрузить подсказки типов."),
    ("session-inspector", "filter.noCandidates",
     "Подсказок нет. Ключевое слово всё равно можно применить."),
    ("session-inspector", "filter.context", "Родительский контекст совпавшей записи"),
    ("session-inspector", "table.older", "Загрузить предыдущие"),
    ("session-inspector", "table.latest", "Следить за последними"),
    ("session-inspector", "table.resizeDetails", "Изменить размер панели необработанных данных"),
    ("session-inspector", "table.expand", "Развернуть дочерние строки"),
    ("session-inspector", "table.collapse", "Свернуть дочерние строки"),
    ("session-inspector", "table.removed",
     "Запись удалена или уже завершена. Выберите актуальную запись."),
    ("session-inspector", "object.groupData", "Данные группы"),
    ("session-inspector", "object.accessor", "[Геттер / сеттер, не вычислено]"),
    ("session-inspector", "object.properties", "Другие свойства"),

    # ---------------- subagent ----------------
    ("subagent", "progress.completed", "Завершено: {count}"),
    ("subagent", "progress.active", "Выполняется: {count}"),
    ("subagent", "progress.inactive", "Не выполняется: {count}"),
    ("subagent", "progress.external", "Внешних: {count}"),
    ("subagent", "duration.exactTitle", "Общее активное время: {duration}"),
    ("subagent", "tokens.total", "Токенов: {value}"),
    ("subagent", "load.error", "Не удалось загрузить субагентов"),
    ("subagent", "readonly.unknown.body",
     "Прочтите дочернюю сессию, чтобы понять, можно ли её продолжить."),
    ("subagent", "activity.running", "выполняется"),
    ("subagent", "activity.inactive", "не выполняется"),
    ("subagent", "count.total.one", "{count} субагент"),
    ("subagent", "count.total.other", "Субагентов: {count}"),
    ("subagent", "count.running.one", "{count} субагент выполняется"),
    ("subagent", "count.running.other", "Выполняется: {count}"),
    ("subagent", "switcher.aria", "Переключиться на субагента: {title}"),
    ("subagent", "tree.aria", "Сессии субагентов"),
    ("subagent", "open.floatWindow", "Открыть в плавающей панели"),
    ("subagent", "open.sidebar.aria", "Открыть {label} в боковой панели"),
    ("subagent", "readonly.oneShot.title", "Запись одноразового субагента"),
    ("subagent", "readonly.title", "Этот субагент пока доступен только для чтения"),
    ("subagent", "readonly.oneShot.body",
     "Одноразовые задачи не принимают новые сообщения; полная запись выполнения доступна здесь."),

    # ---------------- common ----------------
    ("common", "copy.optionsHint", "{action}; правый клик — варианты копирования"),

    # ---------------- job ----------------
    ("job", "list.aria", "Фоновые задачи"),
    ("job", "section.live", "Выполняются"),
    ("job", "section.settledCount", "Завершено: {count}"),
    ("job", "row.expandAria", "Показать вывод {label} в реальном времени"),
    ("job", "row.collapseAria", "Скрыть вывод {label} в реальном времени"),
    ("job", "kill.confirm", "Нажмите ещё раз для подтверждения"),
    ("job", "kill.failed", "Не удалось остановить"),
    ("job", "status.running", "выполняется"),
    ("job", "status.stopping", "останавливается"),
    ("job", "status.killed", "отменено"),
    ("job", "duration.title.live", "Выполняется {duration}"),
    ("job", "duration.title.done", "Заняло {duration}"),
    ("job", "output.gap", "… более ранний вывод отброшен …"),
    ("job", "terminal.exitCode", "код выхода {code}"),
    ("job", "terminal.running", "выполняется"),
    ("job", "terminal.done", "готово"),
    ("job", "terminal.expand", "Показать ещё строки ({n})"),
    ("job", "terminal.expandAria", "Развернуть свёрнутые строки вывода ({n})"),

    # ---------------- workflowRun ----------------
    ("workflowRun", "run.members.one", "{count} участник"),
    ("workflowRun", "run.members.other", "Участников: {count}"),
    ("workflowRun", "run.empty", "Участники не запущены"),
    ("workflowRun", "phase.unassigned", "Без фазы"),
    ("workflowRun", "phase.empty", "Пустое название фазы"),
    ("workflowRun", "statusCount.running", "Выполняется: {count}"),
    ("workflowRun", "statusCount.completed", "Завершено: {count}"),
    ("workflowRun", "statusCount.failed", "Ошибка: {count}"),
    ("workflowRun", "statusCount.cancelled", "Отменено: {count}"),
    ("workflowRun", "statusCount.interrupted", "Прервано: {count}"),
    ("workflowRun", "member.empty", "Пустое название участника"),
    ("workflowRun", "status.running", "Выполняется"),
    ("workflowRun", "status.interrupted", "Прервано"),
]

override = {(ns, key): ru for ns, key, ru in CHANGES}
assert len(override) == len(CHANGES), "duplicate (ns, key) in CHANGES"

with open(SRC, encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

seen = set()
out = []
kept = changed = 0
for row in rows:
    ns, key = row["ns"], row["key"]
    ident = (ns, key)
    seen.add(ident)
    ru = override.get(ident, row["ru"])
    if ru == row["ru"]:
        kept += 1
    else:
        changed += 1
    out.append({"ns": ns, "key": key, "ru": ru})

missing = set(override) - seen
assert not missing, "unknown keys in CHANGES: %r" % (missing,)

with open(DST, "w", encoding="utf-8", newline="\n") as f:
    for obj in out:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

print("rows:", len(out))
print("changed:", changed)
print("kept:", kept)
