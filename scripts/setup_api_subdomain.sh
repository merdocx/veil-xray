#!/bin/bash
# Скрипт для настройки поддомена api.veil-bear.ru для API

set -e

SUBDOMAIN="api.veil-bear.ru"
EMAIL="admin@veil-bear.ru"
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

# Копирование конфигурации
echo ""
echo "📝 Копирование конфигурации Nginx..."
sudo cp /root/scripts/nginx-api-subdomain.conf /etc/nginx/sites-available/api-veil-bear
sudo ln -sf /etc/nginx/sites-available/api-veil-bear /etc/nginx/sites-enabled/api-veil-bear

# Временная конфигурация для certbot
echo ""
echo "📝 Создание временной конфигурации для получения SSL сертификата..."
sudo tee /etc/nginx/sites-available/api-veil-bear > /dev/null <<EOF
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
echo "   API Key: $(grep API_SECRET_KEY /root/.env | cut -d'=' -f2)"
echo "   V2Ray Path: /usr/local/bin/xray"
echo ""

