# Конфигурация Xray

| Файл | Назначение |
|------|------------|
| [config.example.json](config.example.json) | Пример: несколько inbounds (443, 446, 447, 448, XHTTP, Trojan), outbound **SOCKS `upstream`**, routing через релей |

Перед продакшеном:

1. Сгенерируйте свои ключи Reality: `xray x25519`
2. Замените IP релея `77.238.243.136` на **ваш** egress-хост (любой VPS/страна)
3. Выберите режим исходящего трафика: [docs/operations/egress-modes.md](../docs/operations/egress-modes.md)

Проверка: `xray run -test -config /usr/local/etc/xray/config.json`

Теги inbounds должны совпадать с `.env` (`XRAY_VLESS_*_INBOUND_TAG` в [config/settings.py](../config/settings.py)).
