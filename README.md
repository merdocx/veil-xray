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

- Python 3.10+
- Xray-core (последняя стабильная версия)
- Linux (Ubuntu/Debian)
- Домен с настроенным DNS (veil-bear.ru)

## 🛠 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/merdocx/veil-xray.git
cd veil-xray
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Генерация ключей Reality

```bash
python scripts/init_reality_keys.py
```

Сохраните приватный ключ для конфигурации Xray и публичный ключ для настроек API.

### 4. Настройка конфигурации

Скопируйте пример конфигурации и настройте:

```bash
cp config/settings.py.example config/settings.py
# Отредактируйте config/settings.py с вашими настройками
```

Или создайте файл `.env`:

```env
API_SECRET_KEY=your-secret-key-here
REALITY_PUBLIC_KEY=your-public-key-here
REALITY_PRIVATE_KEY=your-private-key-here
DATABASE_URL=sqlite:///./database/veil_xray.db
XRAY_API_HOST=127.0.0.1
XRAY_API_PORT=10085
```

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

```bash
python -m api.main
```

Или с помощью uvicorn:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Для production используйте systemd или supervisor:

```ini
[Unit]
Description=Veil Xray API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/veil-xray
ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📚 API Документация

После запуска API сервера документация доступна по адресу:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Основные Endpoints

#### Создание ключа
```bash
POST /api/keys
Authorization: Bearer YOUR_SECRET_KEY
Content-Type: application/json

{
  "name": "user_name"  # опционально
}
```

#### Удаление ключа
```bash
DELETE /api/keys/{key_id}
Authorization: Bearer YOUR_SECRET_KEY
```

#### Получение статистики трафика
```bash
GET /api/keys/{key_id}/traffic
Authorization: Bearer YOUR_SECRET_KEY
```

#### Получение VLESS ссылки
```bash
GET /api/keys/{key_id}/link
Authorization: Bearer YOUR_SECRET_KEY
```

#### Список всех ключей
```bash
GET /api/keys
Authorization: Bearer YOUR_SECRET_KEY
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

## 🔒 Безопасность

- Используйте сильный `API_SECRET_KEY`
- Настройте HTTPS для API (Nginx/Caddy reverse proxy)
- Ограничьте доступ к API через firewall
- Регулярно обновляйте Xray-core
- Храните приватный ключ Reality в безопасности

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

