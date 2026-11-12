# Патч русского перевода для исходников DSH

Единый diff для чекаута `~/Documents/GitHub/deepseek-harness` (ветка `master`, версия
`0.2.2-rc.1`): приводит штатный русский словарь к тому же вычитанному виду, что и
языковой пакет. Код, ключи, структура файлов и остальные локали не меняются —
только русский текст.

## Состав

| Что | Файлов | Строк |
| --- | --- | --- |
| Словари клиента (`packages/*/src/client/**/locales.ts`) | 67 | ~1555 |
| Метаданные плагинов (`packages/*/locale/ru.json`) | 286 | 350 |
| Оболочка Electron (`apps/desktop/src/locale.ts`: меню, трей, диалоги) | 1 | 93 |
| Хостовые строки (cua, cua-macos, web-провайдеры) + ожидание в cua-спеке | 6 | 7 |
| **Итого** | **360** | **~2005** |

Правки точечные: заменяются только значения существующих русских строк. Порядок
ключей, комментарии, нелитеральные значения, `satisfies`-аннотации и все прочие
локали (`zh`, `en`, `ja`, `es`, `fr`, `de`, `pt`) остаются байт-в-байт.

Отдельно исправлен баг: `hint.plan` и `placeholder.plan` в русском словаре ссылались
на английскую константу `PLAN_NEXT_ACTION_EN`, теперь там русский текст.

## Статус: применён и закоммичен

Патч применён в чекауте на ветке **`i18n/ru-copy-review`** (от `master`, `fcc0ad4621`):

| Коммит | Что | Файлов |
| --- | --- | --- |
| `9cd149bdc3` | `i18n(ru): replace machine-translated client UI copy` | 67 |
| `40107a1d1d` | `i18n(ru): review plugin metadata translations` | 286 |
| `eaa5fa968f` | `i18n(ru): align desktop shell and host-owned copy` | 7 |

Рабочее дерево чистое, 360 файлов. Прогнаны гейты репозитория и pre-commit хуки
(lefthook: lint, whitespace, vendor manifest) — все зелёные:

```
run-gates: PASS Windows installer locales
run-gates: PASS plugin locale metadata
run-gates: PASS locale dictionaries
run-gates: 3 passed, 0 failed
```

Вернуться на master: `git switch master`. Откатить ветку: `git branch -D i18n/ru-copy-review`.

Отправка в GitHub (origin — upstream, прав на push нет; нужен форк):

```bash
gh repo fork deepseek-ai/deepseek-harness --clone=false --remote=true
git push -u fork i18n/ru-copy-review
gh pr create --repo deepseek-ai/deepseek-harness \
  --head Fuheshka:i18n/ru-copy-review \
  --title "i18n(ru): review the Russian localization" \
  --body-file /Users/fuheshka/Documents/Obsidian\ Vault/.dsh-locale-ru/PR.md
```

## Как применить с нуля

```bash
cd ~/Documents/GitHub/deepseek-harness
git switch -c ru-locale-review          # по желанию: отдельная ветка
git apply --check "/Users/fuheshka/Documents/Obsidian Vault/.dsh-locale-ru/dsh-ru-locale.patch"
git apply         "/Users/fuheshka/Documents/Obsidian Vault/.dsh-locale-ru/dsh-ru-locale.patch"
git diff --stat
```

Проверки после применения:

```bash
pnpm run check:i18n      # плейсхолдеры и полнота словарей
pnpm run build           # если нужна сборка из исходников
```

Откат: `git apply -R <patch>` или `git checkout -- .` (на чистом checkout).

## Что это меняет и не меняет

- Меняет: русский текст в исходниках — то есть в приложении, собранном из этого
  чекаута, и в будущих релизах/PR.
- Не меняет: уже установленное приложение `/Applications/DeepSeek Harness.app`
  (его словарь лежит внутри подписанного `app.asar`). Живой интерфейс сейчас
  обслуживает языковой пакет из `.dsh-locale-ru/pkg`.
- Не входит: документация `docs/DETAIL.*` (пара en/zh), модельные промпты,
  тесты — кроме одной ожидаемой строки в `cua`-спеке, обновлённой вместе с текстом.

## Как пересобрать патч после правок перевода

```bash
cd "/Users/fuheshka/Documents/Obsidian Vault/.dsh-locale-ru/tools"

# клиентский UI
python3 extract.py && python3 group.py
#   → правка tools/out/group-NN.jsonl ({"ns","key","ru"})
python3 validate.py            # плейсхолдеры, глоссарий, запреты
python3 build.py               # языковой пакет: ../pkg/client.js

# метаданные плагинов
python3 extract_meta.py
#   → правка tools/out-meta/meta-NN.jsonl
# оболочка Electron
#   → правка tools/out-shell/shell-01.jsonl

python3 patch_build.py         # ../dsh-ru-locale.patch + ../stage/
```

`tools/overrides.jsonl` — точечные правки поверх групп (используются и пакетом, и
патчем). `tools/style-guide.md` — правила и глоссарий.
