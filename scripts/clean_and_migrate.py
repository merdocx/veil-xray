#!/usr/bin/env python3
"""
Скрипт для очистки всех ключей, пользователей и конфигураций, а также выполнения миграции
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from api.database import Key, TrafficStats, Base
from api.xray_config import XrayConfigManager
import json
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def clean_database():
    """Очистка базы данных от всех ключей и статистики"""
    db_url = settings.database_url
    
    # Создаем движок
    engine = create_engine(
        db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    logger.info("🗑️  Starting database cleanup...")
    
    db = SessionLocal()
    try:
        # Удаляем всю статистику трафика
        traffic_count = db.query(TrafficStats).count()
        db.query(TrafficStats).delete()
        logger.info(f"✅ Deleted {traffic_count} traffic stats record(s)")
        
        # Удаляем все ключи
        keys_count = db.query(Key).count()
        db.query(Key).delete()
        logger.info(f"✅ Deleted {keys_count} key(s)")
        
        db.commit()
        logger.info("✅ Database cleanup completed successfully")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Database cleanup failed: {e}")
        return False
    finally:
        db.close()


def clean_xray_config():
    """Очистка конфигурации Xray от всех пользователей"""
    logger.info("🗑️  Starting Xray config cleanup...")
    
    config_manager = XrayConfigManager()
    
    try:
        config = config_manager.load_config()
        
        # Находим VLESS inbound
        vless_inbound = None
        for inbound in config.get("inbounds", []):
            if inbound.get("protocol") == "vless":
                vless_inbound = inbound
                break
        
        if not vless_inbound:
            logger.warning("VLESS inbound not found in Xray config")
            return True
        
        # Очищаем список клиентов
        clients_count = len(vless_inbound["settings"].get("clients", []))
        vless_inbound["settings"]["clients"] = []
        
        # Убеждаемся, что общий short_id присутствует
        common_short_id = settings.reality_common_short_id
        stream_settings = vless_inbound.get("streamSettings", {})
        if "realitySettings" not in stream_settings:
            stream_settings["realitySettings"] = {}
        
        reality_settings = stream_settings["realitySettings"]
        short_ids = reality_settings.get("shortIds", [])
        
        # Очищаем и добавляем только общий short_id
        if common_short_id not in short_ids:
            short_ids = [common_short_id]
        else:
            # Оставляем только общий short_id
            short_ids = [common_short_id]
        
        reality_settings["shortIds"] = short_ids
        stream_settings["realitySettings"] = reality_settings
        vless_inbound["streamSettings"] = stream_settings
        
        logger.info(f"✅ Removed {clients_count} user(s) from Xray config")
        logger.info(f"✅ Set common short_id '{common_short_id}' in Xray config")
        
        # Сохраняем конфигурацию
        if config_manager.save_config(config):
            logger.info("✅ Xray config cleanup completed successfully")
            return True
        else:
            logger.error("Failed to save Xray config")
            return False
            
    except Exception as e:
        logger.error(f"❌ Xray config cleanup failed: {e}")
        return False


def main():
    """Основная функция"""
    logger.info("🚀 Starting cleanup and migration process...")
    
    # 1. Очистка базы данных
    if not clean_database():
        logger.error("❌ Database cleanup failed, aborting")
        return False
    
    # 2. Очистка конфигурации Xray
    if not clean_xray_config():
        logger.error("❌ Xray config cleanup failed, aborting")
        return False
    
    logger.info("✅ Cleanup and migration completed successfully")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

