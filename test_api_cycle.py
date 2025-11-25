#!/usr/bin/env python3
"""
Тестовый скрипт для проверки всего цикла работы API:
1. Создание ключа
2. Получение VLESS ссылки
3. Проверка работоспособности
4. Получение трафика
5. Удаление ключа
"""

import requests
import json
import sys
from urllib.parse import urlparse

# Настройки
API_URL = "http://localhost:8000"  # или ваш URL
API_KEY = "a9lxDECFHDLI67OcvA9mTTTPyaesHxA2BlcUCTQhoEQ"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_health_check():
    """1. Проверка работоспособности API"""
    print("\n" + "="*60)
    print("1. ПРОВЕРКА РАБОТОСПОСОБНОСТИ API")
    print("="*60)
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        if response.status_code == 200:
            print("✅ API работает")
            return True
        else:
            print("❌ API не работает")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_create_key():
    """2. Создание ключа"""
    print("\n" + "="*60)
    print("2. СОЗДАНИЕ КЛЮЧА")
    print("="*60)
    try:
        response = requests.post(
            f"{API_URL}/api/keys",
            json={"name": "Test API Cycle Key"},
            headers=headers,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ Ключ создан")
            
            # Проверяем формат short_id
            short_id = data.get("short_id", "")
            print(f"\nПроверка short_id: '{short_id}'")
            print(f"  - Длина: {len(short_id)}")
            print(f"  - Тип: {type(short_id)}")
            
            # Проверяем, что это hex строка
            try:
                int(short_id, 16)
                print(f"  - ✅ Является валидной hex строкой")
            except ValueError:
                print(f"  - ❌ НЕ является hex строкой!")
                return None
            
            # Проверяем UUID
            uuid = data.get("uuid", "")
            print(f"\nПроверка UUID: '{uuid}'")
            print(f"  - Длина: {len(uuid)}")
            print(f"  - Формат: {'✅ Корректный' if len(uuid) == 36 else '❌ Некорректный'}")
            
            return data
        else:
            print(f"❌ Ошибка создания ключа: {data.get('detail', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_get_vless_link(key_id):
    """3. Получение VLESS ссылки"""
    print("\n" + "="*60)
    print("3. ПОЛУЧЕНИЕ VLESS ССЫЛКИ")
    print("="*60)
    try:
        response = requests.get(
            f"{API_URL}/api/keys/{key_id}/link",
            headers=headers,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            vless_link = data.get("vless_link", "")
            print(f"\n✅ VLESS ссылка получена")
            print(f"Ссылка: {vless_link}")
            
            # Парсим ссылку
            if vless_link.startswith("vless://"):
                parsed = urlparse(vless_link)
                print(f"\nПарсинг ссылки:")
                print(f"  - UUID: {parsed.username}")
                print(f"  - Сервер: {parsed.hostname}:{parsed.port}")
                
                # Парсим параметры
                params = {}
                for param in parsed.query.split("&"):
                    if "=" in param:
                        k, v = param.split("=", 1)
                        params[k] = v
                
                print(f"  - Параметры:")
                for k, v in params.items():
                    print(f"    * {k}: {v}")
                
                # Проверяем sid (short_id)
                sid = params.get("sid", "")
                print(f"\n  Проверка sid (short_id): '{sid}'")
                try:
                    int(sid, 16)
                    print(f"    ✅ Является валидной hex строкой")
                except ValueError:
                    print(f"    ❌ НЕ является hex строкой!")
            
            return data
        else:
            print(f"❌ Ошибка получения ссылки: {data.get('detail', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_get_traffic(key_id):
    """4. Получение статистики трафика"""
    print("\n" + "="*60)
    print("4. ПОЛУЧЕНИЕ СТАТИСТИКИ ТРАФИКА")
    print("="*60)
    try:
        response = requests.get(
            f"{API_URL}/api/keys/{key_id}/traffic",
            headers=headers,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ Статистика трафика получена")
            upload = data.get("upload", 0)
            download = data.get("download", 0)
            total = data.get("total", 0)
            print(f"  - Upload: {upload} bytes ({upload / 1024 / 1024:.2f} MB)")
            print(f"  - Download: {download} bytes ({download / 1024 / 1024:.2f} MB)")
            print(f"  - Total: {total} bytes ({total / 1024 / 1024:.2f} MB)")
            return data
        else:
            print(f"❌ Ошибка получения статистики: {data.get('detail', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_delete_key(key_id):
    """5. Удаление ключа"""
    print("\n" + "="*60)
    print("5. УДАЛЕНИЕ КЛЮЧА")
    print("="*60)
    try:
        response = requests.delete(
            f"{API_URL}/api/keys/{key_id}",
            headers=headers,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ Ключ удален")
            return True
        else:
            print(f"❌ Ошибка удаления: {data.get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция - выполняет весь цикл тестирования"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ПОЛНОГО ЦИКЛА РАБОТЫ API")
    print("="*60)
    
    # 1. Проверка работоспособности
    if not test_health_check():
        print("\n❌ API не работает, прекращаем тестирование")
        sys.exit(1)
    
    # 2. Создание ключа
    key_data = test_create_key()
    if not key_data:
        print("\n❌ Не удалось создать ключ, прекращаем тестирование")
        sys.exit(1)
    
    key_id = key_data.get("key_id")
    short_id = key_data.get("short_id")
    uuid = key_data.get("uuid")
    
    print(f"\n📋 Созданный ключ:")
    print(f"  - ID: {key_id}")
    print(f"  - UUID: {uuid}")
    print(f"  - Short ID: {short_id}")
    
    # 3. Получение VLESS ссылки
    link_data = test_get_vless_link(key_id)
    if not link_data:
        print("\n⚠️  Не удалось получить VLESS ссылку, но продолжаем тестирование")
    
    # 4. Получение статистики трафика
    traffic_data = test_get_traffic(key_id)
    if not traffic_data:
        print("\n⚠️  Не удалось получить статистику трафика, но продолжаем тестирование")
    
    # 5. Удаление ключа
    if not test_delete_key(key_id):
        print("\n⚠️  Не удалось удалить ключ")
    
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*60)

if __name__ == "__main__":
    main()

