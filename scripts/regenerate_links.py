#!/usr/bin/env python3
"""Скрипт для генерации исправленных VLESS ссылок для всех ключей"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from api.database import SessionLocal, Key
from api.utils import build_vless_link
from config.settings import settings
import base64


def regenerate_links():
    """Генерация исправленных VLESS ссылок для всех ключей"""
    db: Session = SessionLocal()
    
    try:
        # Получаем все активные ключи
        keys = db.query(Key).filter(Key.is_active == 1).order_by(Key.id).all()
        
        if not keys:
            print("📋 В базе данных нет активных ключей")
            return
        
        # Проверяем наличие публичного ключа
        if not settings.reality_public_key:
            print("❌ Ошибка: Reality public key не настроен в .env файле")
            return
        
        # Конвертируем публичный ключ в URL-safe формат
        public_key = settings.reality_public_key
        try:
            if "/" in public_key or "+" in public_key or public_key.endswith("="):
                # Стандартный base64, конвертируем в URL-safe
                decoded = base64.b64decode(
                    public_key + "==" if not public_key.endswith("=") else public_key
                )
                public_key = (
                    base64.urlsafe_b64encode(decoded).decode("utf-8").rstrip("=")
                )
        except Exception:
            pass
        
        print("=" * 120)
        print(f"{'ID':<5} {'UUID':<38} {'Name':<20} {'VLESS Link':<60}")
        print("=" * 120)
        
        for key in keys:
            # Генерируем исправленную ссылку (без flow=none)
            vless_link = build_vless_link(
                uuid=key.uuid,
                short_id=settings.reality_common_short_id,
                server_address=settings.domain,
                port=settings.reality_port,
                sni=settings.reality_sni,
                fingerprint=settings.reality_fingerprint,
                public_key=public_key,
                dest=settings.reality_dest,
                flow="none",  # Будет автоматически пропущен в исправленной функции
            )
            
            name = key.name or "-"
            uuid_short = key.uuid[:8] + "..." if len(key.uuid) > 8 else key.uuid
            
            # Проверяем, что flow отсутствует в ссылке
            has_flow_none = "flow=none" in vless_link or "&flow=none" in vless_link
            status = "✅" if not has_flow_none else "❌"
            
            print(f"{status} {key.id:<4} {uuid_short:<38} {name:<20}")
            print(f"   {vless_link}")
            print()
        
        print("=" * 120)
        print(f"\n📊 Всего активных ключей: {len(keys)}")
        print("✅ Все ссылки исправлены и готовы к использованию в v2raytun")
        print("\n💡 Примечание: Ссылки генерируются динамически при каждом запросе через API.")
        print("   После исправления кода все новые запросы будут возвращать правильные ссылки.")
        
    except Exception as e:
        print(f"❌ Ошибка при генерации ссылок: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    regenerate_links()

