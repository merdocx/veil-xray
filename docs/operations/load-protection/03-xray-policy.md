# Xray: policy, таймауты, буферы (шаг 3)

Рабочий пример полей для уровня `0` см. в [xray/config.example.json](../../../xray/config.example.json) (`policy.levels."0"`). **Prod-снимок:** [SERVER_PROFILE.md](../SERVER_PROFILE.md) (раздел Xray policy).

## Поля

- **`handshake`** — **4** с (рекомендация Xray docs; было 60).
- **`connIdle`** — **300** с (default Xray; было 1200/1800). При обрывах idle — поднять до 600–900; при FIN-WAIT — не выше 300 без baseline.
- **`uplinkOnly` / `downlinkOnly`** — **2** / **5** с (Xray docs).
- **`bufferSize`** — **256** KiB (best practice при ~100 пользователях; было 512).
- Применение: `scripts/load-protection/apply-policy-recommended.sh` + `systemctl restart xray`.

Сверяйте имена и единицы с [документацией Policy](https://xtls.github.io/config/policy.html) для **вашей** версии Xray.

## Порядок применения на проде

1. Бэкап `config.json`.
2. `xray -test -config /path/to/config.json`
3. Перезагрузка сервиса Xray в окне обслуживания при агрессивных таймаутах.

## veil-xray-api

`XrayConfigManager` меняет только **clients** (и связанные поля) у VLESS inbound; секция **`policy` не перезаписывается** при добавлении/удалении ключей, если вы не деплоите целый файл из шаблона поверх продакшена.
