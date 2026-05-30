# Цепочка RU-мост → egress (обход ТСПУ)

Для пользователей из России прямое подключение **клиент → зарубежный IP** часто приводит к «заморозке» TCP после 15–20 KB. Рекомендуемая схема:

```text
[Клиент в РФ] ──REALITY──► [VPS в РФ, мост] ──XHTTP/chain──► [veil-xray egress] ──► [Интернет]
                                    │
                                    └── geosite:category-ru → direct (без VPN)
```

## Роли узлов

| Узел | Где | Задача |
|------|-----|--------|
| **veilbot** | Отдельный сервер (`veil-bird.ru`) | Telegram, оплата, подписки; дергает API панели |
| **veil-xray (egress)** | Зарубежный VPS (например KZ) | Ключи в SQLite, hot-add в Xray, выход в интернет (direct / WG / SOCKS) |
| **RU-мост** | VPS в РФ (Yandex Cloud, VK Cloud, Selectel…) | Принимает клиентов с «российским» SNI; гонит остальной трафик на egress |

---

## Как это работает сейчас (без моста)

1. Пользователь покупает подписку в **veilbot**.
2. Бот вызывает **veil-xray API**: `POST /api/keys` → UUID попадает в Xray без перезапуска (`xray api adu`).
3. Пользователь получает ссылку подписки `https://veil-bird.ru/api/subscription/{token}?format=happ`.
4. Бот запрашивает у панели `GET .../subscription?profiles=auto&format=singbox_b64` — Happ получает профиль с DNS и TUN.
5. Трафик идёт **напрямую** на зарубежный IP (порты 443/448/446/8445 на egress).

**veilbot не крутит VPN** — только управление и выдача конфигов.

---

## Как будет работать с мостом

1. Пользователь подключается к **IP моста в РФ** (в подписке — профиль `ru` / XHTTP, не зарубежный :448).
2. Мост расшифровывает VLESS+REALITY; российские сайты (`geosite:category-ru`, `geoip:ru`) отправляет **напрямую** в интернет РФ.
3. Остальной трафик мост пересылает на **egress** (текущий veil-xray) по внутреннему VLESS (лучше **XHTTP** на leg мост→egress).
4. Egress выходит в интернет со своего IP (как сейчас). На egress в firewall разрешён вход **только с IP моста** на порты chain — конечные пользователи на :443/:448 egress не ходят.

Плюсы: для ТСПУ сессия «клиент↔мост» выглядит как обычный HTTPS внутри РФ; freeze на зарубежный IP срабатывает реже.

---

## API veil-xray (уже есть)

| Запрос | Назначение |
|--------|------------|
| `GET /api/keys/{id}/link?profile=happ` | :448 для Happ/iOS |
| `GET /api/keys/{id}/link?profile=ru` | XHTTP для РФ-профиля |
| `GET /api/keys/{id}/subscription?profiles=ru&format=singbox_b64` | Подписка sing-box под мост |
| `GET /api/keys/{id}/bot-bundle` | VLESS + sing-box b64 для veilbot |

Создание/удаление ключей: hot-add (`adu` / `rmu`), **без** `systemctl restart xray` после каждого ключа.

**veilbot** (уже на проде): подписка `?format=happ`, после `POST /keys` не вызывать `sync-config`.

---

## Инструкция: настройка RU-моста

### Шаг 0. Подготовка

- VPS в **РФ**, Ubuntu 22.04+, открыты нужные порты (например `443`, `8445` для XHTTP).
- Установить Xray 26.x, `geoip.dat` / `geosite.dat` в `/usr/local/share/xray/`.
- Записать: `BRIDGE_PUBLIC_IP`, `EGRESS_PUBLIC_IP`, `EGRESS_API` (veil-xray), общий **UUID пользователя** (создаётся на egress через API/бот).

На **egress** сгенерировать отдельный inbound для chain-only (отдельный порт, отдельный shortId) — не смешивать с публичным :448 для Happ.

### Шаг 1. Egress — ограничить прямой вход

На зарубежном veil-xray:

```bash
# Пример: разрешить chain-порт только с IP моста
BRIDGE_IP=1.2.3.4
CHAIN_PORT=8446   # отдельный inbound под мост

ufw allow from $BRIDGE_IP to any port $CHAIN_PORT proto tcp
# Опционально: убрать из публичной подписки прямые :443/:448 для RU-аудитории
```

В `config.json` egress добавьте inbound `vless-reality-bridge` (порт `CHAIN_PORT`, свой `shortIds`, SNI как на мосте→egress leg). Пользователей с интернета на этот порт **не** пускать — только мост.

Перезагрузка только при смене inbounds: `xray -test && systemctl reload xray` или safe-restart по runbook.

### Шаг 2. Мост — REALITY inbound для клиентов

На RU VPS создайте `/usr/local/etc/xray/config.json` (фрагмент):

```json
{
  "inbounds": [
    {
      "tag": "vless-reality-ru-client",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [{ "id": "USER_UUID_FROM_EGRESS_API", "flow": "" }],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "dest": "www.yandex.ru:443",
          "serverNames": ["yandex.ru", "www.yandex.ru"],
          "privateKey": "BRIDGE_REALITY_PRIVATE_KEY",
          "shortIds": ["7bb45050"]
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
          "address": "EGRESS_PUBLIC_IP",
          "port": 8446,
          "users": [{ "id": "USER_UUID_FROM_EGRESS_API", "encryption": "none", "flow": "" }]
        }]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": {
          "serverName": "www.microsoft.com",
          "publicKey": "EGRESS_REALITY_PUBLIC_KEY",
          "shortId": "7bb45050",
          "fingerprint": "chrome"
        },
        "xhttpSettings": { "path": "/your-xhttp-path", "mode": "stream-one" }
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

Подставьте реальные ключи Reality, path XHTTP из `.env` egress (`REALITY_XHTTP_PATH`), UUID из API.

Проверка:

```bash
xray -test -config /usr/local/etc/xray/config.json
systemctl enable --now xray
```

### Шаг 3. DNS на мосте

Клиенты должны резолвить DNS **через туннель** или через мост. Для sing-box/Happ используйте профиль с `remote` DNS (как в `build_ru_singbox_subscription_config` на egress). На мосте при необходимости добавьте inbound DNS или полагайтесь на клиентский профиль.

### Шаг 4. Выдача пользователям

- До полного перехода: `GET /api/keys/{id}/link?profile=ru` и подписка `profiles=ru`.
- В veilbot позже: отдельный `format=ru` или смена `profiles=auto` на панели, когда мост в проде.
- **Happ:** режим **Global**, не Rule; обновить подписку после смены профиля.

### Шаг 5. Проверка

1. С телефона в РФ: ping через VPN на зарубежный сайт — в логах **моста** должен быть `chain-egress`, на **egress** — accepted с source = `BRIDGE_IP`.
2. Открыть `yandex.ru` — трафик должен идти `direct` с моста (в логах outbound `direct`).
3. С чужого IP на `EGRESS:8446` — соединение **отклонено** firewall.

---

## Чеклист внедрения

- [ ] Egress: inbound для моста + UFW только с `BRIDGE_IP`
- [ ] Мост: REALITY с **российским** SNI, routing RU → direct
- [ ] Leg мост→egress: XHTTP + REALITY, те же UUID/shortId что в API
- [ ] API/бот: выдача `profile=ru` / `profiles=ru` вместо прямого :448 для RU-аудитории
- [ ] Мониторинг: probe из РФ >25 KB на мост (отдельная задача)

См. также: [egress-modes.md](egress-modes.md), [routing-split-ru-restore.md](routing-split-ru-restore.md), [SERVER_PROFILE.md](SERVER_PROFILE.md).
