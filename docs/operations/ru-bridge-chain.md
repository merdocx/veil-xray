# Топологии veil-xray: база и опции (мост, WG, релей)

> **Соглашение:** IP, порты, SNI, домены и JSON — **примеры**. Плейсхолдеры `<…>` подставляйте из своего `.env`, `config.json` и API.

**По умолчанию** достаточно **одного** сервера veil-xray: клиент → VLESS+REALITY → интернет (`direct`).  
**Front relay**, **egress-релей** (SOCKS/WG) и **RU-мост** — **необязательные** усиления.

---

## Варианты развёртывания

| Вариант | Путь трафика | Когда имеет смысл |
|---------|--------------|-------------------|
| **A — базовый** (по умолчанию) | Клиент → veil-xray → интернет | Стандартная выдача ключей; egress = IP VPN-сервера |
| **E — front relay** | Клиент → **релей (L4)** → veil-xray → интернет | Стабильный вход через ближний VPS; REALITY на backend |
| **B — SOCKS egress** | Клиент → veil-xray → SOCKS-релей → интернет | Выход с другого IP без WG |
| **C — WG egress** | Клиент → veil-xray → WG → релей → интернет | Выход с IP релея через туннель |
| **D — RU-мост** | Клиент → мост (Xray) → veil-xray → интернет | Freeze ТСПУ; прикладной chain, не L4 |

**E** — релей **перед** VPN ([relay-front-topology.md](relay-front-topology.md)).  
**B / C** — релей **после** VPN ([egress-modes.md](egress-modes.md)).  
**D** — отдельный входной Xray на мосте, не nginx stream.

Варианты независимы (кроме здравого смысла: E+D обычно не смешивают).

```text
A:  [Клиент] ──REALITY──► [veil-xray] ──direct──► [Интернет]

E:  [Клиент] ──TCP──► [front relay] ──TCP──► [veil-xray] ──► [Интернет]

B:  [Клиент] ──► [veil-xray] ──SOCKS──► [egress-релей] ──► [Интернет]

C:  [Клиент] ──► [veil-xray] ──WG──► [egress-релей] ──► [Интернет]

D:  [Клиент] ──► [мост / bridge VPS] ──chain──► [veil-xray] ──► [Интернет]
```

Подробнее: **E** — [relay-front-topology.md](relay-front-topology.md); **B/C** — [egress-modes.md](egress-modes.md).

---

## Вариант A — базовая схема (без моста, без WG)

### Роли

| Узел | Задача |
|------|--------|
| **veilbot** | Оплата, подписки, вызов API панели (отдельный VPS) |
| **veil-xray** | Xray inbounds, API, SQLite, hot-add ключей |

### Как работает

1. Пользователь в **veilbot** → `POST /api/keys` на veil-xray (UUID в Xray без restart).
2. Подписка (пример URL):  
   `https://<домен-бота>/api/subscription/<token>?format=happ`
3. Бот запрашивает у панели (пример):  
   `GET .../subscription?profiles=auto&format=singbox_b64`
4. Клиент (Happ и др.) подключается **напрямую** к IP/DNS **veil-xray**.
5. Исходящий трафик — outbound **`direct`** в `config.json` (шаблон: [xray/config.example.json](../../xray/config.example.json) без релея или с routing только на `direct`).

**Не требуется:** второй VPS моста, WireGuard, SOCKS, отдельный chain-inbound.

### API (базовые эндпоинты)

| Запрос | Назначение |
|--------|------------|
| `GET /api/keys/{id}/link?profile=happ` | Профиль для Happ/iOS |
| `GET /api/keys/{id}/link?profile=primary` / `stable` | Другие inbounds по вашему `config.json` |
| `GET /api/keys/{id}/bot-bundle` | Сводка для veilbot |
| `GET .../subscription?profiles=auto&format=singbox_b64` | Подписка sing-box |

`profile=ru` и `profiles=ru` — **только для варианта D** (мост), в базе не нужны.

### Чеклист базы

- [ ] Xray + veil-xray-api на одном узле
- [ ] veilbot → API URL с `/api` и Bearer-токеном
- [ ] Подписка с DNS (пример: `?format=happ`)
- [ ] Outbound `direct` (или ваш осознанный выбор B/C)

---

## Вариант E — опционально: front relay (L4)

Клиент подключается к **IP/DNS релея**; nginx stream (или DNAT) пробрасывает TCP на veil-xray. API и ключи — только на **backend**; в `.env` задаётся `DOMAIN=<адрес релея>`.

- Runbook: [relay-front-topology.md](relay-front-topology.md)
- Шаблон nginx: [scripts/relay/nginx-stream-l4.conf.example](../../scripts/relay/nginx-stream-l4.conf.example)

**Не требуется** для варианта A. **Не путать** с B/C (egress после VPN) и D (Xray-мост).

---

## Вариант B — опционально: SOCKS-релей (egress)

Дополнение к A: в `config.json` outbound `upstream` (SOCKS) и routing на него.  
API по-прежнему только управляет **clients** inbounds.

- Шаблон: `xray/config.example.json` (замените `<RELAY_HOST>` на IP релея).
- Проверка: `scripts/verify-egress-via-relay.sh` (пример env в [egress-modes.md](egress-modes.md)).

**Не требуется** для работы veil-xray в варианте A.

---

## Вариант C — опционально: WireGuard-релей

Дополнение к A: на **том же** входном узле `wg-quick@wg0` + outbound с `sockopt.mark` (пример в [egress-modes.md](egress-modes.md)).

- Юнит `wg-quick@wg0` включают **только** на хостах с настроенным `/etc/wireguard/wg0.conf`.
- На узле без WG сервис можно **не** ставить / держать disabled.

**Не требуется** для работы veil-xray в варианте A.

---

## Вариант D — опционально: RU-мост → egress

Отдельный VPS (мост) принимает клиентов; veil-xray на egress остаётся точкой выхода.  
Имеет смысл при нестабильных длинных сессиях «клиент → зарубежный IP напрямую», а не как обязательный шаг установки.

### Когда рассматривать

- База (A) уже работает, но у части клиентов нестабильны длинные сессии на IP egress напрямую.
- Готовы администрировать **второй** сервер и согласовать chain с egress.

### Кратко по потоку

1. Клиент → **IP моста** (профиль `ru` / XHTTP в подписке).
2. Мост: при желании RU-трафик → `direct`, остальное → chain на `<EGRESS_PUBLIC_IP>`.
3. Egress: отдельный inbound только для моста (firewall с `<BRIDGE_PUBLIC_IP>`).

### API (дополнение к A, только при включённом D)

| Запрос | Назначение |
|--------|------------|
| `GET /api/keys/{id}/link?profile=ru` | Ссылка под XHTTP / мост |
| `GET .../subscription?profiles=ru&format=singbox_b64` | Подписка под мост |

### D — шаг 0. Подготовка (пример плейсхолдеров)

| Плейсхолдер | Откуда |
|-------------|--------|
| `<BRIDGE_PUBLIC_IP>` | IP bridge VPS |
| `<EGRESS_PUBLIC_IP>` | IP veil-xray |
| `<CHAIN_PORT>` | Свободный порт на egress для моста |
| `<USER_UUID>` | API / бот |
| `<REALITY_*>` | `init_reality_keys.py` / `.env` |

### D — шаг 1. Egress: chain-inbound (пример UFW)

```bash
BRIDGE_IP=<BRIDGE_PUBLIC_IP>
CHAIN_PORT=<CHAIN_PORT>

ufw allow from "$BRIDGE_IP" to any port "$CHAIN_PORT" proto tcp
```

Inbound (пример тега `vless-reality-bridge`) — в **вашем** `config.json` на egress.

### D — шаг 2. Мост: пример фрагмента `config.json`

```json
{
  "inbounds": [{
    "tag": "vless-reality-ru-client",
    "port": "<CLIENT_PORT>",
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
        "serverNames": ["<RU_SNI>"],
        "privateKey": "<BRIDGE_REALITY_PRIVATE_KEY>",
        "shortIds": ["<BRIDGE_SHORT_ID>"]
      }
    }
  }],
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
    "rules": [
      { "type": "field", "domain": ["geosite:category-ru"], "outboundTag": "direct" },
      { "type": "field", "ip": ["geoip:ru"], "outboundTag": "direct" },
      { "type": "field", "network": "tcp,udp", "outboundTag": "chain-egress" }
    ]
  }
}
```

Правила `geosite:category-ru` → `direct` на мосте **опциональны** (можно весь трафик гнать на egress).

### D — проверка (примеры)

1. Зарубежный сайт: на мосте `chain-egress`, на egress source = `<BRIDGE_PUBLIC_IP>`.
2. С чужого IP на `<EGRESS_PUBLIC_IP>:<CHAIN_PORT>` — отклонено firewall (если настроено).

### Чеклист D (только если включили мост)

- [ ] Egress: chain-inbound + firewall с IP моста
- [ ] Мост: REALITY + chain на egress
- [ ] Бот/API: `profile=ru` / `profiles=ru` для целевой аудитории

---

## veilbot (все варианты)

Бот не поднимает VPN. Типичная интеграция с **вариантом A**:

- `?format=happ` в URL подписки
- после `POST /keys` не вызывать `sync-config`
- `GET .../bot-bundle` или `subscription?profiles=auto&format=singbox_b64`

Для **D** — дополнительно выдача `profiles=ru`, когда мост в проде.

---

## Связанные документы

- [relay-front-topology.md](relay-front-topology.md) — вариант E (L4 front relay)
- [egress-modes.md](egress-modes.md) — варианты B и C (SOCKS / WG egress)
- [routing-split-ru-restore.md](routing-split-ru-restore.md) — опциональный split RU на **одном** узле (не то же самое, что мост D)
- [OPERATIONS.md](../OPERATIONS.md) — systemd, деплой
- [SERVER_PROFILE.md](SERVER_PROFILE.md) — пример **конкретного** prod-хоста (не универсальный чеклист)
