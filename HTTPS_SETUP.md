# Настройка HTTPS для Veil Xray API

Этот документ содержит инструкции по настройке HTTPS для Veil Xray API с использованием Nginx reverse proxy и Let's Encrypt SSL сертификатов.

## 🎯 Цель

Настроить безопасное HTTPS соединение для API, чтобы:
- Защитить передачу `API_SECRET_KEY` и других данных
- Соответствовать современным стандартам безопасности
- Обеспечить доверие пользователей

## ⚡ Быстрая настройка

### Шаг 1: Проверка готовности

Перед настройкой HTTPS рекомендуется проверить готовность системы:

```bash
sudo bash scripts/check_https_ready.sh
```

Скрипт проверит:
- Настройки домена
- DNS записи
- Открытость портов 80 и 443
- Статус firewall
- Доступность API сервера
- Установку Nginx и Certbot

### Шаг 2: Автоматическая установка (рекомендуется)

```bash
sudo bash scripts/setup_https.sh
```

Скрипт запросит:
- Домен (автоматически подставит из настроек, если доступен)
- Email для Let's Encrypt

### Шаг 3: Проверка после установки

После установки проверьте корректность настройки:

```bash
sudo bash scripts/verify_https.sh
```

Скрипт проверит:
- Конфигурацию Nginx
- SSL сертификат и срок действия
- Доступность через HTTPS
- Корректность редиректа HTTP -> HTTPS
- Настройку автообновления сертификатов

### Требования перед запуском

1. ✅ Домен настроен и указывает на IP сервера (A-запись)
2. ✅ Порты 80 и 443 открыты в firewall
3. ✅ API сервер запущен на порту 8000

## 📋 Ручная настройка

### Шаг 1: Установка зависимостей

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### Шаг 2: Копирование конфигурации

```bash
sudo cp scripts/nginx-veil-xray-api.conf /etc/nginx/sites-available/veil-xray-api
sudo ln -s /etc/nginx/sites-available/veil-xray-api /etc/nginx/sites-enabled/
```

### Шаг 3: Редактирование конфигурации

Откройте файл конфигурации:

```bash
sudo nano /etc/nginx/sites-available/veil-xray-api
```

Замените `your-domain.example` (или плейсхолдер в шаблоне) на ваш домен:
- В блоке `server_name` для HTTP (порт 80)
- В блоке `server_name` для HTTPS (порт 443)

### Шаг 4: Проверка конфигурации

```bash
sudo nginx -t
```

Если все корректно, вы увидите:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Шаг 5: Получение SSL сертификата

```bash
sudo certbot --nginx -d your-domain.com --non-interactive --agree-tos --email your-email@example.com --redirect
```

Certbot автоматически:
- Получит сертификат от Let's Encrypt
- Обновит конфигурацию Nginx
- Настроит редирект HTTP → HTTPS

### Шаг 6: Перезагрузка Nginx

```bash
sudo systemctl reload nginx
```

### Шаг 7: Проверка

1. Откройте в браузере: `https://your-domain.com`
2. Проверьте, что HTTP редиректит на HTTPS: `http://your-domain.com` → `https://your-domain.com`
3. Проверьте сертификат в браузере (должен быть валидным)

## 🔧 Управление сертификатами

### Проверка сертификатов

```bash
sudo certbot certificates
```

### Обновление сертификатов вручную

```bash
sudo certbot renew
```

### Тестовое обновление (dry-run)

```bash
sudo certbot renew --dry-run
```

### Автоматическое обновление

Certbot автоматически настроит обновление сертификатов через systemd timer. Проверить статус:

```bash
sudo systemctl status certbot.timer
```

## 🛠 Устранение проблем

### Проблема: Certbot не может получить сертификат

**Причины:**
- Домен не указывает на IP сервера
- Порты 80/443 закрыты в firewall
- Nginx не запущен

**Решение:**
1. Проверьте DNS: `dig your-domain.com` или `nslookup your-domain.com`
2. Проверьте firewall: `sudo ufw status` или `sudo iptables -L`
3. Проверьте Nginx: `sudo systemctl status nginx`

### Проблема: Nginx не запускается

**Проверьте:**
```bash
sudo nginx -t  # Проверка синтаксиса
sudo journalctl -u nginx -n 50  # Логи Nginx
```

### Проблема: API недоступен через HTTPS

**Проверьте:**
1. API сервер запущен: `sudo systemctl status veil-xray-api`
2. Порт 8000 слушается: `sudo netstat -tlnp | grep 8000`
3. Логи Nginx: `sudo tail -f /var/log/nginx/veil-xray-api-error.log`

### Проблема: HTTP не редиректит на HTTPS

**Решение:**
Убедитесь, что в конфигурации Nginx есть блок редиректа:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## 📊 Мониторинг

### Логи Nginx

```bash
# Access log
sudo tail -f /var/log/nginx/veil-xray-api-access.log

# Error log
sudo tail -f /var/log/nginx/veil-xray-api-error.log
```

### Статус сервисов

```bash
# Nginx
sudo systemctl status nginx

# API сервер
sudo systemctl status veil-xray-api

# Certbot timer
sudo systemctl status certbot.timer
```

## 🔒 Дополнительная безопасность

### Настройка firewall

```bash
# Разрешить только HTTP и HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp  # Закрыть прямой доступ к API
```

### Ограничение доступа к API

В конфигурации Nginx можно добавить ограничения по IP:

```nginx
location / {
    # Разрешить только определенные IP
    allow 1.2.3.4;
    deny all;
    
    proxy_pass http://127.0.0.1:8000;
    # ... остальные настройки
}
```

## 📝 Конфигурация Nginx

Основные настройки безопасности в конфигурации:

- **TLS 1.2 и 1.3** - современные протоколы
- **HSTS** - HTTP Strict Transport Security
- **Безопасные cipher suites** - только проверенные алгоритмы
- **X-Frame-Options** - защита от clickjacking
- **X-Content-Type-Options** - защита от MIME sniffing

## ✅ Чеклист после настройки

- [ ] HTTPS работает: `https://your-domain.com`
- [ ] HTTP редиректит на HTTPS
- [ ] Сертификат валиден (проверено в браузере)
- [ ] API доступен через HTTPS
- [ ] Автообновление сертификатов настроено
- [ ] Firewall настроен (порты 80, 443 открыты, 8000 закрыт)
- [ ] Логирование работает

## 🔗 Полезные ссылки

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u nginx -n 100`
2. Проверьте конфигурацию: `sudo nginx -t`
3. Создайте Issue в репозитории с описанием проблемы

