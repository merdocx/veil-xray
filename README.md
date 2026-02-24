# Veil Xray - VLESS+Reality VPN Server with API Management

Сервер VPN на базе Xray с протоколом VLESS+Reality и REST API для управления пользователями и мониторинга трафика.

## 🚀 Особенности

- **VLESS + Reality протокол** - современный и безопасный VPN протокол
- **REST API** - полное управление через API без перезагрузки сервиса
- **Динамическое управление** - добавление/удаление пользователей без перезапуска Xray
- **Мониторинг трафика** - статистика использования в реальном времени
- **Оптимизация для мобильных** - оптимизировано для v2raytun на iOS/Android
- **SQLite база данных** - простая и надежная база данных

## 📋 Требования

- Python 3.11+
- Xray-core 25.x или 26.x (рекомендуется 26.x). Flow задаётся в `REALITY_FLOW` (по умолчанию `xtls-rprx-vision` для совместимости с 26.x)
- Linux (Ubuntu/Debian)
- Домен с настроенным DNS (например, your-domain.com)

## 🛠 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/merdocx/veil-xray.git
cd veil-xray
```

### 2. Установка зависимостей

**Рекомендуется использовать виртуальное окружение:**

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

**Или без виртуального окружения:**

```bash
pip install -r requirements.txt
```

### 3. Генерация ключей Reality

```bash
python scripts/init_reality_keys.py
```

Сохраните приватный ключ для конфигурации Xray и публичный ключ для настроек API.

### 4. Настройка конфигурации

Создайте файл `.env` с настройками:
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
read_file

```env
API_SECRET_KEY=your-secret-key-here
REALITY_PUBLIC_KEY=your-public-key-here
REALITY_PRIVATE_KEY=your-private-key-here
REALITY_COMMON_SHORT_ID=7bb45050
DATABASE_URL=sqlite:///./database/veil_xray.db
XRAY_API_HOST=127.0.0.1
XRAY_API_PORT=10085
```

**Примечание:** `REALITY_COMMON_SHORT_ID` - общий short_id для всех пользователей (по умолчанию `"7bb45050"`). Все ключи используют один и тот же short_id, что позволяет избежать перезагрузки Xray при создании/удалении ключей.

### 5. Настройка Xray

1. Установите Xray-core согласно [официальной документации](https://xtls.github.io/)
2. Скопируйте `xray/config.example.json` в `/usr/local/etc/xray/config.json`
3. Добавьте приватный ключ Reality в конфигурацию Xray
4. Настройте API endpoint в Xray:

```json
{
  "api": {
    "tag": "api",
    "services": ["StatsService", "HandlerService"]
  }
}
```

5. Запустите Xray:

```bash
systemctl start xray
systemctl enable xray
```

### 6. Инициализация базы данных

База данных создастся автоматически при первом запуске API.

### 7. Запуск API сервера

**Если используете виртуальное окружение, активируйте его:**

```bash
source venv/bin/activate  # Linux/Mac
```

**Запуск API сервера:**

```bash
python -m api.main
```

Или с помощью uvicorn:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Для production используйте systemd:

```bash
# Скопировать unit файл
sudo cp scripts/veil-xray-api.service /etc/systemd/system/

# Отредактировать пути в файле (если необходимо)
sudo nano /etc/systemd/system/veil-xray-api.service

# Перезагрузить systemd
sudo systemctl daemon-reload

# Запустить сервис
sudo systemctl start veil-xray-api

# Включить автозапуск
sudo systemctl enable veil-xray-api

# Проверить статус
sudo systemctl status veil-xray-api
```

**Примечание:** Перед использованием systemd service файла убедитесь, что пути в файле `scripts/veil-xray-api.service` соответствуют вашей установке (путь к Python, путь к проекту, пользователь).

### 8. Настройка HTTPS и поддомена для API (рекомендуется для production)

Для обеспечения безопасности API рекомендуется настроить HTTPS через Nginx reverse proxy с SSL сертификатами от Let's Encrypt.

**Рекомендуемая конфигурация:** Использование отдельного поддомена для API (например, `api.your-domain.com`) позволяет:
- Изолировать API от основного домена
- Обойти проблемы с CDN (если основной домен проходит через CDN)
- Упростить настройку и управление

#### Настройка поддомена для API

**Шаг 1: Настройка DNS**

Создайте A-запись для поддомена в DNS:
- Имя: `api`
- Тип: `A`
- Значение: IP адрес вашего сервера
- TTL: 300 (или по умолчанию)

**Шаг 2: Автоматическая настройка поддомена**

Используйте готовый скрипт для автоматической настройки:

```bash
sudo bash scripts/setup_api_subdomain.sh
```

Перед запуском отредактируйте скрипт и замените:
- `SUBDOMAIN="api.your-domain.com"` на ваш поддомен (например, `api.example.com`)
- `EMAIL="your-email@example.com"` на ваш email для Let's Encrypt

Скрипт выполнит:
- Проверку DNS записи
- Установку Nginx (если не установлен)
- Установку Certbot (если не установлен)
- Создание конфигурации Nginx для поддомена
- Получение SSL сертификата для поддомена
- Настройку автоматического обновления сертификатов
- Настройку редиректа HTTP → HTTPS

**Шаг 3: Проверка**

После настройки проверьте доступность API:

```bash
curl https://api.your-domain.com/
```

**Требования перед запуском:**
- Поддомен должен указывать на IP сервера (A-запись в DNS)
- Порты 80 и 443 должны быть открыты в firewall
- API сервер должен быть запущен на порту 8000

#### Ручная настройка (альтернатива)

Подробные инструкции по ручной настройке HTTPS см. в [HTTPS_SETUP.md](HTTPS_SETUP.md).

**Проверка настройки:**
- API доступен по HTTPS: `https://api.your-domain.com`
- HTTP редиректит на HTTPS: `http://api.your-domain.com` → `https://api.your-domain.com`
- Сертификат валиден: проверьте в браузере или через `certbot certificates`

**Автообновление сертификатов:**
Certbot автоматически настроит обновление сертификатов. Проверить можно командой:

```bash
sudo certbot renew --dry-run
```

**Важно для внешних ботов:**
Если ваш домен проходит через CDN (например, Cloudflare, Akamai), рекомендуется использовать поддомен без CDN или прямой IP адрес. Подробнее см. [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## 📚 API Документация

### Для разработчиков и ботов

**Полная документация API для внешних ботов и приложений:** [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

Документация включает:
- Все endpoints с примерами запросов и ответов
- Примеры кода на Python, JavaScript, cURL
- Примеры интеграции с Telegram ботами
- Рекомендации по обработке ошибок и rate limiting
- Инструкции по настройке подключения (включая работу с поддоменами и CDN)

### Интерактивная документация

После запуска API сервера интерактивная документация доступна по адресу:
- Swagger UI: `http://localhost:8000/docs` (или `https://api.your-domain.com/docs` если настроен HTTPS)
- ReDoc: `http://localhost:8000/redoc` (или `https://api.your-domain.com/redoc` если настроен HTTPS)

### Основные Endpoints

#### Проверка работоспособности API
```bash
GET /
```

Возвращает статус сервиса:
```json
{
  "status": "ok",
  "service": "veil-xray-api"
}
```

#### Создание ключа
```bash
POST /api/keys
Authorization: Bearer YOUR_SECRET_KEY
Content-Type: application/json

{
  "name": "user_name"  # опционально
}
```

Ответ:
```json
{
  "key_id": 1,
  "uuid": "uuid-значение",
  "short_id": "7bb45050",
  "name": "user_name",
  "created_at": 1234567890,
  "is_active": true
}
```

#### Получение информации о ключе
```bash
GET /api/keys/{key_id}
# или
GET /api/keys/{uuid}
Authorization: Bearer YOUR_SECRET_KEY
```

**Примечание:** Endpoint поддерживает как `key_id`, так и `uuid` в качестве идентификатора.

Ответ:
```json
{
  "key_id": 1,
  "uuid": "uuid-значение",
  "short_id": "7bb45050",
  "name": "user_name",
  "created_at": 1234567890,
  "is_active": true
}
```

#### Список всех ключей
```bash
GET /api/keys
Authorization: Bearer YOUR_SECRET_KEY
```

Ответ:
```json
{
  "keys": [
    {
      "key_id": 1,
      "uuid": "uuid-значение",
      "short_id": "7bb45050",
      "name": "user_name",
      "created_at": 1234567890,
      "is_active": true
    }
  ],
  "total": 1
}
```

#### Удаление ключа
```bash
DELETE /api/keys/{key_id}
# или
DELETE /api/keys/{uuid}
Authorization: Bearer YOUR_SECRET_KEY
```

**Примечание:** Endpoint поддерживает как `key_id`, так и `uuid` в качестве идентификатора.

Ответ:
```json
{
  "success": true,
  "message": "Key 1 deleted successfully"
}
```

#### Получение статистики трафика
```bash
GET /api/keys/{key_id}/traffic
Authorization: Bearer YOUR_SECRET_KEY
```

Ответ:
```json
{
  "key_id": 1,
  "upload": 1024000,
  "download": 2048000,
  "total": 3072000,
  "last_updated": 1234567890
}
```

#### Обнуление статистики трафика
```bash
POST /api/keys/{key_id}/traffic/reset
Authorization: Bearer YOUR_SECRET_KEY
```

Обнуление статистики трафика по конкретному ключу.

Ответ:
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

#### Получение VLESS ссылки
```bash
GET /api/keys/{key_id}/link
# или
GET /api/keys/{uuid}/link
Authorization: Bearer YOUR_SECRET_KEY
```

**Примечание:** Endpoint поддерживает как `key_id`, так и `uuid` в качестве идентификатора.

Ответ:
```json
{
  "key_id": 1,
  "vless_link": "vless://..."
}
```

#### Синхронизация статистики трафика
```bash
POST /api/traffic/sync
Authorization: Bearer YOUR_SECRET_KEY
```

Ручная синхронизация статистики трафика для всех активных ключей.

Ответ:
```json
{
  "success": true,
  "message": "Synced 10 keys, 0 errors",
  "updated": 10,
  "errors": 0
}
```

## 🧪 Тестирование

Запуск тестов:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

С покрытием кода:

```bash
pytest tests/ -v --cov=api --cov-report=html
```

**Требования к покрытию:** Минимум 55% покрытия кода (текущее покрытие: ~59%)

## 🔒 Безопасность

- **HTTPS обязателен для production** - используйте Nginx reverse proxy с Let's Encrypt (см. раздел "Настройка HTTPS и поддомена для API")
- Используйте сильный `API_SECRET_KEY` (минимум 32 символа)
- Ограничьте доступ к API через firewall (откройте только порты 80 и 443)
- Настройте rate limiting для защиты от DDoS (рекомендуется использовать `slowapi` или `fastapi-limiter`)
- Регулярно обновляйте Xray-core и зависимости Python
- Храните приватный ключ Reality в безопасности (права доступа 600)
- Не храните секреты в коде или публичных репозиториях

## 📊 Мониторинг трафика

Статистика трафика обновляется автоматически при запросе через API. Данные хранятся в SQLite базе данных и синхронизируются с Xray Stats API.

## 🏗 Структура проекта

```
/
├── api/              # API сервер (FastAPI)
│   ├── main.py      # Основной файл приложения
│   ├── database.py  # Модели базы данных
│   ├── models.py    # Pydantic модели
│   ├── xray_client.py # Клиент Xray API
│   └── utils.py     # Вспомогательные функции
├── config/           # Конфигурационные файлы
│   └── settings.py  # Настройки приложения
├── xray/            # Конфигурация Xray
│   └── config.example.json
├── database/        # SQLite база данных
├── scripts/         # Скрипты развертывания
├── tests/           # Тесты
├── .github/         # GitHub Actions CI/CD
│   └── workflows/
└── requirements.txt # Зависимости Python
```

## 🤝 Вклад

1. Fork проекта
2. Создайте ветку для новой функции (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в ветку (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект распространяется под лицензией MIT.

## 🔗 Полезные ссылки

- [Xray-core Documentation](https://xtls.github.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [VLESS Protocol](https://github.com/XTLS/Xray-core/discussions/716)

## ⚠️ Важные замечания

- Приватный ключ Reality должен храниться в безопасности
- Публичный ключ используется для генерации VLESS ссылок
- SNI и Fingerprint настроены для оптимальной работы с мобильными клиентами
- Dest должен соответствовать SNI для лучшей маскировки трафика

## 📞 Поддержка

При возникновении проблем создайте Issue в репозитории.


