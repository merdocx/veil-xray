# Резервное копирование и логирование

Пути ниже даны для стандартной установки в **`/root/veil-v2ray`**. При другом каталоге замените префикс.

## Резервное копирование базы данных

### Скрипт

- **Файл:** `scripts/backup_database.sh` (в каталоге проекта)
- **База:** `{PROJECT_ROOT}/database/veil_xray.db`
- **Архивы:** `{PROJECT_ROOT}/backups/`, имя `veil_xray_YYYYMMDD_HHMMSS.db.gz`
- **Хранение:** 30 дней (настраивается в скрипте, `RETENTION_DAYS`)

### Ручной запуск

```bash
/root/veil-v2ray/scripts/backup_database.sh
```

### Расписание (cron)

На прод-сервере проекта в **root crontab** добавлено ежедневное задание **02:00** с логом `logs/backup.log`. Для нового хоста добавьте вручную:

```cron
0 2 * * * /root/veil-v2ray/scripts/backup_database.sh >> /root/veil-v2ray/logs/backup.log 2>&1
```

Каталог `logs/` создаётся при первом запуске API или вручную: `mkdir -p /root/veil-v2ray/logs`.

### Ротация `backup.log`

На прод-сервере: **`/etc/logrotate.d/veil-v2ray-backup-log`** (ежемесячно, 12 архивов). Шаблон в репозитории: [logrotate/veil-v2ray-backup-log.example](logrotate/veil-v2ray-backup-log.example).

### Восстановление из бэкапа

```bash
sudo systemctl stop veil-xray-api
gunzip -c /root/veil-v2ray/backups/veil_xray_YYYYMMDD_HHMMSS.db.gz > /tmp/restore.db
sqlite3 /root/veil-v2ray/database/veil_xray.db ".restore '/tmp/restore.db'"
sudo systemctl start veil-xray-api
```

---

## Логирование API

### Файл

По умолчанию: **`{PROJECT_ROOT}/logs/veil_xray_api.log`**

Задаётся в `.env` (`LOG_FILE`) и в [config/settings.py](../config/settings.py).

### Ротация без logrotate

Приложение использует **`RotatingFileHandler`**:

- `LOG_MAX_BYTES` (по умолчанию **10 MB**)
- `LOG_BACKUP_COUNT` (по умолчанию **5** файлов)

Итого до ~60 MB на диске в каталоге `logs/`. Отдельный **`/etc/logrotate.d/veil-xray-api` не обязателен** и при дублировании с внутренней ротацией может мешать.

### Journald

Юнит `veil-xray-api.service` перенаправляет stdout/stderr в журнал:

```bash
journalctl -u veil-xray-api -f
```

### Уровень логирования

В `.env`:

```env
LOG_LEVEL=INFO
LOG_FILE=./logs/veil_xray_api.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

После изменения: `sudo systemctl restart veil-xray-api`.

---

## Логи Nginx (если используется)

Обычно (имена могут отличаться в вашем `sites-enabled`):

- `/var/log/nginx/veil-xray-api-access.log`
- `/var/log/nginx/veil-xray-api-error.log`

Ротация: системный пакет `nginx` через `/etc/logrotate.d/nginx` (`/var/log/nginx/*.log`).

---

## Логи Xray

Конфиг: `/usr/local/etc/xray/config.json` (`log`). При запуске через `systemctl`:

```bash
journalctl -u xray -f
```

---

## Мониторинг baseline

См. [docs/operations/load-protection/02-monitoring-baseline.md](../docs/operations/load-protection/02-monitoring-baseline.md) — файл `/var/log/veil-baseline.log` и cron.

---

## Устранение неполадок

### Бэкап не создаётся

- Права: `chmod +x /root/veil-v2ray/scripts/backup_database.sh`
- Наличие `sqlite3`: `which sqlite3`
- Лог cron (если настроен): `tail /root/veil-v2ray/logs/backup.log`

### Логи API не пишутся

- `mkdir -p /root/veil-v2ray/logs` и права на запись пользователя сервиса
- Проверка `.env` и перезапуск `veil-xray-api`


## Ротация ops-логов (рекомендация)

Файлы `/var/log/veil-slo.log`, `/var/log/veil-baseline.log` растут от cron. Пример `/etc/logrotate.d/veil-ops`:

```
/var/log/veil-slo.log /var/log/veil-baseline.log /var/log/veil-xray-tcp-restart.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
```
