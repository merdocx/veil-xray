# Требования к серверу и базовые настройки

Документ для **входного VPN-узла** veil-xray (VLESS+Reality + API). Runtime: `/opt/veil-xray`, git: `/root/veil-xray`.

См. также: [FIRST_DEPLOY.md](FIRST_DEPLOY.md) (пошаговый чеклист), [OPERATIONS.md](../OPERATIONS.md) (эксплуатация), [SERVER_PROFILE.md](SERVER_PROFILE.md) (пример эталонного prod).

---

## 1. Железо и ОС

| Параметр | Минимум | Рекомендуется (prod) |
|----------|---------|----------------------|
| vCPU | 1 | **2** |
| RAM | **2 GiB** | **4 GiB** (~100 активных ключей) |
| Диск | 20 GiB | 40+ GiB (логи, бэкапы SQLite) |
| ОС | Ubuntu 22.04+ | **Ubuntu 24.04 LTS** |
| Сеть | Публичный IPv4 | IPv4 + при необходимости IPv6 |

Порты (UFW): **22**, **80** (API), **443** (VLESS), **446–448**, **8445**, **2085** — см. [FIRST_DEPLOY.md](FIRST_DEPLOY.md).

---

## 2. Пакеты

```bash
sudo apt-get update
sudo apt-get install -y \
  git curl ca-certificates \
  python3 python3-pip python3-venv \
  nginx certbot python3-certbot-nginx \
  dnsutils sqlite3 rsync
```

Xray-core: [официальная установка](https://github.com/XTLS/Xray-install) → `/usr/local/bin/xray`, config `/usr/local/etc/xray/config.json`.

---

## 3. Базовые настройки узла

### 3.1 Sysctl (TCP)

```bash
sudo cp /opt/veil-xray/scripts/load-protection/sysctl-tcp-tuning.conf /etc/sysctl.d/99-veil-tcp.conf
sudo sysctl --system
```

Файл уже включает `ip_forward` (IPv4/IPv6) для TUN/маршрутизации; для outbound `direct` это обычно не критично.

### 3.2 Xray

- Policy: `scripts/load-protection/apply-policy-recommended.sh` (handshake 4, connIdle 300, bufferSize 256).
- Лимит памяти: `/etc/systemd/system/xray.service.d/override.conf` → `MemoryMax=1G` (шаблон в `scripts/load-protection/systemd/`).
- Egress без релея: outbound **`direct`** в `config.json` (см. [egress-modes.md](egress-modes.md)).

### 3.3 Reality

- Ключи: `scripts/init_reality_keys.py` + `scripts/ops/apply-reality-keys-to-xray-config.sh`.
- `REALITY_DEST` должен **отвечать с VPS** (`curl` на `https://www.cloudflare.com` и т.п.).
- Публичный `pbk` в ссылках = `Password (PublicKey)` от `xray x25519 -i "$REALITY_PRIVATE_KEY"`.

### 3.4 API / veilbot

- `.env` в `/opt/veil-xray/.env` (`chmod 600`).
- API только `127.0.0.1:8000`; снаружи — Nginx `:80`.
- Лимит ключей на узле — в **veilbot** (`servers.max_keys`), не в панели.

---

## 4. Мониторинг загрузки сервера

Устанавливается через `scripts/ops/install-ops-cron.sh` (вызывается из `deploy-prod.sh`).

| Задача | Расписание | Скрипт | Лог |
|--------|------------|--------|-----|
| Baseline (метрики каждую минуту) | `* * * * *` | `load-protection/monitor-baseline.sh` | `/var/log/veil-baseline.log` |
| SLO (пороги warn/crit) | `*/5 * * * *` | `load-protection/check-slo.sh` | `/var/log/veil-slo.log` |
| Алерт crit SLO | `*/5` | `alert-slo-crit.sh` | syslog |
| Алерт TCP FIN-WAIT | `*/5` | `alert-tcp-pressure.sh` | syslog |
| Авторестарт Xray при TCP crit | `*/5` | `ops/auto-restart-xray-on-tcp.sh` | `/var/log/veil-xray-tcp-restart.log` |
| Отчёт baseline | 06:05 daily / понедельник 7d | `baseline-report.sh` | `/var/log/veil-baseline-report.log` |

Пороги SLO: `scripts/load-protection/slo-thresholds.env` (на **2 GiB RAM** — профиль `2g`, см. ниже).

**Быстрый статус на сервере:**

```bash
/opt/veil-xray/scripts/ops/server-load-status.sh
```

**Ручная проверка:**

```bash
tail -1 /var/log/veil-baseline.log
tail -1 /var/log/veil-slo.log
/opt/veil-xray/scripts/load-protection/check-slo.sh; echo "exit=$?"
# 0=ok, 1=warn, 2=crit
```

**Профиль порогов по RAM:**

```bash
# 2 GiB VPS (типичный Fornex 2GB)
sudo /opt/veil-xray/scripts/ops/apply-slo-profile.sh 2g

# 4 GiB prod (эталон SERVER_PROFILE)
sudo /opt/veil-xray/scripts/ops/apply-slo-profile.sh 4g
```

Опционально: webhook для crit — `/etc/veil-slo-alert.env` из `scripts/load-protection/slo-alert.env.example` ([09-slo-alerting.md](load-protection/09-slo-alerting.md)).

Netdata на prod обычно **выключен** (`systemctl disable netdata`) — достаточно baseline + SLO.

---

## 5. Автозапуск (systemd)

После деплоя должны быть **enabled** и **active**:

| Юнит | Назначение |
|------|------------|
| `xray.service` | VPN (VLESS+Reality) |
| `veil-xray-api.service` | REST API (`127.0.0.1:8000`) |
| `nginx.service` | Reverse proxy для API |

```bash
sudo systemctl enable xray veil-xray-api nginx
sudo systemctl is-active xray veil-xray-api nginx
```

Юниты: `scripts/veil-xray-api.service`, `scripts/xray.service`.  
`deploy-prod.sh` устанавливает unit API и выполняет `systemctl enable veil-xray-api`.

WireGuard (`wg-quick@wg0`) — только при egress через WG ([egress-modes.md](egress-modes.md)).

---

## 6. Ротация логов

| Лог | Механизм | Конфиг |
|-----|----------|--------|
| API `veil_xray_api.log` | Python `RotatingFileHandler` **10 MB × 5** | `.env`: `log_max_bytes`, `log_backup_count` |
| API (доп.) | logrotate weekly | `/etc/logrotate.d/veil-xray-api-log` |
| Ops: SLO, baseline, restart | logrotate weekly | `/etc/logrotate.d/veil-ops` |
| `backup.log` | logrotate monthly | `/etc/logrotate.d/veil-xray-backup-log` |
| Nginx | системный пакет | `/etc/logrotate.d/nginx` |
| Xray | journald | `journalctl -u xray` |

Установка logrotate (из репозитория, через `deploy-prod.sh`):

- `scripts/load-protection/logrotate-veil-ops.example` → `/etc/logrotate.d/veil-ops`
- `scripts/logrotate/veil-xray-backup-log.example` → `/etc/logrotate.d/veil-xray-backup-log`
- `scripts/logrotate/veil-xray-api-log.example` → `/etc/logrotate.d/veil-xray-api-log`

Проверка:

```bash
ls -la /etc/logrotate.d/veil-*
sudo logrotate -d /etc/logrotate.d/veil-ops
```

---

## 7. Cron и бэкапы

Файл **`/etc/cron.d/veil-xray`** (не дублировать в `crontab -e`):

```bash
sudo /opt/veil-xray/scripts/ops/install-ops-cron.sh
cat /etc/cron.d/veil-xray
```

Бэкап SQLite: **02:00** → `/opt/veil-xray/backups/`, лог `/opt/veil-xray/logs/backup.log` (нужен `sqlite3`).

---

## 8. Чеклист после установки

```bash
/root/veil-xray/scripts/ops/deploy-prod.sh
sudo /opt/veil-xray/scripts/ops/apply-slo-profile.sh auto
/opt/veil-xray/scripts/ops/server-load-status.sh

systemctl is-enabled xray veil-xray-api nginx
test -f /etc/cron.d/veil-xray && test -f /etc/logrotate.d/veil-ops
curl -sS http://127.0.0.1:8000/health
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
```
