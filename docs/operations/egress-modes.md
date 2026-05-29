# Режимы исходящего трафика (egress)

Veil Xray **не выбирает страну выхода** — это настраивается на **каждом сервере** в `config.json` Xray и (при необходимости) в ОС (WireGuard, маршрутизация). Релей — **любой удалённый хост** с публичным IP, через который должен выходить трафик клиентов.

API (`veil-xray-api`) **не управляет** WireGuard и SOCKS: только пользователями и inbounds. Egress — зона ответственности админа и `xray/config.json`.

---

## Три режима

| Режим | Outbound в Xray | Когда использовать |
|--------|-----------------|-------------------|
| **Прямой** | `direct` | Edge-узел, отдельный IP входа, тестовый стенд; трафик выходит с IP **этого** сервера |
| **SOCKS-релей** | `upstream` (protocol `socks`) | Входной узел без WG; релей поднимает SOCKS (например Dante) |
| **WireGuard-релей** | `wg-egress` (`freedom` + `sockopt.mark`) | Входной узел с туннелем `wg0` на релей; трафик с mark уходит в таблицу маршрутизации через WG |

Пример IP релея в репозитории: `77.238.243.136` — **один из деплоев**, не требование «Нидерланды». Подставьте свой `RELAY_HOST` / `RELAY_IP`.

---

## Роли серверов

```text
[Клиент VPN] → [Входной узел: Xray inbounds] → ? → [Интернет]
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │ direct                  │ SOCKS / WG на RELAY_HOST │
                    ▼                         ▼                         │
              IP входного сервера      IP релея (любая страна/ДЦ)       │
```

- **Входной узел** — принимает VLESS/Trojan, в API создаются ключи.
- **Релей (egress)** — опционально; другой VPS/дедик, с которого в интернет уходит уже «чистый» IP.
- **Edge без релея** — один сервер: inbounds + `direct` (как на отдельных IP входа).

---

## Шаблоны в репозитории

| Файл / документ | Содержание |
|-----------------|------------|
| [xray/config.example.json](../../xray/config.example.json) | Inbounds + outbound **`upstream`** (SOCKS на `RELAY_HOST:1080`) + routing → `upstream` |
| Ниже в этом файле | Фрагмент **`wg-egress`** и правила routing |
| [routing-split-ru-restore.md](routing-split-ru-restore.md) | Опционально: RU → `direct`, остальное → релей |
| [RECOMMENDED_SETTINGS.md](RECOMMENDED_SETTINGS.md) | Policy, SLO; пример prod с WG |
| [SERVER_PROFILE.md](SERVER_PROFILE.md) | Эталон **конкретного** входного хоста (примеры IP — не универсальны) |

Проверка SOCKS с входного узла:

```bash
RELAY_HOST=1.2.3.4 EXPECTED_RELAY_IP=1.2.3.4 bash scripts/verify-egress-via-relay.sh
```

---

## WireGuard: фрагмент для `config.json`

На **входном** узле (после настройки `wg-quick@wg0` и policy routing, mark `0x77` / `119`):

```json
{
  "protocol": "freedom",
  "tag": "wg-egress",
  "settings": { "domainStrategy": "UseIPv4" },
  "streamSettings": {
    "sockopt": { "mark": 119 }
  }
}
```

Правила routing (схема):

| Условие | Outbound |
|---------|----------|
| VPN inbounds, весь трафик | `wg-egress` |
| DNS :53 с inbound | `wg-egress` (или отдельный DNS outbound) |
| IP **релея** (`RELAY_IP`) | `direct` (анти-петля) |
| `geoip:private` | `block` |

Проверка:

```bash
curl -4 --interface wg0 https://api.ipify.org
# Ожидается публичный IP релея, не входного узла
```

Конфиг интерфейса WG (`/etc/wireguard/wg0.conf`) в репозиторий **не входит** — создаётся на хосте (peer = ваш `RELAY_HOST:51820` или иной порт).

---

## SOCKS: фрагмент (уже в `config.example.json`)

Замените `77.238.243.136` на адрес вашего релея в `outbounds` и в правиле `ip → direct`.

### Аудит режима «весь трафик через SOCKS»

При routing из `config.example.json` пользовательский трафик с VPN-inbounds → `upstream`, **без** split RU (`geosite:category-ru` / `geoip:ru` → `direct`).

| Правило | Outbound | Зачем |
|---------|----------|--------|
| `api-in` | `api` | Локальный Xray API, не интернет клиентов |
| `ip: RELAY_IP` | `direct` | Анти-петля при подключении к самому релею |
| VPN + порт **53** | `direct` (или `dns-out`) | DNS; после резолва сайты идут по остальным правилам |
| `geoip:private` | `block` | Частные сети |
| остальной VPN-трафик | `upstream` | Выход через SOCKS |

API (`veil-xray-api`) меняет только `clients` в inbounds, не перезаписывает `routing`/`outbounds`. Split RU: [routing-split-ru-restore.md](routing-split-ru-restore.md) — только если снова нужен.

Проверка на сервере:

```bash
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
grep -E 'upstream|outboundTag' /usr/local/etc/xray/config.json
```

---

## Что не делает проект

- Не поднимает WireGuard автоматически
- Не хранит ключи WG в `.env` API
- Не привязывает релей к стране — только к IP/маршруту, который вы настроили

---

## Связанные документы

- [OPERATIONS.md](../OPERATIONS.md) — сервисы, в т.ч. `wg-quick@wg0` на узлах с WG
- [README.md](../../README.md) — быстрый старт
- [API_DOCUMENTATION.md](../../API_DOCUMENTATION.md) — REST API (egress не настраивается через API)
