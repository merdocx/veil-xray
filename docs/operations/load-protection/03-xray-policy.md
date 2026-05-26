# Xray: policy, таймауты, буферы (шаг 3)

Рабочий пример полей для уровня `0` см. в [xray/config.example.json](../../../xray/config.example.json) (`policy.levels."0"`). **Prod-снимок:** [SERVER_PROFILE.md](../SERVER_PROFILE.md) (раздел Xray policy).

## Поля

- **`handshake`** (секунды) — таймаут этапа рукопожатия.
- **`connIdle`** (секунды) — простой соединения до закрытия. На прод-сервере с **2026-05-26**: **1200** (20 мин), было 1800 (30 мин). Снижение ускоряет освобождение TCP при пиках; при жалобах на обрывы — поднять до 1500–1800. Применение: `scripts/load-protection/apply-policy-connidle.sh` + `systemctl restart xray`.
- **`bufferSize`** (КБ на соединение) — в **example** `256`; на **prod** **`512`**. При давлении RAM можно снизить до 256 off-peak + рестарт Xray.

Сверяйте имена и единицы с [документацией Policy](https://xtls.github.io/config/policy.html) для **вашей** версии Xray.

## Порядок применения на проде

1. Бэкап `config.json`.
2. `xray -test -config /path/to/config.json`
3. Перезагрузка сервиса Xray в окне обслуживания при агрессивных таймаутах.

## veil-v2ray

`XrayConfigManager` меняет только **clients** (и связанные поля) у VLESS inbound; секция **`policy` не перезаписывается** при добавлении/удалении ключей, если вы не деплоите целый файл из шаблона поверх продакшена.
