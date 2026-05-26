# Эксплуатация: сервисы, логи, автозапуск, мониторинг

Сводка для продакшена на типичном хосте с путём проекта `/root/veil-v2ray`. Подставьте свой путь при другой установке.

## Автозапуск (systemd)

| Юнит | Назначение | Обычное состояние |
|------|------------|-------------------|
| `xray.service` | Xray (VLESS+Reality), `/usr/local/bin/xray run -config /usr/local/etc/xray/config.json` | `enabled` |
| `veil-xray-api.service` | FastAPI через uvicorn на `127.0.0.1:8000` | `enabled` |
| `nginx.service` | Reverse proxy и TLS для API | `enabled` |
| `netdata.service` | Мониторинг хоста (веб на `127.0.0.1:19999`) | `enabled` (если установлен) |

Проверка:

```bash
systemctl is-enabled xray veil-xray-api nginx netdata 2>/dev/null
systemctl status xray veil-xray-api nginx --no-pager
```

Юнит-файлы в репозитории (шаблоны): [scripts/veil-xray-api.service](../scripts/veil-xray-api.service), [scripts/xray.service](../scripts/xray.service). На сервере актуальные копии лежат в `/etc/systemd/system/`.

## Логирование

### API (Veil Xray)

| Что | Где |
|-----|-----|
| Файл приложения | `{PROJECT_ROOT}/logs/veil_xray_api.log` (по умолчанию `./logs/...` относительно рабочей директории сервиса) |
| Ротация в приложении | `RotatingFileHandler`: **10 MB** на файл, **5** архивов (`log_max_bytes`, `log_backup_count` в `.env` / [config/settings.py](../config/settings.py)) |
| Journal systemd | `StandardOutput=journal`, `StandardError=journal` — дублирование в журнал |

Просмотр:

```bash
tail -f /root/veil-v2ray/logs/veil_xray_api.log
journalctl -u veil-xray-api -f
```

Health-check API: `GET /` или `GET /health` (через Nginx — `GET /health` проксируется на корень приложения). **Не запускайте `pytest` на проде** — тесты пишут в отдельный лог (`LOG_FILE` в conftest) и используют временную БД.

**Logrotate для `veil_xray_api.log` не используется:** ротацию делает **Python** (`RotatingFileHandler`: текущий файл + `.1` … `.5`, по ~10 MB). Проверка: `ls -la /root/veil-v2ray/logs/veil_xray_api.log*`. Дублирующий `logrotate` для того же файла может мешать — не включайте без необходимости.

### Nginx (прокси к API)

| Что | Где (типично) |
|-----|----------------|
| Access | `/var/log/nginx/veil-xray-api-access.log` |
| Error | `/var/log/nginx/veil-xray-api-error.log` |

Ротация: системный `/etc/logrotate.d/nginx` (шаблон `/var/log/nginx/*.log`).

### Xray

Вывод процесса при работе через systemd попадает в **journal**:

```bash
journalctl -u xray -f
```

Уровень и путь при необходимости задаются в `/usr/local/etc/xray/config.json` (`log`).

### Мониторинг нагрузки (baseline)

| Что | Где |
|-----|-----|
| Метрики раз в минуту | `/var/log/veil-baseline.log` |
| Cron | root: `monitor-baseline.sh` из [scripts/load-protection/](../scripts/load-protection/) |

Ротация: `/etc/logrotate.d/veil-baseline` (еженедельно, 8 файлов).

### Проверка порогов SLO

| Что | Где |
|-----|-----|
| Пороги | `scripts/load-protection/slo-thresholds.env` |
| Скрипт (cron **каждые 5 мин**) | `scripts/load-protection/check-slo.sh` |
| Лог | `/var/log/veil-slo.log` (ротация: `/etc/logrotate.d/veil-slo`) |

Код выхода скрипта: `0` — ок, `1` — предупреждение, `2` — критично (удобно для внешнего алерта). Подробнее: [docs/operations/load-protection/01-slo-draft-this-host.md](operations/load-protection/01-slo-draft-this-host.md).

**Алерт при crit:** `scripts/load-protection/alert-slo-crit.sh` (cron каждые 5 мин, `logger -t veil-slo`). Настройка webhook: [09-slo-alerting.md](operations/load-protection/09-slo-alerting.md), шаблон `/etc/veil-slo-alert.env` из `slo-alert.env.example`.

## Production runbook

См. [docs/operations/PRODUCTION_RUNBOOK.md](operations/PRODUCTION_RUNBOOK.md) — запрет `pytest` на prod, осторожность с `sync-config` в пик.

## Git deploy (SSH)

[docs/operations/github-deploy.md](operations/github-deploy.md) — deploy key и `git pull` на production.

### Netdata

Логи пакета: `journalctl -u netdata`. Веб-интерфейс только на **localhost:19999** (см. `bind socket to IP` в `/etc/netdata/netdata.conf`).

## Резервное копирование БД

Скрипт: [scripts/backup_database.sh](../scripts/backup_database.sh) — кладёт сжатые копии в `{PROJECT_ROOT}/backups/`, удаляет файлы старше 30 дней.

**Расписание (root `crontab`):** ежедневно в **02:00**, лог: `{PROJECT_ROOT}/logs/backup.log`.

**Ротация `backup.log`:** `/etc/logrotate.d/veil-v2ray-backup-log` — раз в месяц, 12 архивов, `copytruncate`.

Тот же блок cron для другого хоста:

```cron
0 2 * * * /root/veil-v2ray/scripts/backup_database.sh >> /root/veil-v2ray/logs/backup.log 2>&1
```

Подробнее: [scripts/BACKUP_AND_LOGGING.md](../scripts/BACKUP_AND_LOGGING.md).

### Проверка на сервере

```bash
crontab -l | grep backup_database
ls -la /root/veil-v2ray/backups/
tail -20 /root/veil-v2ray/logs/backup.log
```

## Мониторинг и защита от перегрузки

- Базовая линия и Netdata: [docs/operations/load-protection/02-monitoring-baseline.md](operations/load-protection/02-monitoring-baseline.md)
- Остальные шаги: [docs/operations/load-protection/README.md](operations/load-protection/README.md)

## Быстрая проверка здоровья

```bash
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
curl -sS http://127.0.0.1:8000/
systemctl is-active xray veil-xray-api nginx
```

HTTPS API (если настроен): `curl -sS https://<ваш API хост>/`.
