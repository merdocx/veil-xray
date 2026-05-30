# Цепочка RU-мост → egress (обход ТСПУ)

> **Соглашение для этой инструкции:** IP, порты, SNI, `shortId`, домены бота и фрагменты JSON — **только примеры**.  
> На каждом хосте подставляйте свои значения из `.env`, `config.json` и API. Имена вроде `<BRIDGE_IP>` — плейсхолдеры, не копируйте буквально.

Для пользователей из России прямое подключение **клиент → зарубежный IP** часто приводит к «заморозке» TCP после 15–20 KB. Рекомендуемая схема:

```text
[Клиент в РФ] ──REALITY──► [VPS в РФ, мост] ──XHTTP/chain──► [veil-xray egress] ──► [Интернет]
                                    │
                                    └── geosite:category-ru → direct (без VPN)
```

## Роли узлов

| Узел | Где | Задача |
|------|-----|--------|
| **veilbot** | Отдельный VPS (например, ваш домен подписок) | Telegram, оплата, подписки; дергает API панели |
| **veil-xray (egress)** | Зарубежный VPS (например, EU/KZ) | Ключи в SQLite, hot-add в Xray, выход в интернет (direct / WG / SOCKS) |
| **RU-мост** | VPS в РФ (любой провайдер с РФ-IP) | Принимает клиентов; гонит нероссийский трафик на egress |

---

## Как это работает сейчас (без моста)

1. Пользователь покупает подписку в **veilbot**.
2. Бот вызывает **veil-xray API**: `POST /api/keys` → UUID попадает в Xray без перезапуска (`xray api adu`).
3. Пользователь получает ссылку подписки вида  
   `https://<ваш-домен-бота>/api/subscription/<token>?format=happ` (пример query-параметра: `format=happ`).
4. Бот запрашивает у панели  
   `GET .../subscription?profiles=auto&format=singbox_b64` — Happ получает профиль с DNS и TUN.
5. Трафик идёт **напрямую** на IP egress (порты inbounds задаются в **вашем** `config.json`, часто встречаются 443, 448, 446, 8445 — не норма для всех установок).

**veilbot не крутит VPN** — только управление и выдача конфигов.

---

## Как будет работать с мостом

1. Пользователь подключается к **IP моста в РФ** (в подписке — профиль `ru` / XHTTP, а не прямой inbound egress для конечных клиентов).
2. Мост расшифровывает VLESS+REALITY; российские сайты (`geosite:category-ru`, `geoip:ru`) можно отправлять **напрямую** в интернет РФ.
3. Остальной трафик мост пересылает на **egress** по внутреннему VLESS (часто **XHTTP** на участке мост→egress).
4. На egress в firewall имеет смысл разрешить chain-inbound **только с IP моста**; публичные inbounds для конечных пользователей РФ можно не публиковать.

---

## API veil-xray (эндпоинты)

| Запрос | Назначение |
|--------|------------|
| `GET /api/keys/{id}/link?profile=happ` | Профиль Happ/iOS (порт задаётся на сервере, часто 448) |
| `GET /api/keys/{id}/link?profile=ru` | Профиль с XHTTP для схемы с мостом |
| `GET /api/keys/{id}/subscription?profiles=ru&format=singbox_b64` | Подписка sing-box (когда мост готов) |
| `GET /api/keys/{id}/bot-bundle` | Сводка для veilbot (VLESS + sing-box b64) |

Создание/удаление ключей: hot-add (`adu` / `rmu`). Полный `sync-config` — только ручной repair, не после каждого ключа.

**veilbot:** при интеграции обычно используют `?format=happ` и не вызывают `sync-config` после `POST /keys` (конкретика — в коде/деплое бота).

---

## Инструкция: настройка RU-моста

### Шаг 0. Подготовка

- VPS в **РФ**, Linux, открыты **ваши** порты (пример: `443/tcp`, `8445/tcp` — возьмите из плана inbounds).
- Xray 25.x/26.x, `geoip.dat` / `geosite.dat` (путь как в вашей установке, часто `/usr/local/share/xray/`).
- Завести переменные (имена произвольные, смысл важен):

| Плейсхолдер | Откуда взять |
|-------------|----------------|
| `<BRIDGE_PUBLIC_IP>` | IP RU VPS |
| `<EGRESS_PUBLIC_IP>` | IP зарубежного veil-xray |
| `<EGRESS_API_URL>` | URL API панели, например `https://<host>:8443/api` |
| `<USER_UUID>` | `POST /api/keys` или бот |
| `<CHAIN_PORT>` | Свободный порт на egress только для моста |
| `<REALITY_*>` | `init_reality_keys.py` / `.env` на соответствующем узле |

На **egress** заведите **отдельный** inbound для chain (свой порт и `shortIds`), не смешивайте с публичным inbound для Happ.

### Шаг 1. Egress — ограничить прямой вход на chain

Пример UFW (подставьте свои IP и порт):

```bash
BRIDGE_IP=<BRIDGE_PUBLIC_IP>      # пример: 203.0.113.10
CHAIN_PORT=<CHAIN_PORT>            # пример: 8446

ufw allow from "$BRIDGE_IP" to any port "$CHAIN_PORT" proto tcp
```

В `config.json` egress — inbound с тегом на ваш выбор (пример имени: `vless-reality-bridge`): порт `<CHAIN_PORT>`, свои `shortIds` и SNI, согласованные с leg мост→egress. С интернета на этот порт — только мост.

После правки inbounds: `xray -test` и перезапуск/reload по [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md).

### Шаг 2. Мост — REALITY inbound для клиентов

Фрагмент **примерной** конфигурации (`/usr/local/etc/xray/config.json` на RU VPS):

```json
{
  "inbounds": [
    {
      "tag": "vless-reality-ru-client",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [{ "id": "<USER_UUID>", "flow": "" }],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "dest": "<RU_COVER_DEST>",
          "serverNames": ["<RU_SNI_1>", "<RU_SNI_2>"],
          "privateKey": "<BRIDGE_REALITY_PRIVATE_KEY>",
          "shortIds": ["<BRIDGE_SHORT_ID>"]
        }
      },
      "sniffing": { "enabled": true, "destOverride": ["http", "tls"] }
    }
  ],
  "outbounds": [
    { "tag": "direct", "protocol": "freedom" },
    {
      "tag": "chain-egress",
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "<EGRESS_PUBLIC_IP>",
          "port": "<CHAIN_PORT>",
          "users": [{ "id": "<USER_UUID>", "encryption": "none", "flow": "" }]
        }]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": {
          "serverName": "<EGRESS_SNI>",
          "publicKey": "<EGRESS_REALITY_PUBLIC_KEY>",
          "shortId": "<EGRESS_SHORT_ID>",
          "fingerprint": "<FP>"
        },
        "xhttpSettings": { "path": "<REALITY_XHTTP_PATH>", "mode": "stream-one" }
      }
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      { "type": "field", "domain": ["geosite:category-ru"], "outboundTag": "direct" },
      { "type": "field", "ip": ["geoip:ru"], "outboundTag": "direct" },
      { "type": "field", "network": "tcp,udp", "outboundTag": "chain-egress" }
    ]
  }
}
```

**Примеры значений (не копировать вслепую):**

| Поле | Пример смысла |
|------|----------------|
| `<RU_COVER_DEST>` | `www.example.ru:443` — легитимный RU HTTPS-сайт под TLS 1.3 |
| `<RU_SNI_*>` | те же домены, что в `serverNames` |
| `<EGRESS_SNI>` | SNI egress inbound (как в `.env`: `REALITY_SNI`) |
| `<REALITY_XHTTP_PATH>` | из `.env` egress: `REALITY_XHTTP_PATH` |
| `<FP>` | `ios`, `chrome`, `firefox` — по политике клиента |
| `port` inbound клиентов | любой открытый порт, не обязательно 443 |

Проверка:

```bash
xray -test -config /usr/local/etc/xray/config.json
systemctl enable --now xray
```

### Шаг 3. DNS на мосте

DNS задаётся в **клиентском** профиле (sing-box/Happ) или отдельным inbound на мосте — как решите в своём шаблоне. На egress для RU-профиля логика может быть в `build_ru_singbox_subscription_config` (см. код `api/utils.py`).

### Шаг 4. Выдача пользователям

- Когда мост готов: `GET /api/keys/{id}/link?profile=ru`, подписка `profiles=ru&format=singbox_b64`.
- В veilbot при необходимости — отдельный `format` / смена `profiles=auto` (зависит от вашего деплоя бота).
- **Happ:** для полного туннеля обычно нужен режим **Global** (не Rule) и удалённый DNS — это настройки **клиента**, не константы сервера.

### Шаг 5. Проверка

1. С клиента в РФ — зарубежный сайт: в логах **моста** outbound `chain-egress`, на **egress** — accepted с source `<BRIDGE_PUBLIC_IP>`.
2. Сайт из `geosite:category-ru` — на мосте outbound `direct` (проверьте на **вашем** тестовом RU-домене).
3. С произвольного IP на `<EGRESS_PUBLIC_IP>:<CHAIN_PORT>` — соединение **отклонено** firewall (если правило настроено).

---

## Чеклист внедрения

- [ ] Egress: inbound для моста + firewall только с `<BRIDGE_PUBLIC_IP>`
- [ ] Мост: REALITY с RU cover SNI, routing RU → direct
- [ ] Leg мост→egress: согласованы UUID, shortId, XHTTP path с egress
- [ ] API/бот: выдача `profile=ru` / `profiles=ru` для целевой аудитории
- [ ] Мониторинг: внешний probe из РФ (порог трафика — на ваше усмотрение)

См. также: [egress-modes.md](egress-modes.md), [routing-split-ru-restore.md](routing-split-ru-restore.md), [SERVER_PROFILE.md](SERVER_PROFILE.md).
