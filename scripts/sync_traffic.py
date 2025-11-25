#!/usr/bin/env python3
"""Скрипт для синхронизации статистики трафика из Xray в базу данных"""
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from api.database import SessionLocal, Key, TrafficStats
from api.xray_client import XrayClient
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def sync_traffic_stats():
    """Синхронизация статистики трафика для всех активных ключей"""
    db: Session = SessionLocal()
    xray_client = XrayClient()
    
    try:
        # Получаем все активные ключи
        keys = db.query(Key).filter(Key.is_active == 1).all()
        
        if not keys:
            logger.info("No active keys found")
            return
        
        logger.info(f"Syncing traffic stats for {len(keys)} keys...")
        
        updated_count = 0
        error_count = 0
        
        for key in keys:
            try:
                # Формируем email для запроса статистики
                email = f"user_{key.id}_{key.uuid[:8]}"
                
                # Получаем статистику из Xray
                xray_stats = await xray_client.get_user_stats(email)
                
                upload = xray_stats.get("upload", 0)
                download = xray_stats.get("download", 0)
                
                # Обновляем или создаем запись статистики в базе данных
                traffic_stat = db.query(TrafficStats).filter(
                    TrafficStats.key_id == key.id
                ).order_by(TrafficStats.updated_at.desc()).first()
                
                if traffic_stat:
                    # Обновляем существующую запись только если данные изменились
                    if traffic_stat.upload != upload or traffic_stat.download != download:
                        traffic_stat.upload = upload
                        traffic_stat.download = download
                        traffic_stat.updated_at = int(time.time())
                        updated_count += 1
                        logger.info(f"Updated stats for key {key.id}: upload={upload}, download={download}")
                else:
                    # Создаем новую запись
                    traffic_stat = TrafficStats(
                        key_id=key.id,
                        upload=upload,
                        download=download,
                        updated_at=int(time.time())
                    )
                    db.add(traffic_stat)
                    updated_count += 1
                    logger.info(f"Created stats for key {key.id}: upload={upload}, download={download}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error syncing stats for key {key.id}: {e}")
        
        # Сохраняем изменения
        db.commit()
        
        logger.info(f"Sync completed: {updated_count} updated, {error_count} errors")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during sync: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(sync_traffic_stats())

