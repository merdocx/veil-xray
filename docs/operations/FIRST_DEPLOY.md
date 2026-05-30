# Первый деплой на чистый VPS (чеклист)

Краткий чеклист после установки по [README.md](../../README.md). Runtime: `/opt/veil-xray`, git: `/root/veil-xray`.

## 1. Пакеты и firewall

```bash
sudo apt-get install -y git curl ca-certificates python3 python3-pip python3-venv \
  nginx certbot python3-certbot-nginx dnsutils sqlite3 rsync
```

UFW (минимум для VPN + API):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp      # API (Nginx)
sudo ufw allow 443/tcp     # VLESS Reality
sudo ufw allow 446/tcp     # alt
sudo ufw allow 447/tcp     # SNI-B
sudo ufw allow 448/tcp     # Happ (без Vision)
sudo ufw allow 8445/tcp    # XHTTP
sudo ufw allow 2085/tcp    # Trojan Reality
sudo ufw enable
```

## 2. Ключи Reality

Генерация (рекомендуется — совпадает с API):

```bash
cd /opt/veil-xray && source venv/bin/activate
python scripts/init_reality_keys.py
```

Подстановка в Xray **безопасно** (сначала `_B`, потом основной placeholder):

```bash
scripts/ops/apply-reality-keys-to-xray-config.sh /opt/veil-xray/.env
```

Проверка пары ключей:

```bash
PRIV=$(grep REALITY_PRIVATE_KEY= /opt/veil-xray/.env | cut -d= -f2)
/usr/local/bin/xray x25519 -i "$PRIV"   # Password (PublicKey) == REALITY_PUBLIC_KEY в .env
```

## 3. Reality `dest` / SNI

`REALITY_DEST` должен **отвечать с сервера** (иначе в логах: `authentication failed`):

```bash
curl -sS --max-time 5 -o /dev/null -w "%{http_code}\n" https://www.cloudflare.com
```

Если `www.microsoft.com` недоступен — в `.env` и во всех `realitySettings` в `config.json`:

- `REALITY_SNI=cloudflare.com`
- `REALITY_DEST=www.cloudflare.com:443`

## 4. Egress на одном узле

В `config.json` для клиентского трафика — outbound **`direct`**, не `upstream` (SOCKS-релей), если релея нет. См. [egress-modes.md](egress-modes.md).

## 5. Systemd и деплой

```bash
cp /opt/veil-xray/scripts/veil-xray-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now veil-xray-api xray nginx
/root/veil-xray/scripts/ops/deploy-prod.sh
```

## 6. veilbot

| Параметр | Пример |
|----------|--------|
| API URL | `http://IP_СЕРВЕРА` (Nginx :80 → API :8000) |
| Подписка | **Happ** (`bot-bundle`, `profiles=auto`) — одна ссылка :448 |
| После ключа | **не** вызывать `sync-config` |

## 7. Smoke

```bash
curl -sS http://127.0.0.1:8000/health
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
systemctl is-active xray veil-xray-api nginx
```

Создание/удаление ключа через API **не требует** `systemctl restart xray` (hot-add `adu` / `rmu`).
