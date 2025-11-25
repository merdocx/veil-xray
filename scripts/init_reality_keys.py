#!/usr/bin/env python3
"""Скрипт для генерации ключей Reality при первом запуске"""
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.utils import generate_reality_keys
from config.settings import settings

def main():
    """Генерация и вывод ключей Reality"""
    print("Generating Reality keys...")
    
    public_key, private_key = generate_reality_keys()
    
    print("\n" + "="*60)
    print("REALITY KEYS GENERATED")
    print("="*60)
    print(f"\nPublic Key (pbk):\n{public_key}")
    print(f"\nPrivate Key (хранить в секрете!):\n{private_key}")
    print("\n" + "="*60)
    print("\nВАЖНО:")
    print("1. Сохраните приватный ключ в безопасном месте")
    print("2. Добавьте приватный ключ в конфигурацию Xray (config.json)")
    print("3. Установите публичный ключ в переменные окружения или config/settings.py")
    print("4. Публичный ключ будет использоваться для генерации VLESS ссылок")
    print("="*60 + "\n")
    
    # Сохранение в файл (опционально)
    keys_file = Path(__file__).parent.parent / "config" / "reality_keys.txt"
    keys_file.parent.mkdir(exist_ok=True)
    
    with open(keys_file, "w") as f:
        f.write(f"PUBLIC_KEY={public_key}\n")
        f.write(f"PRIVATE_KEY={private_key}\n")
    
    print(f"Keys saved to: {keys_file}")
    print("ВАЖНО: Удалите этот файл после настройки!")

if __name__ == "__main__":
    main()


