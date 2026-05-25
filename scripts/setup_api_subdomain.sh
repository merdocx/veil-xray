#!/bin/bash
# Скрипт для настройки поддомена для API (например, api.your-domain.com)
# 
# ИСПОЛЬЗОВАНИЕ:
#   1. Отредактируйте переменные SUBDOMAIN и EMAIL ниже
#   2. Запустите: sudo bash scripts/setup_api_subdomain.sh

set -e

# ⚠️ ВАЖНО: Замените на ваш поддомен и email перед запуском!
SUBDOMAIN="api.your-domain.com"  # Замените на ваш поддомен (например, api.example.com)
EMAIL="your-email@example.com"  # Замените на ваш email для Let's Encrypt
SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com)

echo "🔧 Настройка поддомена $SUBDOMAIN для Veil Xray API"
echo ""

# Проверка DNS
echo "📋 Проверка DNS записи для $SUBDOMAIN..."
DNS_IP=$(dig +short $SUBDOMAIN @8.8.8.8 | tail -1)

if [ -z "$DNS_IP" ]; then
    echo "❌ DNS запись для $SUBDOMAIN не найдена!"
    echo ""
    echo "⚠️  Необходимо создать DNS A-запись:"
    echo "   Имя: api"
    echo "   Тип: A"
    echo "   Значение: $SERVER_IP"
    echo "   TTL: 300 (или по умолчанию)"
    echo ""
    echo "После создания DNS записи подождите 5-10 минут для распространения и запустите скрипт снова."
    exit 1
fi

if [ "$DNS_IP" != "$SERVER_IP" ]; then
    echo "⚠️  DNS запись найдена, но указывает на другой IP: $DNS_IP (ожидается: $SERVER_IP)"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ DNS запись найдена: $SUBDOMAIN -> $DNS_IP"
fi

# Определение имени конфигурационного файла из поддомена
CONFIG_NAME=$(echo $SUBDOMAIN | tr '.' '-')
CONFIG_FILE="/etc/nginx/sites-available/$CONFIG_NAME"

# Копирование конфигурации
echo ""
echo "📝 Копирование конфигурации Nginx..."
# Создаем временную конфигурацию с заменой домена
sed "s/api\.veil-bear\.ru/$SUBDOMAIN/g" /root/scripts/nginx-api-subdomain.conf > /tmp/nginx-api-subdomain.conf
sudo cp /tmp/nginx-api-subdomain.conf "$CONFIG_FILE"
sudo ln -sf "$CONFIG_FILE" /etc/nginx/sites-enabled/$CONFIG_NAME
rm -f /tmp/nginx-api-subdomain.conf

# Временная конфигурация для certbot
echo ""
echo "📝 Создание временной конфигурации для получения SSL сертификата..."
sudo tee "$CONFIG_FILE" > /dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $SUBDOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Проверка конфигурации
echo ""
echo "🔍 Проверка конфигурации Nginx..."
sudo nginx -t

# Перезагрузка Nginx
echo ""
echo "🔄 Перезагрузка Nginx..."
sudo systemctl reload nginx

# Получение SSL сертификата
echo ""
echo "🔐 Получение SSL сертификата от Let's Encrypt..."
sudo certbot --nginx -d $SUBDOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

# Проверка доступности
echo ""
echo "✅ Проверка доступности API..."
sleep 2
if curl -s -f https://$SUBDOMAIN/ > /dev/null; then
    echo "✅ API доступен по адресу: https://$SUBDOMAIN"
else
    echo "⚠️  API может быть недоступен. Проверьте вручную: curl https://$SUBDOMAIN/"
fi

echo ""
echo "🎉 Настройка завершена!"
echo ""
echo "📋 Параметры для внешнего бота:"
echo "   API URL: https://$SUBDOMAIN"
echo "   API Key: см. API_SECRET_KEY в /root/.env (не выводится в консоль)"
echo "   V2Ray Path: /usr/local/bin/xray"
echo ""

