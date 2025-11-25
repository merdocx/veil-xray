#!/usr/bin/env python3
"""
Скрипт миграции для перехода на единый short_id

Обновляет все существующие ключи в базе данных, устанавливая им общий short_id.
Также удаляет уникальное ограничение с поля short_id (для SQLite требуется пересоздание таблицы).
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from api.database import Key, Base
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_database():
    """Миграция базы данных на единый short_id"""
    db_url = settings.database_url
    
    # Создаем движок
    engine = create_engine(
        db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    common_short_id = settings.reality_common_short_id
    logger.info(f"🔄 Starting migration to common short_id: {common_short_id}")
    
    db = SessionLocal()
    try:
        # Получаем все ключи
        keys = db.query(Key).all()
        logger.info(f"Found {len(keys)} key(s) in database")
        
        updated_count = 0
        for key in keys:
            if key.short_id != common_short_id:
                old_short_id = key.short_id
                key.short_id = common_short_id
                updated_count += 1
                logger.info(
                    f"Updated key {key.id} (UUID: {key.uuid[:8]}...): "
                    f"{old_short_id} -> {common_short_id}"
                )
        
        if updated_count > 0:
            db.commit()
            logger.info(f"✅ Updated {updated_count} key(s) with common short_id")
        else:
            logger.info("✅ All keys already use common short_id")
        
        # Для SQLite: удаление уникального ограничения требует пересоздания таблицы
        # Это сложная операция, поэтому просто предупреждаем пользователя
        if "sqlite" in db_url:
            logger.warning(
                "⚠️  SQLite doesn't support ALTER COLUMN to remove UNIQUE constraint. "
                "If you encounter errors when creating new keys, you may need to: "
                "1. Export your data, 2. Delete the database, 3. Recreate it, 4. Import data back."
            )
        else:
            # Для других БД можно попробовать удалить ограничение
            try:
                with engine.connect() as conn:
                    # Пытаемся удалить уникальный индекс (если существует)
                    # Это зависит от конкретной СУБД
                    logger.info("Attempting to remove unique constraint from short_id...")
                    # Для PostgreSQL:
                    if "postgresql" in db_url:
                        conn.execute(text(
                            "DROP INDEX IF EXISTS ix_keys_short_id;"
                        ))
                        conn.execute(text(
                            "ALTER TABLE keys DROP CONSTRAINT IF EXISTS keys_short_id_key;"
                        ))
                        conn.commit()
                        logger.info("✅ Removed unique constraint from short_id")
            except Exception as e:
                logger.warning(f"⚠️  Could not remove unique constraint: {e}")
                logger.info("You may need to manually remove the unique constraint from short_id")
        
        logger.info("✅ Migration completed successfully")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Migration failed: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)

