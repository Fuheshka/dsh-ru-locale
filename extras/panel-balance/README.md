# Панель расходов и баланс

Фикс интерфейса, который не является патчем файлов плагина: он меняет
конфигурацию двух уже установленных плагинов. Секретов и содержимого
`ledger.json` здесь нет — только рецепт настроек.

## Что было не так

- `dsh-cost-meter` рисовал карточку в футере сайдбара, но
  `dsh-claude-style` включал «footer takeover»: сворачивал футер в 0×0 и
  переносил его содержимое в поповер по клику на имя пользователя. В итоге
  карточка расходов появлялась не там, где нужно.
- Баланс показывал `₽0 / $0`, потому что плагин обращался к отдельному
  API-ключу `DEEPSEEK_API_KEY`, а не к балансу официального аккаунта.

## Что выставлено

1. **Claude Style → Sidebar → Redraw the account area = off**.
   В `~/.dsh/profiles/desktop/cordis.patch.yml` (фрагмент —
   [`cordis.example.yml`](cordis.example.yml)):

   ```yaml
   - id: ui-skin-claude-style
     name: dsh-claude-style
     config:
       collapseFooter: false
   ```

2. **Cost meter → Display → Sidebar**: карточка включена и остаётся в футере
   над строкой пользователя. В `~/.dsh/storages/cost-meter/ledger.json`:
   `config.sidebar: true`, `config.peakNotice: true`,
   `config.balance.display: "both"` (баланс в ₽ и $),
   `config.hideOfficialBalance: false`.

3. **Баланс**: если в настройках `dsh-cost-meter` задан отдельный
   `DEEPSEEK_API_KEY` и Balance API возвращает `$0.00`, ключ нужно убрать —
   плагин переключится на баланс официального аккаунта DeepSeek, тот же
   источник, что в **Settings → Account**. Резервная копия
   `.credentials.yaml` делается вручную перед правкой; в репозиторий она не
   попадает.

## Проверка

- В футере сайдбара над именем видны **Today**, **Balance**, **Off-peak**.
- Клик по имени открывает только штатное меню DSH, без карточки расходов.
- **Settings → Cost → Overview → Account balance** показывает тот же баланс,
  что **Settings → Account**, с точностью до живой траты.
- `Balance API key: Not configured` — это нормально, используется вход в
  аккаунт.

После правки конфигурации нужен `Cmd+R` или перезапуск DSH.
