# Аудит: весь пользовательский трафик через релей `77.238.243.136`

Проверено: боевой `/usr/local/etc/xray/config.json`, [xray/config.example.json](../../xray/config.example.json), скрипты и документация в `veil-v2ray` (без `venv/`).

## Итог

**Пользовательский трафик с `vless-reality` (кроме явных исключений ниже) идёт в outbound `upstream` → SOCKS `77.238.243.136:1080`.**

Правил вида `geosite:category-ru` / `geoip:ru` → `direct` в текущих конфигах **нет** (split отключён).

## Исключения (намеренные)

| Правило | Куда | Зачем |
|---------|------|--------|
| `inboundTag: api-in` → `api` | Локальный API Xray | Управление Xray с `127.0.0.1:10085`, не «интернет пользователя». |
| `ip: 77.238.243.136` → `direct` | Только **если цель соединения — сам IP релея** | Иначе Xray пытался бы открыть SOCKS к релею **через** SOCKS → петля. Это не «обход» пользовательского трафика. |
| `vless-reality` + порт **53** (UDP/TCP) → `direct` | DNS с этого сервера напрямую к резолверам | Не через SOCKS; иначе нужен UDP на релее. **IP-сайтов после DNS** идут дальше по правилам → обычно `upstream`. |
| `geoip:private` → `block` | Частные сети | Безопасность; не про релей. |

## Что не трогает маршрутизацию Xray

- **veil-v2ray (FastAPI):** правки `clients` в inbound, не перезаписывает `routing`/`outbounds` при нормальной работе [xray_config.py](../../api/xray_config.py).
- **Строки «direct» в логах API** — про fallback при ошибке API, не про outbound Xray.

## Устаревшие инструкции

Файл [routing-split-ru-restore.md](routing-split-ru-restore.md) содержит **старый** набор правил со split RU/foreign. Его включают **только если** снова нужен split. Текущий пример в репозитории — **без** split.

## Проверка на сервере

```bash
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
grep -E 'outboundTag|77\.238' /usr/local/etc/xray/config.json
```

Ожидание: один SOCKS на `77.238.243.136`, для `vless-reality` единый catch-all → `upstream` после правил выше.
