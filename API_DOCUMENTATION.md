# Veil Xray API - Документация для внешних ботов

Полная документация REST API для управления VPN ключами через внешние боты и приложения.

## 📋 Содержание

- [Параметры подключения для внешних ботов](#параметры-подключения-для-внешних-ботов)
- [Базовая информация](#базовая-информация)
- [Аутентификация](#аутентификация)
- [Endpoints](#endpoints)
  - [Проверка работоспособности](#проверка-работоспособности)
  - [Управление ключами](#управление-ключами)
  - [Статистика трафика](#статистика-трафика)
- [Коды ошибок](#коды-ошибок)
- [Примеры использования](#примеры-использования)

---

## Параметры подключения для внешних ботов

Для подключения внешнего бота (который управляет ключами) к серверу необходимо указать следующие параметры:

### 1. API URL (api_url)

**Базовый адрес REST API сервера**

⚠️ **ВАЖНО:** Если домен проходит через CDN (например, Akamai, Cloudflare), используйте **прямой IP-адрес сервера** вместо домена.

**Рабочие варианты:**

1. **Прямой IP с HTTP (рекомендуется, если домен за CDN):**
   - Формат: `http://IP-адрес:8000`
   - Пример: `http://YOUR_SERVER_IP:8000` (замените `YOUR_SERVER_IP` на IP вашего сервера)
   - ✅ Работает напрямую, обходит CDN
   - ⚠️ HTTP небезопасен (данные передаются в открытом виде)

2. **Поддомен без CDN (рекомендуется для production):**
   - Формат: `https://api.your-domain.com` или `http://api.your-domain.com:8000`
   - Пример: `https://api.your-domain.com` или `http://api.your-domain.com:8000`
   - ✅ Безопасно (HTTPS) и обходит CDN
   - ⚠️ Требует настройки DNS записи для поддомена

3. **Домен без CDN (если CDN отключен):**
   - Формат: `https://your-domain.com` или `http://your-domain.com:8000`
   - Пример: `https://your-domain.com` или `http://your-domain.com:8000`
   - ⚠️ Может не работать, если домен проходит через CDN

**Примечания:**
- Админка автоматически нормализует путь до `/api`, поэтому указывайте только базовый адрес без `/api` в конце
- Для разработки: `http://localhost:8000`
- Если получаете ошибку 400 от CDN (например, "Invalid URL" от Akamai), используйте прямой IP

**Как определить правильный адрес:**
```bash
# Проверка доступности API по IP
curl http://IP-адрес:8000/

# Проверка доступности API по домену
curl https://your-domain.com/

# Если домен возвращает ошибку CDN, используйте прямой IP
```

### 2. API ключ (api_key)

**Bearer-токен для авторизации**

- **Формат:** Строка (минимум 32 символа)
- **Использование:** Передается в заголовке `Authorization: Bearer YOUR_SECRET_KEY`
- **Где найти:** Значение `API_SECRET_KEY` из конфигурации сервера (файл `.env` или переменная окружения)
- **Пример:** `your-api-secret-key-minimum-32-characters-long`
- **Важно:** Для V2Ray/Xray это обязательное поле. Без правильного ключа все запросы будут возвращать `401 Unauthorized`

**Как получить:**
- Запросите у администратора сервера значение `API_SECRET_KEY`
- Или проверьте файл `.env` на сервере: `grep API_SECRET_KEY /root/.env`

### 3. Путь к бинарю Xray (v2ray_path)

**Путь к исполняемому файлу Xray**

- **По умолчанию:** `/usr/local/bin/xray`
- **Использование:** Используется для обслуживания и проверки конфигурации Xray
- **Можно указать свой путь:** Если Xray установлен в другом месте, укажите полный путь к бинарнику
- **Проверка:** Убедитесь, что файл существует и имеет права на выполнение: `ls -l /usr/local/bin/xray`

**Примеры:**
- Стандартная установка: `/usr/local/bin/xray`
- Установка через пакетный менеджер: `/usr/bin/xray`
- Кастомная установка: `/opt/xray/xray`

---

### Пример конфигурации

**Вариант 1: Поддомен с HTTPS (рекомендуется):**
```json
{
  "api_url": "https://api.your-domain.com",
  "api_key": "YOUR_API_SECRET_KEY",
  "v2ray_path": "/usr/local/bin/xray"
}
```

**Вариант 2: Прямой IP с HTTP (временное решение, если домен за CDN):**
```json
{
  "api_url": "http://YOUR_SERVER_IP:8000",
  "api_key": "YOUR_API_SECRET_KEY",
  "v2ray_path": "/usr/local/bin/xray"
}
```

**Проверка работоспособности:**
```bash
# Проверка доступности API через поддомен (HTTPS)
curl -k https://api.your-domain.com/

# Проверка доступности API через прямой IP (HTTP)
curl http://YOUR_SERVER_IP:8000/

# Создание ключа через API (HTTPS поддомен)
curl -X POST "https://api.your-domain.com/api/keys" \
  -H "Authorization: Bearer YOUR_API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "test_key"}'
```

**⚠️ Важно:** 
- Замените `your-domain.com` на ваш домен
- Замените `YOUR_SERVER_IP` на IP адрес вашего сервера
- Замените `YOUR_API_SECRET_KEY` на ваш API ключ из `.env` файла
- Рекомендуется использовать поддомен с HTTPS для production
- Если порт 443 занят Xray для VPN, используйте альтернативный порт (например, 8443)

---

## Базовая информация

**Base URL:** `https://your-domain.com` (или `http://localhost:8000` для разработки)

**Формат данных:** JSON

**Кодировка:** UTF-8

**Версия API:** 1.3.1

---

## Важная информация о Short ID

### Общий Short ID для всех пользователей

Система использует **единый общий `short_id`** для всех VPN ключей вместо индивидуальных `short_id` для каждого ключа.

**Преимущества:**
- ✅ **Нет перезагрузки Xray** - при создании/удалении ключей не требуется перезагрузка Xray, так как `short_id` не меняется
- ✅ **Мгновенная доступность** - новые ключи работают сразу после создания
- ✅ **Упрощенная конфигурация** - один `short_id` для всех пользователей упрощает управление

**Настройка:**
- По умолчанию используется `short_id`: `"7bb45050"`
- Можно изменить через переменную окружения `REALITY_COMMON_SHORT_ID` в файле `.env`
- `short_id` должен быть строкой из 8 шестнадцатеричных символов

**Важно:**
- Все ключи в ответах API возвращают один и тот же `short_id`
- Все VLESS ссылки используют один и тот же `short_id` - это нормальное поведение
- При первом запуске API общий `short_id` автоматически добавляется в конфигурацию Xray

---

## Аутентификация

Все запросы к API (кроме проверки работоспособности) требуют аутентификации через Bearer Token.

### Заголовок авторизации

```
Authorization: Bearer YOUR_SECRET_KEY
```

`YOUR_SECRET_KEY` - это значение `API_SECRET_KEY` из конфигурации сервера. Этот ключ должен быть передан администратором сервера.

### Пример запроса с авторизацией

```bash
curl -X GET "https://your-domain.com/api/keys" \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "Content-Type: application/json"
```

---

## Endpoints

### Проверка работоспособности

#### `GET /`

Проверка доступности API сервера. Не требует аутентификации.

**Запрос:**
```bash
GET /
```

**Ответ:**
```json
{
  "status": "ok",
  "service": "veil-xray-api"
}
```

**Коды ответа:**
- `200 OK` - API работает

---

### Управление ключами

#### `POST /api/keys`

Создание нового VPN ключа.

**Запрос:**
```bash
POST /api/keys
Authorization: Bearer YOUR_SECRET_KEY
Content-Type: application/json

{
  "name": "user_name"  // опционально
}
```

**Параметры:**
- `name` (string, опционально) - имя пользователя для идентификации

**Ответ (успех):**
```json
{
  "key_id": 1,
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "short_id": "7bb45050",
  "name": "user_name",
  "created_at": 1703520000,
  "is_active": true
}
```

**Поля ответа:**
- `key_id` (integer) - уникальный идентификатор ключа
- `uuid` (string) - UUID для VLESS протокола (генерируется автоматически)
- `short_id` (string) - общий короткий идентификатор для всех пользователей (8 символов, по умолчанию `"7bb45050"`)
- `name` (string|null) - имя пользователя
- `created_at` (integer) - Unix timestamp создания
- `is_active` (boolean) - статус активности

**Коды ответа:**
- `200 OK` - ключ успешно создан
- `401 Unauthorized` - неверный токен авторизации
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Ключ автоматически добавляется в Xray конфигурацию
- Статистика трафика инициализируется с нулевыми значениями
- UUID генерируется автоматически для каждого ключа
- **Short ID общий для всех пользователей** - это позволяет избежать перезагрузки Xray при создании/удалении ключей. Все ключи используют один и тот же `short_id` из настроек (`REALITY_COMMON_SHORT_ID` в `.env`, по умолчанию `"7bb45050"`)

---

#### `GET /api/keys`

Получение списка всех ключей.

**Запрос:**
```bash
GET /api/keys
Authorization: Bearer YOUR_SECRET_KEY
```

**Ответ:**
```json
{
  "keys": [
    {
      "key_id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "short_id": "7bb45050",
      "name": "user_name",
      "created_at": 1703520000,
      "is_active": true
    },
    {
      "key_id": 2,
      "uuid": "223e4567-e89b-12d3-a456-426614174001",
      "short_id": "7bb45050",
      "name": null,
      "created_at": 1703520100,
      "is_active": true
    }
  ],
  "total": 2
}
```

**Коды ответа:**
- `200 OK` - успешно
- `401 Unauthorized` - неверный токен авторизации
- `500 Internal Server Error` - ошибка сервера

---

#### `GET /api/keys/{key_id}`

Получение информации о конкретном ключе.

**Запрос:**
```bash
GET /api/keys/1
Authorization: Bearer YOUR_SECRET_KEY
```

**Параметры URL:**
- `key_id` (integer) - идентификатор ключа

**Ответ (успех):**
```json
{
  "key_id": 1,
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "short_id": "7bb45050",
  "name": "user_name",
  "created_at": 1703520000,
  "is_active": true
}
```

**Коды ответа:**
- `200 OK` - успешно
- `401 Unauthorized` - неверный токен авторизации
- `404 Not Found` - ключ не найден
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Все ключи используют один и тот же `short_id` (общий для всех пользователей)

---

#### `DELETE /api/keys/{key_id}`

Удаление ключа.

**Запрос:**
```bash
DELETE /api/keys/1
Authorization: Bearer YOUR_SECRET_KEY
```

**Параметры URL:**
- `key_id` (integer) - идентификатор ключа

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Key 1 deleted successfully"
}
```

**Коды ответа:**
- `200 OK` - ключ успешно удален
- `401 Unauthorized` - неверный токен авторизации
- `404 Not Found` - ключ не найден
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Ключ удаляется из базы данных и конфигурации Xray
- Статистика трафика удаляется автоматически (каскадное удаление)
- Пользователь удаляется из Xray без перезагрузки сервиса

---

#### `GET /api/keys/{key_id}/link`

Получение готовой VLESS ссылки для импорта в клиент.

**Запрос:**
```bash
GET /api/keys/1/link
Authorization: Bearer YOUR_SECRET_KEY
```

**Параметры URL:**
- `key_id` (integer) - идентификатор ключа

**Ответ (успех):**
```json
{
  "key_id": 1,
  "vless_link": "vless://123e4567-e89b-12d3-a456-426614174000@your-domain.com:443?type=tcp&security=reality&sni=microsoft.com&fp=chrome&pbk=public_key_here&sid=abcd1234&spx=%2F&flow=none#user_name"
}
```

**Поля ответа:**
- `key_id` (integer) - идентификатор ключа
- `vless_link` (string) - готовая VLESS ссылка для импорта

**Коды ответа:**
- `200 OK` - успешно
- `401 Unauthorized` - неверный токен авторизации
- `404 Not Found` - ключ не найден
- `500 Internal Server Error` - ошибка сервера или не настроен публичный ключ Reality

**Примечания:**
- Ссылка оптимизирована для клиента v2raytun (iOS/Android)
- Ссылку можно напрямую импортировать в VPN клиент
- Формат ссылки соответствует стандарту VLESS протокола

---

### Статистика трафика

#### `GET /api/keys/{key_id}/traffic`

Получение статистики использования трафика по ключу.

**Запрос:**
```bash
GET /api/keys/1/traffic
Authorization: Bearer YOUR_SECRET_KEY
```

**Параметры URL:**
- `key_id` (integer) - идентификатор ключа

**Ответ (успех):**
```json
{
  "key_id": 1,
  "upload": 1024000,
  "download": 2048000,
  "total": 3072000,
  "last_updated": 1703520000
}
```

**Поля ответа:**
- `key_id` (integer) - идентификатор ключа
- `upload` (integer) - загружено байт (от клиента к серверу)
- `download` (integer) - скачано байт (от сервера к клиенту)
- `total` (integer) - общий трафик (upload + download)
- `last_updated` (integer) - Unix timestamp последнего обновления

**Коды ответа:**
- `200 OK` - успешно
- `401 Unauthorized` - неверный токен авторизации
- `404 Not Found` - ключ не найден
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Статистика обновляется автоматически при запросе из Xray API
- Данные синхронизируются с Xray Stats API
- Значения в байтах (для конвертации в MB: `bytes / 1024 / 1024`)

---

#### `POST /api/keys/{key_id}/traffic/reset`

Обнуление статистики трафика по конкретному ключу.

**Запрос:**
```bash
POST /api/keys/1/traffic/reset
Authorization: Bearer YOUR_SECRET_KEY
```

**Параметры URL:**
- `key_id` (integer) - идентификатор ключа

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Traffic reset successfully for key 1",
  "key_id": 1,
  "previous_upload": 1024000,
  "previous_download": 2048000,
  "previous_total": 3072000
}
```

**Поля ответа:**
- `success` (boolean) - успешность операции
- `message` (string) - текстовое сообщение о результате
- `key_id` (integer) - идентификатор ключа
- `previous_upload` (integer) - значение upload до обнуления (в байтах)
- `previous_download` (integer) - значение download до обнуления (в байтах)
- `previous_total` (integer) - общий трафик до обнуления (в байтах)

**Коды ответа:**
- `200 OK` - трафик успешно обнулен
- `401 Unauthorized` - неверный токен авторизации
- `404 Not Found` - ключ не найден
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Обнуляет значения `upload` и `download` в базе данных
- Сохраняет предыдущие значения в ответе для истории
- Обновляет timestamp последнего обновления
- Если статистики для ключа не было, создается новая запись с нулевыми значениями
- **Важно:** Обнуление происходит только в базе данных. Xray может продолжать считать трафик, но при следующей синхронизации значения будут обновлены из Xray API

---

#### `POST /api/traffic/sync`

Ручная синхронизация статистики трафика для всех активных ключей.

**Запрос:**
```bash
POST /api/traffic/sync
Authorization: Bearer YOUR_SECRET_KEY
```

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Synced 10 keys, 0 errors",
  "updated": 10,
  "errors": 0
}
```

**Поля ответа:**
- `success` (boolean) - успешность операции
- `message` (string) - текстовое сообщение о результате
- `updated` (integer) - количество обновленных ключей
- `errors` (integer) - количество ошибок при синхронизации

**Коды ответа:**
- `200 OK` - синхронизация завершена
- `401 Unauthorized` - неверный токен авторизации
- `500 Internal Server Error` - ошибка сервера

**Примечания:**
- Синхронизируются только активные ключи (`is_active = true`)
- Операция может занять время при большом количестве ключей
- Ошибки для отдельных ключей не прерывают общую синхронизацию

---

## Коды ошибок

### HTTP статус коды

| Код | Описание | Причина |
|-----|----------|---------|
| `200` | OK | Запрос выполнен успешно |
| `400` | Bad Request | Неверный формат запроса |
| `401` | Unauthorized | Отсутствует или неверный токен авторизации |
| `403` | Forbidden | Доступ запрещен |
| `404` | Not Found | Ресурс не найден (ключ, endpoint) |
| `500` | Internal Server Error | Ошибка сервера |

### Формат ошибок

Все ошибки возвращаются в формате:

```json
{
  "detail": "Описание ошибки"
}
```

**Примеры:**

```json
{
  "detail": "Key with id 999 not found"
}
```

```json
{
  "detail": "Failed to create key: Database error"
}
```

---

## Примеры использования

### Python (requests)

```python
import requests

API_URL = "https://your-domain.com"
API_KEY = "your-secret-key-here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Создание ключа
response = requests.post(
    f"{API_URL}/api/keys",
    json={"name": "user_123"},
    headers=headers
)
key_data = response.json()
print(f"Created key: {key_data['key_id']}, UUID: {key_data['uuid']}")

# Получение VLESS ссылки
key_id = key_data['key_id']
response = requests.get(
    f"{API_URL}/api/keys/{key_id}/link",
    headers=headers
)
vless_link = response.json()['vless_link']
print(f"VLESS link: {vless_link}")

# Получение статистики
response = requests.get(
    f"{API_URL}/api/keys/{key_id}/traffic",
    headers=headers
)
traffic = response.json()
print(f"Traffic: {traffic['total'] / 1024 / 1024:.2f} MB")

# Обнуление статистики трафика
response = requests.post(
    f"{API_URL}/api/keys/{key_id}/traffic/reset",
    headers=headers
)
reset_data = response.json()
print(f"Traffic reset: previous total was {reset_data['previous_total'] / 1024 / 1024:.2f} MB")

# Список всех ключей
response = requests.get(f"{API_URL}/api/keys", headers=headers)
keys = response.json()
print(f"Total keys: {keys['total']}")

# Удаление ключа
response = requests.delete(
    f"{API_URL}/api/keys/{key_id}",
    headers=headers
)
print(response.json()['message'])
```

### Python (httpx, асинхронный)

```python
import httpx
import asyncio

API_URL = "https://your-domain.com"
API_KEY = "your-secret-key-here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

async def main():
    async with httpx.AsyncClient() as client:
        # Создание ключа
        response = await client.post(
            f"{API_URL}/api/keys",
            json={"name": "user_123"},
            headers=headers
        )
        key_data = response.json()
        
        # Получение VLESS ссылки
        key_id = key_data['key_id']
        response = await client.get(
            f"{API_URL}/api/keys/{key_id}/link",
            headers=headers
        )
        vless_link = response.json()['vless_link']
        print(f"VLESS link: {vless_link}")

asyncio.run(main())
```

### cURL

```bash
# Переменные
API_URL="https://your-domain.com"
API_KEY="your-secret-key-here"

# Создание ключа
curl -X POST "${API_URL}/api/keys" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name": "user_123"}'

# Получение списка ключей
curl -X GET "${API_URL}/api/keys" \
  -H "Authorization: Bearer ${API_KEY}"

# Получение VLESS ссылки
KEY_ID=1
curl -X GET "${API_URL}/api/keys/${KEY_ID}/link" \
  -H "Authorization: Bearer ${API_KEY}"

# Получение статистики
curl -X GET "${API_URL}/api/keys/${KEY_ID}/traffic" \
  -H "Authorization: Bearer ${API_KEY}"

# Обнуление статистики трафика
curl -X POST "${API_URL}/api/keys/${KEY_ID}/traffic/reset" \
  -H "Authorization: Bearer ${API_KEY}"

# Удаление ключа
curl -X DELETE "${API_URL}/api/keys/${KEY_ID}" \
  -H "Authorization: Bearer ${API_KEY}"
```

### JavaScript (fetch)

```javascript
const API_URL = 'https://your-domain.com';
const API_KEY = 'your-secret-key-here';

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};

// Создание ключа
async function createKey(name) {
  const response = await fetch(`${API_URL}/api/keys`, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({ name })
  });
  return await response.json();
}

// Получение VLESS ссылки
async function getVlessLink(keyId) {
  const response = await fetch(`${API_URL}/api/keys/${keyId}/link`, {
    headers: headers
  });
  const data = await response.json();
  return data.vless_link;
}

// Получение статистики
async function getTraffic(keyId) {
  const response = await fetch(`${API_URL}/api/keys/${keyId}/traffic`, {
    headers: headers
  });
  return await response.json();
}

// Обнуление статистики трафика
async function resetTraffic(keyId) {
  const response = await fetch(`${API_URL}/api/keys/${keyId}/traffic/reset`, {
    method: 'POST',
    headers: headers
  });
  return await response.json();
}

// Использование
(async () => {
  const key = await createKey('user_123');
  console.log('Created key:', key.key_id);
  
  const link = await getVlessLink(key.key_id);
  console.log('VLESS link:', link);
  
  const traffic = await getTraffic(key.key_id);
  console.log('Traffic:', traffic.total / 1024 / 1024, 'MB');
  
  // Обнуление трафика
  const reset = await resetTraffic(key.key_id);
  console.log('Traffic reset, previous total:', reset.previous_total / 1024 / 1024, 'MB');
})();
```

### Telegram Bot (python-telegram-bot)

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests

API_URL = "https://your-domain.com"
API_KEY = "your-secret-key-here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

async def create_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового ключа"""
    user_name = update.effective_user.username or str(update.effective_user.id)
    
    response = requests.post(
        f"{API_URL}/api/keys",
        json={"name": user_name},
        headers=headers
    )
    
    if response.status_code == 200:
        key_data = response.json()
        
        # Получаем VLESS ссылку
        link_response = requests.get(
            f"{API_URL}/api/keys/{key_data['key_id']}/link",
            headers=headers
        )
        vless_link = link_response.json()['vless_link']
        
        await update.message.reply_text(
            f"✅ Ключ создан!\n\n"
            f"ID: {key_data['key_id']}\n"
            f"UUID: {key_data['uuid']}\n\n"
            f"VLESS ссылка:\n`{vless_link}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Ошибка при создании ключа")

async def traffic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение статистики трафика"""
    if not context.args:
        await update.message.reply_text("Использование: /traffic <key_id>")
        return
    
    key_id = context.args[0]
    response = requests.get(
        f"{API_URL}/api/keys/{key_id}/traffic",
        headers=headers
    )
    
    if response.status_code == 200:
        traffic = response.json()
        total_mb = traffic['total'] / 1024 / 1024
        upload_mb = traffic['upload'] / 1024 / 1024
        download_mb = traffic['download'] / 1024 / 1024
        
        await update.message.reply_text(
            f"📊 Статистика трафика (ключ {key_id}):\n\n"
            f"📤 Загружено: {upload_mb:.2f} MB\n"
            f"📥 Скачано: {download_mb:.2f} MB\n"
            f"📊 Всего: {total_mb:.2f} MB"
        )
    else:
        await update.message.reply_text("❌ Ключ не найден")

async def reset_traffic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обнуление статистики трафика"""
    if not context.args:
        await update.message.reply_text("Использование: /reset_traffic <key_id>")
        return
    
    key_id = context.args[0]
    response = requests.post(
        f"{API_URL}/api/keys/{key_id}/traffic/reset",
        headers=headers
    )
    
    if response.status_code == 200:
        reset_data = response.json()
        previous_total_mb = reset_data['previous_total'] / 1024 / 1024
        
        await update.message.reply_text(
            f"🔄 Трафик обнулен для ключа {key_id}\n\n"
            f"📊 Предыдущий трафик: {previous_total_mb:.2f} MB"
        )
    elif response.status_code == 404:
        await update.message.reply_text("❌ Ключ не найден")
    else:
        await update.message.reply_text("❌ Ошибка при обнулении трафика")

# Инициализация бота
app = Application.builder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("create", create_key_command))
app.add_handler(CommandHandler("traffic", traffic_command))
app.add_handler(CommandHandler("reset_traffic", reset_traffic_command))
app.run_polling()
```

---

## Рекомендации для ботов

### Обработка ошибок

Всегда проверяйте HTTP статус код перед обработкой ответа:

```python
response = requests.get(f"{API_URL}/api/keys/{key_id}", headers=headers)

if response.status_code == 200:
    data = response.json()
    # Обработка данных
elif response.status_code == 404:
    # Ключ не найден
    print("Key not found")
elif response.status_code == 401:
    # Ошибка авторизации
    print("Unauthorized")
else:
    # Другая ошибка
    error = response.json()
    print(f"Error: {error['detail']}")
```

### Retry механизм

Рекомендуется использовать retry для сетевых запросов:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def api_request(method, endpoint, **kwargs):
    response = requests.request(method, f"{API_URL}{endpoint}", **kwargs)
    response.raise_for_status()
    return response.json()
```

### Кэширование

Для часто запрашиваемых данных (список ключей, статистика) используйте кэширование:

```python
from functools import lru_cache
from datetime import datetime, timedelta

cache_time = {}
CACHE_TTL = 60  # секунд

def get_cached_keys():
    now = datetime.now()
    if 'keys' not in cache_time or (now - cache_time['keys']).seconds > CACHE_TTL:
        response = requests.get(f"{API_URL}/api/keys", headers=headers)
        cache['keys'] = response.json()
        cache_time['keys'] = now
    return cache['keys']
```

### Rate Limiting

Избегайте слишком частых запросов. Рекомендуется:
- Не более 10 запросов в секунду
- Использовать batch операции где возможно
- Кэшировать данные, которые редко меняются

---

## Дополнительная информация

### Swagger UI

Интерактивная документация API доступна по адресу:
- `https://your-domain.com/docs` - Swagger UI
- `https://your-domain.com/redoc` - ReDoc

### Поддержка

При возникновении проблем:
1. Проверьте правильность токена авторизации
2. Убедитесь, что API сервер доступен
3. Проверьте формат запросов и ответов
4. Создайте Issue в репозитории проекта

---

**Версия документации:** 1.2.0  
**Последнее обновление:** 2025-11-25

