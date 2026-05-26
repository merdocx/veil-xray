# Эксплуатация: сервисы, логи, автозапуск, мониторинг

Сводка для продакшена. Путь проекта: `/root/veil-v2ray`.

**Эталон всех лимитов и примеров `.env` / SLO / sysctl:** [operations/SERVER_PROFILE.md](operations/SERVER_PROFILE.md) (2 vCPU, 4 GiB, v1.3.15).

## Автозапуск (systemd)

| Юнит | Назначение | Prod |
|------|------------|------|
| `xray.service` | Xray VLESS+Reality, config `/usr/local/etc/xray/config.json` | enabled |
| `veil-xray-api.service` | FastAPI `127.0.0.1:8000` | enabled |
| `nginx.service` | TLS reverse proxy для API | enabled |
| `wg-quick@wg0` | WireGuard egress (NL) | enabled |
| `netdata.service` | Мониторинг (localhost:19999) | **disabled** на prod |

```bash
systemctl is-enabled xray veil-xray-api nginx wg-quick@wg0
systemctl status xray veil-xray-api nginx --no-pager
```

Юниты в репозитории: [scripts/veil-xray-api.service](../scripts/veil-xray-api.service), [scripts/xray.service](../scripts/xray.service).  
Лимит Xray: `MemoryMax=1G` — см. [SERVER_PROFILE.md](operations/SERVER_PROFILE.md).

## Cron (ops)

Расписание в **`/etc/cron.d/veil-xray`** (не дублировать в root crontab). Установка:

```bash
/root/veil-v2ray/scripts/ops/install-ops-cron.sh
```

Задачи: baseline (1 мин), SLO + алерты (5 мин), ночной рестарт Xray (04:00), отчёты baseline, бэкап БД (02:00). Таблица — в [SERVER_PROFILE.md](operations/SERVER_PROFILE.md).

## Логирование

### API

| Что | Где |
|-----|-----|
| Файл | `/root/veil-v2ray/logs/veil_xray_api.log` |
| Ротация | Python: **10 MB** × **5** (`log_max_bytes`, `log_backup_count`) |
| Journal | `journalctl -u veil-xray-api -f` |

**Не запускайте `pytest` на prod** — см. [PRODUCTION_RUNBOOK.md](operations/PRODUCTION_RUNBOOK.md).

### Xray

```bash
journalctl -u xray -f
```

### Мониторинг нагрузки

| Лог | Скрипт | Частота |
|-----|--------|---------|
| `/var/log/veil-baseline.log` | `monitor-baseline.sh` | 1 мин |
| `/var/log/veil-slo.log` | `check-slo.sh` | 5 мин |
| `/var/log/veil-baseline-report.log` | `baseline-report.sh` | 06:05 / пн |
| `/var/log/veil-xray-restart.log` | ночной рестарт | 04:00 |
| `/var/log/veil-xray-tcp-restart.log` | auto-restart TCP | при срабатывании |

Ротация ops: `/etc/logrotate.d/veil-ops` (шаблон `scripts/load-protection/logrotate-veil-ops.example`).

### Nginx

`/var/log/nginx/veil-xray-api-access.log`, `veil-xray-api-error.log` — системный logrotate.

## SLO и алерты

Пороги: [scripts/load-protection/slo-thresholds.env](../scripts/load-protection/slo-thresholds.env) (под **2 CPU / 4 GiB**).

| Скрипт | Назначение |
|--------|------------|
| `check-slo.sh` | exit 0/1/2 → warn/crit |
| `alert-slo-crit.sh` | syslog + webhook при crit |
| `alert-tcp-pressure.sh` | crit по FIN-WAIT |

Настройка webhook: [operations/load-protection/09-slo-alerting.md](operations/load-protection/09-slo-alerting.md).

Черновик порогов для **старого** 1 vCPU / 2 GiB (история): [01-slo-draft-this-host.md](operations/load-protection/01-slo-draft-this-host.md).

## Production runbook

[operations/PRODUCTION_RUNBOOK.md](operations/PRODUCTION_RUNBOOK.md)

## Git deploy

[operations/github-deploy.md](operations/github-deploy.md)

## Резервное копирование БД

[scripts/backup_database.sh](../scripts/backup_database.sh) → `backups/`, cron **02:00**. Подробнее: [scripts/BACKUP_AND_LOGGING.md](../scripts/BACKUP_AND_LOGGING.md).

## Netdata (опционально)

На prod **отключён** для экономии RAM. Включение: `systemctl enable --now netdata`, доступ `ssh -L 19999:127.0.0.1:19999 root@<host>`. См. [02-monitoring-baseline.md](operations/load-protection/02-monitoring-baseline.md).

## Мониторинг и защита от перегрузки

- [operations/load-protection/README.md](operations/load-protection/README.md) — индекс шагов
- [operations/load-protection/08-capacity-decision.md](operations/load-protection/08-capacity-decision.md) — решение по ёмкости

## Быстрая проверка здоровья

```bash
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
curl -sS http://127.0.0.1:8000/health
systemctl is-active xray veil-xray-api nginx wg-quick@wg0
tail -1 /var/log/veil-slo.log
```
