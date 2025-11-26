# Резервное копирование и логирование

## Резервное копирование базы данных

### Автоматическое резервное копирование

Резервное копирование базы данных настроено через cron задачу и выполняется автоматически каждый день в 2:00 ночи.

**Расположение:**
- Скрипт: `/root/scripts/backup_database.sh`
- Директория бэкапов: `/root/backups/`
- Логи бэкапов: `/root/logs/backup.log`

**Параметры:**
- Хранение бэкапов: 30 дней
- Автоматическое сжатие: включено (gzip)
- Формат имени файла: `veil_xray_YYYYMMDD_HHMMSS.db.gz`

### Ручное создание бэкапа

```bash
/root/scripts/backup_database.sh
```

### Восстановление из бэкапа

```bash
# Остановите API сервис
sudo systemctl stop veil-xray-api

# Распакуйте бэкап (если сжат)
gunzip /root/backups/veil_xray_YYYYMMDD_HHMMSS.db.gz

# Восстановите базу данных
sqlite3 /root/database/veil_xray.db ".restore '/root/backups/veil_xray_YYYYMMDD_HHMMSS.db'"

# Запустите API сервис
sudo systemctl start veil-xray-api
```

### Настройка расписания бэкапов

Для изменения расписания отредактируйте cron задачу:

```bash
crontab -e
```

Текущее расписание: `0 2 * * *` (каждый день в 2:00)

Примеры:
- `0 */6 * * *` - каждые 6 часов
- `0 0 * * 0` - каждое воскресенье в полночь
- `0 2 * * 1-5` - каждый рабочий день в 2:00

## Логирование

### Файловое логирование

Логи приложения записываются в файл: `/root/logs/veil_xray_api.log`

**Настройки:**
- Максимальный размер файла: 10MB
- Количество ротированных файлов: 5
- Формат: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Уровень логирования: INFO (настраивается через `.env`)

### Ротация логов

Ротация логов настроена через logrotate и выполняется автоматически.

**Конфигурация:** `/etc/logrotate.d/veil-xray-api`

**Параметры:**
- Ротация: ежедневно
- Хранение: 30 дней
- Сжатие: включено (с задержкой)
- Права доступа: 0644 root root

### Просмотр логов

**Файловые логи:**
```bash
tail -f /root/logs/veil_xray_api.log
```

**Systemd journal:**
```bash
sudo journalctl -u veil-xray-api -f
```

**Последние записи:**
```bash
sudo journalctl -u veil-xray-api -n 100
```

**Логи за определенный период:**
```bash
sudo journalctl -u veil-xray-api --since "2025-11-26 00:00:00" --until "2025-11-26 23:59:59"
```

### Настройка уровня логирования

Отредактируйте файл `.env`:

```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=./logs/veil_xray_api.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5
```

После изменения перезапустите сервис:

```bash
sudo systemctl restart veil-xray-api
```

## Мониторинг

### Проверка статуса бэкапов

```bash
# Список бэкапов
ls -lh /root/backups/

# Размер директории бэкапов
du -sh /root/backups/

# Последние записи в логе бэкапов
tail -n 20 /root/logs/backup.log
```

### Проверка ротации логов

```bash
# Тестовая ротация (без изменений)
sudo logrotate -d /etc/logrotate.d/veil-xray-api

# Принудительная ротация
sudo logrotate -f /etc/logrotate.d/veil-xray-api
```

### Проверка размера логов

```bash
# Размер текущего лог-файла
du -h /root/logs/veil_xray_api.log

# Размер всех лог-файлов
du -sh /root/logs/
```

## Устранение неполадок

### Бэкап не создается

1. Проверьте права доступа:
```bash
ls -l /root/scripts/backup_database.sh
chmod +x /root/scripts/backup_database.sh
```

2. Проверьте наличие sqlite3:
```bash
which sqlite3
```

3. Проверьте логи:
```bash
tail -n 50 /root/logs/backup.log
```

### Логи не записываются

1. Проверьте права на директорию:
```bash
ls -ld /root/logs/
mkdir -p /root/logs
chmod 755 /root/logs
```

2. Проверьте конфигурацию в `.env`

3. Перезапустите сервис:
```bash
sudo systemctl restart veil-xray-api
```

### Ротация не работает

1. Проверьте конфигурацию:
```bash
cat /etc/logrotate.d/veil-xray-api
```

2. Проверьте статус logrotate:
```bash
sudo logrotate -d /etc/logrotate.d/veil-xray-api
```

3. Проверьте cron задачу logrotate:
```bash
grep logrotate /etc/cron.daily/logrotate
```

