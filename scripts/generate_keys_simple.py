#!/usr/bin/env python3
"""Упрощенный скрипт для генерации ключей Reality (только стандартная библиотека)"""
import secrets
import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

def generate_reality_keys():
    """Генерация пары ключей для Reality"""
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Сериализация приватного ключа
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Сериализация публичного ключа
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # Кодирование в base64
    private_key_b64 = base64.b64encode(private_bytes).decode('utf-8')
    public_key_b64 = base64.b64encode(public_bytes).decode('utf-8')
    
    return public_key_b64, private_key_b64

if __name__ == "__main__":
    print("Generating Reality keys...")
    
    try:
        public_key, private_key = generate_reality_keys()
        
        print("\n" + "="*60)
        print("REALITY KEYS GENERATED")
        print("="*60)
        print(f"\nPublic Key (pbk):\n{public_key}")
        print(f"\nPrivate Key (хранить в секрете!):\n{private_key}")
        print("\n" + "="*60)
        
        # Сохранение в файл
        keys_file = "/root/config/reality_keys.txt"
        import os
        os.makedirs("/root/config", exist_ok=True)
        
        with open(keys_file, "w") as f:
            f.write(f"PUBLIC_KEY={public_key}\n")
            f.write(f"PRIVATE_KEY={private_key}\n")
        
        print(f"\nKeys saved to: {keys_file}")
        
        # Обновление .env файла
        env_file = "/root/.env"
        env_example = "/root/.env.example"
        
        # Читаем .env.example если существует
        env_content = ""
        if os.path.exists(env_example):
            with open(env_example, "r") as f:
                env_content = f.read()
        else:
            # Создаем базовый .env
            env_content = """# API Settings
API_SECRET_KEY=change-me-in-production-use-strong-random-key
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=sqlite:///./database/veil_xray.db

# Xray API Settings
XRAY_API_HOST=127.0.0.1
XRAY_API_PORT=10085
XRAY_CONFIG_PATH=/usr/local/etc/xray/config.json

# Reality Settings (Universal parameters)
REALITY_SERVER_NAME=veil-bear.ru
REALITY_SNI=microsoft.com
REALITY_FINGERPRINT=chrome
REALITY_DEST=www.microsoft.com:443
REALITY_PORT=443

# Reality Keys (generate using scripts/init_reality_keys.py)
REALITY_PUBLIC_KEY=
REALITY_PRIVATE_KEY=

# Domain
DOMAIN=veil-bear.ru
"""
        
        # Заменяем пустые значения ключей
        env_content = env_content.replace("REALITY_PUBLIC_KEY=", f"REALITY_PUBLIC_KEY={public_key}")
        env_content = env_content.replace("REALITY_PRIVATE_KEY=", f"REALITY_PRIVATE_KEY={private_key}")
        
        # Генерируем случайный API_SECRET_KEY если он стандартный
        if "change-me-in-production-use-strong-random-key" in env_content:
            import secrets
            random_key = secrets.token_urlsafe(32)
            env_content = env_content.replace(
                "API_SECRET_KEY=change-me-in-production-use-strong-random-key",
                f"API_SECRET_KEY={random_key}"
            )
        
        # Сохраняем .env
        with open(env_file, "w") as f:
            f.write(env_content)
        
        print(f"Environment file updated: {env_file}")
        print("\nВАЖНО:")
        print("1. Сохраните приватный ключ в безопасном месте")
        print("2. Добавьте приватный ключ в конфигурацию Xray (config.json)")
        print("3. Публичный ключ уже добавлен в .env файл")
        print("="*60 + "\n")
        
    except ImportError as e:
        print(f"Error: Missing required library. Please install: pip install cryptography")
        print(f"Details: {e}")
    except Exception as e:
        print(f"Error generating keys: {e}")


