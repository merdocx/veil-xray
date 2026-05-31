# Профиль production-сервера (эталон настроек)

**Актуально на:** 2026-05-30 · **Версия veil-xray:** 1.3.20 · **Хост:** v3091624 (VDSina)

Этот документ — **единый справочник** лимитов и примеров конфигурации для текущего узла. При смене тарифа, порогов или policy обновляйте его вместе с `scripts/load-protection/slo-thresholds.env` и [08-capacity-decision.md](load-protection/08-capacity-decision.md).

---

## 1. Железо и ОС

| Параметр | Значение |
|----------|----------|
| vCPU | **2** |
| RAM | **4 GiB** (~3.8 GiB видимой, MemAvailable типично **2.5–2.9 GiB**) |
| Диск | 100 GiB |
| Трафик (лимит хостера) | 32 TiB / период |
| Публичный IP (вход VPN) | `193.124.65.182` |
| Активных ключей | ~**100** |
| Путь проекта | `/root/veil-xray` |

**История:** до 2026-05-26 — 1 vCPU / 2 GiB (пороги SLO в CHANGELOG; актуальные — в [01-slo-template.md](load-protection/01-slo-template.md)).

---

## 2. Сервисы (systemd)

| Юнит | Состояние на prod | Примечание |
|------|-------------------|------------|
| `xray.service` | enabled, active | VLESS+Reality :443 |
| `veil-xray-api.service` | enabled, active | `127.0.0.1:8000` |
| `nginx.service` | enabled, active | TLS → API |
| `wg-quick@wg0` | enabled, active | Egress через релей (WG) |
| `netdata.service` | **disabled** | Освобождение RAM; опционально |

### Лимит памяти Xray

Файл: `/etc/systemd/system/xray.service.d/override.conf`

```ini
[Service]
MemoryMax=1G
Restart=on-failure
RestartSec=3
```

Шаблон в репозитории: [scripts/load-protection/systemd/xray.service.d-override.conf.example](../../scripts/load-protection/systemd/xray.service.d-override.conf.example).

API (`veil-xray-api`): **без** `MemoryMax` (infinity).

---

## 3. Приложение (`.env` на prod)

Пример значений (секреты подставьте свои; **не коммитьте** реальный `.env`):

```env
API_HOST=127.0.0.1
API_PORT=8000
API_ENABLE_DOCS=false
API_ALLOWED_IPS=127.0.0.1,<admin-ip-1>,<admin-ip-2>

DATABASE_URL=sqlite:///./database/veil_xray.db

XRAY_CONFIG_PATH=/usr/local/etc/xray/config.json
XRAY_API_HOST=127.0.0.1
XRAY_API_PORT=10085

REALITY_SERVER_NAME=193.124.65.182
REALITY_SNI=microsoft.com
REALITY_FINGERPRINT=chrome
REALITY_DEST=www.microsoft.com:443
REALITY_PORT=443
REALITY_COMMON_SHORT_ID=f6de7940
REALITY_FLOW=xtls-rprx-vision

ENABLE_BACKGROUND_TRAFFIC_SYNC=true
BACKGROUND_TRAFFIC_SYNC_INTERVAL_S=600
BACKGROUND_TRAFFIC_SYNC_BATCH_SIZE=50
TRAFFIC_CACHE_TTL_S=3600

LOG_FILE=./logs/veil_xray_api.log
LOG_LEVEL=INFO
```

Полный шаблон: [.env.example](../../.env.example).

**Пик MSK (08:00–23:59):** `POST /api/system/xray/sync-config` → **503**, если не задано `VEIL_ALLOW_SYNC_IN_PEAK=1` на сервисе API.

---

## 4. Xray (`/usr/local/etc/xray/config.json`)

### Policy (уровень `0`, prod)

| Поле | Значение | Комментарий |
|------|----------|-------------|
| `handshake` | **`4`** | сек (Xray docs / best practice) |
| `connIdle` | **`300`** | 5 мин idle (Xray default; было 1200) |
| `uplinkOnly` / `downlinkOnly` | **`2`** / **`5`** | закрытие half-close (Xray docs) |
| `bufferSize` | **`256`** | KiB на соединение (было 512 на prod) |
| `statsUserUplink/Downlink` | `true` | статистика по email |

Применение policy: `scripts/load-protection/apply-policy-recommended.sh` + рестарт Xray.

### Маршрутизация (схема)

Эталон **этого** входного хоста; IP релея — пример деплоя, не требование к стране. Общие режимы: [egress-modes.md](egress-modes.md).

- Inbound: `vless-reality` :443  
- Исходящий трафик клиентов: outbound **`wg-egress`** (`freedom` + `sockopt.mark` **119** / `0x77`)  
- Таблица `wg77`: default via `10.77.0.1 dev wg0`  
- WireGuard peer (пример): **77.238.243.136:51820**  
- SOCKS `upstream` (тот же хост :1080) — запасной путь; на этом узле основной egress — **WG**

### Reality (пример ссылки для клиента)

```
vless://<uuid>@193.124.65.182:443?type=tcp&security=reality&sni=microsoft.com&fp=chrome&pbk=<REALITY_PUBLIC_KEY>&sid=f6de7940&spx=/&flow=xtls-rprx-vision
```

---

## 5. Sysctl (TCP)

Файл на хосте: `/etc/sysctl.d/99-veil-tcp.conf`  
Шаблон: [scripts/load-protection/sysctl-tcp-tuning.conf](../../scripts/load-protection/sysctl-tcp-tuning.conf)

| Параметр | Значение |
|----------|----------|
| `net.ipv4.tcp_max_syn_backlog` | 8192 |
| `net.core.somaxconn` | 8192 |
| `net.core.netdev_max_backlog` | 16384 |
| `net.ipv4.tcp_fin_timeout` | 30 |
| `net.ipv4.tcp_max_orphans` | **16384** |
| `net.ipv4.tcp_keepalive_time` | 600 |
| `vm.swappiness` | 10 |

Установка: `cp …/sysctl-tcp-tuning.conf /etc/sysctl.d/99-veil-tcp.conf && sysctl --system`

---

## 6. SLO и пороги

Источник: [scripts/load-protection/slo-thresholds.env](../../scripts/load-protection/slo-thresholds.env)  
Проверка: `check-slo.sh` каждые **5 мин** → `/var/log/veil-slo.log`

| Метрика | Warn | Crit | Пояснение |
|---------|------|------|-----------|
| `load1 / ncpu` | **1.0** | **3.0** | 2 vCPU |
| `MemAvailable` | **&lt; 1.5 GiB** | **&lt; 1 GiB** | KiB: 1536000 / 1048576 |
| RSS xray | **&gt; 512 MiB** | **&gt; 768 MiB** | при MemoryMax=1G |
| TCP ESTAB :443 | **2500** | **4000** | `ss` established |
| FIN-WAIT :443 | **500** | **800** | забивание TCP |
| FIN-WAIT / ESTAB ×100 | **150%** | **250%** | только если ESTAB ≥ 100 |

Коды выхода `check-slo.sh`: `0` ok, `1` warn, `2` crit.

### Алерты

| Скрипт | Условие |
|--------|---------|
| `alert-slo-crit.sh` | любой crit в SLO |
| `alert-tcp-pressure.sh` | crit + `fin_wait` в reasons |

Конфиг: `/etc/veil-slo-alert.env` из `slo-alert.env.example` (webhook, dedup **30 мин**).

### Условный рестарт Xray по TCP

`scripts/ops/auto-restart-xray-on-tcp.sh`:

- `FIN_WAIT_443` &gt; **800** (`TCP_RESTART_FIN_WAIT_CRIT`) три проверки подряд (cron */5)  
- не чаще **1 раз в час**  
- лог: `/var/log/veil-xray-tcp-restart.log`

---

## 7. Cron (`/etc/cron.d/veil-xray`)

Установка: `scripts/ops/install-ops-cron.sh`

| Расписание | Скрипт | Лог |
|------------|--------|-----|
| `* * * * *` | `monitor-baseline.sh` | `/var/log/veil-baseline.log` |
| `*/5 * * * *` | `check-slo.sh` | `/var/log/veil-slo.log` |
| `*/5 * * * *` | `alert-slo-crit.sh` | syslog |
| `*/5 * * * *` | `alert-tcp-pressure.sh` | syslog |
| `*/5 * * * *` | `auto-restart-xray-on-tcp.sh` | `/var/log/veil-xray-tcp-restart.log` |
| `0 4 * * *` | `cron-nightly-xray-restart.sh` | `/var/log/veil-xray-restart.log` |
| `5 6 * * *` | `baseline-report.sh 1` | `/var/log/veil-baseline-report.log` |
| `10 6 * * 1` | `baseline-report.sh 7` | то же |
| `0 2 * * *` | `backup_database.sh` | `logs/backup.log` |

Ротация ops-логов: `/etc/logrotate.d/veil-ops` из `logrotate-veil-ops.example`.

---

## 8. Логи (быстрый указатель)

| Лог | Назначение |
|-----|------------|
| `logs/veil_xray_api.log` | API (ротация 10 MB × 5 в приложении) |
| `journalctl -u xray` | accepted/rejected VLESS |
| `/var/log/veil-slo.log` | SLO |
| `/var/log/veil-baseline.log` | минутные метрики |
| `/var/log/nginx/veil-xray-api-*.log` | Nginx |

---

## 9. Быстрая проверка

```bash
nproc && free -h | head -2
systemctl is-active xray veil-xray-api nginx wg-quick@wg0
systemctl show xray -p MemoryMax --value
/root/veil-xray/scripts/load-protection/check-slo.sh; echo "slo_exit=$?"
tail -1 /var/log/veil-slo.log
ss -tan sport = :443 | awk '{print $1}' | sort | uniq -c | sort -rn | head -5
ping -c2 10.77.0.1
curl -sS http://127.0.0.1:8000/health
```

---

## 10. Связанные документы

| Документ | Содержание |
|----------|------------|
| [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md) | Запреты, пик MSK, деплой |
| [OPERATIONS.md](../OPERATIONS.md) | Сводка эксплуатации |
| [load-protection/08-capacity-decision.md](load-protection/08-capacity-decision.md) | Решение по ёмкости |
| [load-protection/03-xray-policy.md](load-protection/03-xray-policy.md) | Поля policy |
| [github-deploy.md](github-deploy.md) | Git на prod |
