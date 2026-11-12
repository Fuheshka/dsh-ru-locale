# i18n(ru): review the Russian localization

The shipped Russian dictionaries read like machine translation. This PR reviews
them in place: keys, key order, placeholders, slash commands, non-literal values
and every other locale stay byte-identical — only Russian text changes.

## Why

Concrete defects in the current copy, not a matter of taste:

- **One concept, two words.** `session` is «сеанс» 127 times and «сессия» 19 times,
  sometimes on the same screen (`placeholder.unavailable` vs
  `file.sessionUnavailable`).
- **Terminology drift.** «рабочее пространство» / «рабочая область» for workspace,
  «предустановка» / «пресет» / «предварительная настройка» for preset,
  «поставщик» / «провайдер» for provider.
- **Voice.** "ты" imperatives («переименуй», «сожми», «попробуй») mixed with «вы»
  («удалите», «уменьшите»).
- **Broken constructions** produced by MT:
  - `image.modelUnsupported`: «Текущая модель не поддерживает изображения;
    переключиться на модель, которая делает»
  - `file.stillUploading`: «Файлы все еще загружаются; отправить после того, как
    они закончат»
  - `settings.models.modelReasoningHelpText`: «Эта модель не обеспечивает
    обоснования уровней усилий»
  - `pluginMarket`: «Развернутое обоснование отправляется в выбранную службу» —
    a mistranslation of *deployment*.
- **Latin product names transliterated**: «Гугл», «Бинг» for Google, Bing.
- **Counts that break on 1**: «до {count} изображений», «{count} вызовов
  инструментов».

## What changed

| Part | Files | Strings |
| --- | --- | --- |
| Client UI dictionaries (`packages/*/src/client/**/locales.ts`) | 67 | 1515 |
| Plugin metadata (`locale/**/ru.json`: titles, descriptions) | 286 | 350 |
| Desktop shell (`apps/desktop/src/locale.ts`: menus, tray, dialogs) | 1 | 101 |
| Host-owned copy (Computer Use, permission guide, web providers) + one spec expectation | 6 | — |
| **Total** | **360** | **~1966** |

Deliberate choices, applied consistently:

- **One terminology.** сессия, ход/шаг, рабочая область, пресет, инструмент,
  субагент, промпт, провайдер, установка, подтверждение, разрешение, навык.
- **One voice.** Infinitive labels («Отправить», «Копировать»), «вы» without the
  pronoun in hints («Выберите модель»), impersonal errors («Не удалось сохранить»).
  No "ты" forms.
- **Counts stay grammatical for any number** where the flat dictionary cannot
  pluralize: «Вызовов: {count}», «Изображений: не больше {count}».
- **macOS conventions** in the shell copy: «Завершить», «Скрыть остальные»,
  «О программе», «Версия {version}».
- **ё, «ёлочки», em dash, single ellipsis** everywhere; sentence case for labels.
- **`hint.plan` / `placeholder.plan`** no longer reference the English
  `PLAN_NEXT_ACTION_EN` constant, so the plan hint is actually Russian.

## Verification

```
pnpm run check:i18n                  # 3 passed, 0 failed
pnpm run verify-client-ui-i18n       # 1275 source files use locale-owned copy
pnpm run verify-locale-metadata      # complete shipped-language metadata
pnpm run verify-installer-locales    # 8 languages, matching keys and placeholders
```

Additional checks on the change set itself:

- placeholders, slash commands and `snake_case` field names preserved per string;
- `meta.detail` paths untouched (including `docs/DETAIL.ru.md` for Forge);
- no client source file outside the `ru` dictionary changed;
- all touched TypeScript transpiles without diagnostics;
- `lefthook` pre-commit (lint, whitespace, vendor manifest) passes.

## Not in scope

- Documentation pairs (`docs/**` stay en/zh).
- Model-facing prompts and tool schemas.

## Screens or recordings

Not applicable — text only.

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
