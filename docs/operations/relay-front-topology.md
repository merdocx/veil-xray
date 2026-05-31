# Вариант E — front relay (пользователь → релей → VPN → интернет)

> **Соглашение:** IP, порты и домены — **примеры**. Плейсхолдеры `<…>` подставляйте из своего деплоя.

**Front relay** — отдельный VPS **без** veil-xray API: он только **прозрачно пробрасывает TCP** (L4) на входной узел veil-xray. Клиент в VLESS-ссылке указывает **адрес релея**; VLESS+REALITY терминируется на **VPN-сервере** за релеем.

Это **не** то же самое, что:

| Схема | Где релей | Что делает релей |
|--------|-----------|------------------|
| **E (этот документ)** | **Перед** VPN | L4 forward (nginx stream / DNAT), без Xray |
| **B / C** [egress-modes.md](egress-modes.md) | **После** VPN | Egress: SOCKS или WireGuard, исходящий IP релея |
| **D** [ru-bridge-chain.md](ru-bridge-chain.md) | Мост **вместо** прямого входа | Xray на мосте, chain на egress (прикладной уровень) |

---

## Схема

```text
E:  [Клиент] ──TCP──► [front relay] ──TCP──► [veil-xray] ──direct/SOCKS/WG──► [Интернет]
         │                    │                      │
    VLESS в ссылке      nginx stream           REALITY + API + ключи
    = IP/DNS релея      (прокси портов)        = backend VPN
```

- **Релей:** ближе к пользователю (тот же ДЦ или регион), стабильный маршрут до VPN-backend.
- **VPN-сервер:** veil-xray, SQLite, `veil-xray-api`, hot-add ключей — **без изменений** в API.
- **Egress** на VPN-сервере — по-прежнему A / B / C ([egress-modes.md](egress-modes.md)).

---

## Роли серверов

| Узел | Софт | Обязательно |
|------|------|-------------|
| **Front relay** | nginx `stream` (или nftables DNAT) | Проброс портов VPN → `<VPN_BACKEND_IP>` |
| **VPN backend** | Xray + veil-xray-api | Обычный [FIRST_DEPLOY.md](FIRST_DEPLOY.md) |

На релее **не** ставят: veil-xray API, SQLite, `init_reality_keys` для панели.

---

## Порты для проброса

Пробрасывайте **те же TCP-порты**, что слушает Xray на backend (см. [xray/config.example.json](../../xray/config.example.json)):

| Порт | Назначение |
|------|------------|
| 443 | VLESS REALITY (основной) |
| 446 | VLESS alt |
| 447 | SNI-B |
| 448 | Happ (без Vision) |
| 8445 | XHTTP |
| 2085 | Trojan REALITY |

API (`8000` / Nginx `443` для `api.`) на релей **не** проксируют — бот ходит на VPN-сервер или отдельный поддомен.

---

## Шаг 1. VPN backend (veil-xray)

1. Разверните veil-xray по [FIRST_DEPLOY.md](FIRST_DEPLOY.md) (вариант **A**).
2. UFW на backend: разрешите с **IP front relay** вход на порты 443, 446–448, 8445, 2085:

```bash
RELAY_IP=<FRONT_RELAY_PUBLIC_IP>
for p in 443 446 447 448 8445 2085; do
  ufw allow from "$RELAY_IP" to any port "$p" proto tcp
done
```

3. Запишите `<VPN_BACKEND_PUBLIC_IP>`.

---

## Шаг 2. Front relay (nginx stream)

1. Установите nginx с модулем `stream`.
2. Скопируйте шаблон [scripts/relay/nginx-stream-l4.conf.example](../../scripts/relay/nginx-stream-l4.conf.example) в `/etc/nginx/stream.d/veil-front.conf`.
3. Замените `<VPN_BACKEND_IP>` на IP backend.
4. Проверка и запуск:

```bash
nginx -t && systemctl reload nginx
```

5. UFW на релее: откройте 443, 446–448, 8445, 2085 для клиентов (и 22 для админа).

Шаблон и комментарии: [scripts/relay/README.md](../../scripts/relay/README.md).

---

## Шаг 3. Ссылки и подписки (DOMAIN)

API строит VLESS-ссылки с полем `address` из **`DOMAIN`** в `.env` на **VPN-сервере**.

Для варианта E укажите адрес **front relay** (DNS или IP), на который смотрит клиент:

```env
# На VPN backend (/opt/veil-xray/.env)
DOMAIN=<front-relay.example.com>
# или DOMAIN=<FRONT_RELAY_PUBLIC_IP>
```

Перезапуск API после смены:

```bash
sudo systemctl restart veil-xray-api
```

Перегенерация ссылок для существующих ключей (если нужно): `scripts/regenerate_links.py`.

**Важно:** REALITY-ключи и `short_id` остаются на **backend**; меняется только **хост** в URI, не криптография.

---

## Проверка

С **клиентской** машины (не с релея):

```bash
# TCP до релея
nc -zv <FRONT_RELAY_IP> 443

# После импорта ключа — трафик через VPN; IP выхода = backend или egress (B/C), не IP релея
```

С **релея** до backend:

```bash
nc -zv <VPN_BACKEND_IP> 443
```

На backend в логах Xray должны появляться подключения с source IP = `<FRONT_RELAY_IP>` (если смотрите access/debug).

---

## Комбинации

| Комбинация | Смысл |
|------------|--------|
| **E + A** | Релей спереди, egress `direct` с backend |
| **E + B/C** | Релей спереди, egress через SOCKS/WG с backend |
| **E + D** | Обычно **не** смешивают: D уже даёт вход через bridge VPS; E — другой паттерн (чистый L4) |

---

## Ограничения

- Релей видит **зашифрованный** TLS/Reality-трафик, но не расшифровывает его (в отличие от моста D с Xray).
- Нужна **синхронная** схема портов relay ↔ backend.
- При смене backend IP обновите nginx на реле и firewall на backend.
- API veil-xray **не** управляет релеем — только документация и шаблоны в `scripts/relay/`.

---

## Связанные документы

- [ru-bridge-chain.md](ru-bridge-chain.md) — сводная таблица A–E
- [egress-modes.md](egress-modes.md) — B/C (релей **после** VPN)
- [API_DOCUMENTATION.md](../../API_DOCUMENTATION.md) — выдача ссылок (`DOMAIN`)
