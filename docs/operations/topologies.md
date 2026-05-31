# Топологии veil-xray: база и опции

> **Соглашение:** IP, порты, SNI, домены и JSON — **примеры**. Плейсхолдеры `<…>` подставляйте из своего `.env`, `config.json` и API.

**По умолчанию** достаточно **одного** сервера veil-xray: клиент → VLESS+REALITY → интернет (`direct`).  
**Front relay** и **egress-релей** (SOCKS/WG) — **необязательные** усиления.

---

## Варианты развёртывания

| Вариант | Путь трафика | Когда имеет смысл |
|---------|--------------|-------------------|
| **A — базовый** (по умолчанию) | Клиент → veil-xray → интернет | Стандартная выдача ключей; egress = IP VPN-сервера |
| **E — front relay** | Клиент → **релей (L4)** → veil-xray → интернет | Стабильный вход через ближний VPS; REALITY на backend |
| **B — SOCKS egress** | Клиент → veil-xray → SOCKS-релей → интернет | Выход с другого IP без WG |
| **C — WG egress** | Клиент → veil-xray → WG → релей → интернет | Выход с IP релея через туннель |

**E** — релей **перед** VPN ([relay-front-topology.md](relay-front-topology.md)).  
**B / C** — релей **после** VPN ([egress-modes.md](egress-modes.md)).

Варианты независимы (можно A только; A+E; A+B; A+C; A+B+C и т.д.).

```text
A:  [Клиент] ──REALITY──► [veil-xray] ──direct──► [Интернет]

E:  [Клиент] ──TCP──► [front relay] ──TCP──► [veil-xray] ──► [Интернет]

B:  [Клиент] ──► [veil-xray] ──SOCKS──► [egress-релей] ──► [Интернет]

C:  [Клиент] ──► [veil-xray] ──WG──► [egress-релей] ──► [Интернет]
```

Подробнее: **E** — [relay-front-topology.md](relay-front-topology.md); **B/C** — [egress-modes.md](egress-modes.md).

---

## Вариант A — базовая схема

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
4. Клиент (Happ и др.) подключается к `DOMAIN` из `.env` панели.
5. Исходящий трафик — outbound **`direct`** в `config.json` (или B/C по вашему выбору).

### API (базовые эндпоинты)

| Запрос | Назначение |
|--------|------------|
| `GET /api/keys/{id}/link?profile=happ` | Профиль для Happ/iOS |
| `GET /api/keys/{id}/link?profile=primary` | TCP :443 + Vision |
| `GET /api/keys/{id}/bot-bundle` | Сводка для veilbot |
| `GET .../subscription?profiles=auto&format=singbox_b64` | sing-box с urltest (см. ниже) |

### Чеклист базы

- [ ] Xray + veil-xray-api на одном узле
- [ ] veilbot → API URL с `/api` и Bearer-токеном
- [ ] Outbound `direct` (или осознанный выбор B/C)

---

## Вариант E — front relay (L4)

Клиент подключается к **IP/DNS релея**; nginx stream пробрасывает TCP на veil-xray. В `.env`: `DOMAIN=<адрес релея>`.

- [relay-front-topology.md](relay-front-topology.md)
- [scripts/relay/nginx-stream-l4.conf.example](../../scripts/relay/nginx-stream-l4.conf.example)

---

## Вариант B — SOCKS egress

Дополнение к A: outbound `upstream` (SOCKS) в `config.json`. Шаблон: [xray/config.example.json](../../xray/config.example.json).

---

## Вариант C — WireGuard egress

Дополнение к A: `wg-quick@wg0` + outbound с `sockopt.mark` — [egress-modes.md](egress-modes.md).

---

## Автовыбор: где что происходит

| Уровень | Кто делает | Как |
|---------|------------|-----|
| **Между разными VPS** (`<server-a>`, `<server-b>`, …) | **veilbot** (управляющий сервер) | Одна подписка бота; клиент или бот выбирает узел |
| **На одном veil-xray** (порты 448 / 447 при SNI-B) | **Эта панель** | sing-box JSON с **`urltest`** в `subscription?profiles=auto&format=singbox_b64` |

Veil-xray **не** переключает пользователя между разными панелями — только конфиг **своего** хоста.

---

## veilbot

- `?format=happ` в URL подписки пользователя
- после `POST /keys` не вызывать `sync-config`
- `GET .../bot-bundle` или `subscription?profiles=auto&format=singbox_b64`

---

## Связанные документы

- [relay-front-topology.md](relay-front-topology.md) — вариант E
- [egress-modes.md](egress-modes.md) — варианты B и C
- [routing-split-ru-restore.md](routing-split-ru-restore.md) — опциональный geo-split на **одном** узле (routing в Xray, не отдельный мост)
- [OPERATIONS.md](../OPERATIONS.md) — systemd, деплой
- [API_DOCUMENTATION.md](../../API_DOCUMENTATION.md) — REST API, UX, автовыбор (veilbot vs панель)
