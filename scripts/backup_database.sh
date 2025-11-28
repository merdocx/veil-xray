#!/bin/bash
# Скрипт резервного копирования базы данных Veil Xray

set -euo pipefail

# Настройки
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/database/veil_xray.db"
BACKUP_DIR="$PROJECT_ROOT/backups"
RETENTION_DAYS=30  # Хранить бэкапы 30 дней

# Создаем директорию для бэкапов если её нет
mkdir -p "$BACKUP_DIR"

# Проверяем существование базы данных
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database file not found: $DB_PATH" >&2
    exit 1
fi

# Генерируем имя файла бэкапа с датой и временем
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/veil_xray_${TIMESTAMP}.db"

# Создаем резервную копию
echo "[$(date +"%Y-%m-%d %H:%M:%S")] Creating backup: $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Проверяем успешность создания бэкапа
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Backup created successfully: $BACKUP_FILE (size: $BACKUP_SIZE)"
    
    # Сжимаем бэкап для экономии места
    if command -v gzip >/dev/null 2>&1; then
        gzip -f "$BACKUP_FILE"
        COMPRESSED_FILE="${BACKUP_FILE}.gz"
        COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
        echo "[$(date +"%Y-%m-%d %H:%M:%S")] Backup compressed: $COMPRESSED_FILE (size: $COMPRESSED_SIZE)"
    fi
else
    echo "ERROR: Backup file was not created" >&2
    exit 1
fi

# Удаляем старые бэкапы (старше RETENTION_DAYS дней)
echo "[$(date +"%Y-%m-%d %H:%M:%S")] Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "veil_xray_*.db*" -type f -mtime +$RETENTION_DAYS -delete
DELETED_COUNT=$(find "$BACKUP_DIR" -name "veil_xray_*.db*" -type f | wc -l)
echo "[$(date +"%Y-%m-%d %H:%M:%S")] Cleanup completed. Remaining backups: $DELETED_COUNT"

exit 0




