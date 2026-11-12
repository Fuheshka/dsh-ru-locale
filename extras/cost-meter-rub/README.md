# DUAL ₽ / $ для dsh-cost-meter

Патч для `dsh-cost-meter@1.9.64`: добавляет режим **RUB + USD** и показывает
каждую сумму сразу в двух валютах — `₽17.65 / $0.2122`. USD / CNY / EUR
остаются в селекте.

Установленный плагин лежит в
`~/.dsh/profiles/desktop/node_modules/dsh-cost-meter`. Патч правит девять
файлов его `lib/`; исходный пакет не пересобирается.

## Что меняется

- в селект валюты добавляется `RUB + USD (₽ / $)` (внутри — currency `DUAL`);
- каждая сумма выводится как `₽X / $Y`: рубли по курсу из конфига, доллары —
  исходная цена API;
- `DUAL` добавлен во все enum-списки валют в статистике и экспорте;
- баланс плагина пересчитывается в рубли;
- автообновление курса RUB переведено с Frankfurter (ECB, без рубля) на
  `@fawazahmed0/currency-api`;
- убрана дневная проверка `exchangeRateDate`, из-за которой курс не
  обновлялся при уже установленной дате; остался часовой троттлинг.

## Установка

Из корня этого репозитория:

```bash
cd extras/cost-meter-rub
./install-autofix.sh
```

Скрипт ставит launchd-агент `com.fuheshka.dsh-cost-meter-rub-autofix` с
интервалом 60 секунд. Он сканирует все `~/.dsh/profiles/*/node_modules/dsh-cost-meter`
и заново применяет патч после обновления плагина.

Проверка:

```bash
launchctl print "gui/$(id -u)/com.fuheshka.dsh-cost-meter-rub-autofix"
tail -n 20 autofix.log
cat autofix-state.json
```

Удаление:

```bash
./install-autofix.sh --uninstall
```

## Ручное применение

```bash
cd extras/cost-meter-rub

node patch.mjs --check          # проверить, не слетел ли патч
node patch.mjs --if-needed      # применить только недостающее
node patch.mjs --rate=90.00     # задать курс в пресете RUB / DUAL
node patch.mjs --restore        # вернуть *.rub-bak
```

Без `--rate` уже настроенный курс сохраняется: авто-фиксер не сбрасывает
ручную настройку. Активный курс хранится в
`~/.dsh/storages/cost-meter/ledger.json` и обновляется автоматически.

Перед записью каждый бандл проверяется через `node --check` во временном
каталоге; запись идёт через временный файл и `rename`. Перед первой правкой
новой версии создаётся `backup/dsh-cost-meter-<version>.tgz` (хранятся три
последних).

## После установки

1. Перезагрузить окно DSH: `Cmd+R`.
2. **Settings → Cost → Display** → раскрыть
   **General · appearance, currency and language** → **Currency** →
   **RUB + USD (₽ / $)**.
3. Курс подтянется сам; при желании его можно поправить в поле
   **Exchange rate**.

## Ограничения

- Патч рассчитан на структуру бандлов `1.9.64`. После крупного обновления
  якоря могут не совпасть: `patch.mjs` завершится с `FAIL: ... expected
  exactly 1 anchor`, ничего не запишет, а авто-фиксер напишет ошибку и один
  раз покажет уведомление macOS.
- Нативная карточка **Settings → Account → Основной баланс** относится к ядру
  DSH и остаётся в валюте, которую вернул DeepSeek (USD). Патч плагина на неё
  не влияет.
