#!/usr/bin/env python3
"""Скрипт для отображения текущего трафика ключей"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from api.database import SessionLocal, Key, TrafficStats
from datetime import datetime


def format_bytes(bytes_value: int) -> str:
    """Форматирование байтов в читаемый формат"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def format_timestamp(timestamp: int) -> str:
    """Форматирование timestamp в читаемую дату"""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    return "Never"


def show_traffic():
    """Отображение трафика всех ключей"""
    db: Session = SessionLocal()
    
    try:
        # Получаем все активные ключи с их статистикой трафика
        keys = db.query(Key).filter(Key.is_active == 1).order_by(Key.created_at.desc()).all()
        
        if not keys:
            print("📊 В базе данных нет активных ключей")
            return
        
        print("=" * 100)
        print(f"{'ID':<5} {'UUID':<38} {'Short ID':<10} {'Name':<20} {'Upload':<15} {'Download':<15} {'Total':<15} {'Last Updated':<20}")
        print("=" * 100)
        
        total_upload = 0
        total_download = 0
        
        for key in keys:
            # Получаем последнюю статистику трафика для ключа
            traffic = db.query(TrafficStats).filter(
                TrafficStats.key_id == key.id
            ).order_by(TrafficStats.updated_at.desc()).first()
            
            if traffic:
                upload = traffic.upload
                download = traffic.download
                total = upload + download
                last_updated = traffic.updated_at
            else:
                upload = 0
                download = 0
                total = 0
                last_updated = None
            
            total_upload += upload
            total_download += download
            
            name = key.name or "-"
            uuid_short = key.uuid[:8] + "..." if len(key.uuid) > 8 else key.uuid
            
            print(f"{key.id:<5} {uuid_short:<38} {key.short_id:<10} {name:<20} "
                  f"{format_bytes(upload):<15} {format_bytes(download):<15} "
                  f"{format_bytes(total):<15} {format_timestamp(last_updated):<20}")
        
        print("=" * 100)
        total_all = total_upload + total_download
        print(f"{'ИТОГО:':<5} {'':<38} {'':<10} {'':<20} "
              f"{format_bytes(total_upload):<15} {format_bytes(total_download):<15} "
              f"{format_bytes(total_all):<15} {'':<20}")
        print("=" * 100)
        print(f"\n📈 Всего активных ключей: {len(keys)}")
        print(f"📤 Общий upload: {format_bytes(total_upload)}")
        print(f"📥 Общий download: {format_bytes(total_download)}")
        print(f"📊 Общий трафик: {format_bytes(total_all)}")
        
    except Exception as e:
        print(f"❌ Ошибка при получении данных: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    show_traffic()

