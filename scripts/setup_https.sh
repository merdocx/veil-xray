#!/bin/bash
# Скрипт для настройки HTTPS для Veil Xray API
# Использует Nginx как reverse proxy и Let's Encrypt для SSL сертификатов

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔒 Настройка HTTPS для Veil Xray API${NC}"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Этот скрипт должен быть запущен от root${NC}"
    exit 1
fi

# Попытка получить домен из настроек
DEFAULT_DOMAIN=""
if [ -f "/root/veil-xray/config/settings.py" ]; then
    DEFAULT_DOMAIN=$(grep -E "domain.*=" /root/veil-xray/config/settings.py | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/" | head -1)
    if [ "$DEFAULT_DOMAIN" = "veil-bear.ru" ]; then
        DEFAULT_DOMAIN=""  # Игнорируем значение по умолчанию
    fi
fi

# Запрос домена
if [ ! -z "$DEFAULT_DOMAIN" ]; then
    read -p "Введите ваш домен [$DEFAULT_DOMAIN]: " DOMAIN
    DOMAIN=${DOMAIN:-$DEFAULT_DOMAIN}
else
    read -p "Введите ваш домен (например, veil-bear.ru): " DOMAIN
fi

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}❌ Домен не может быть пустым${NC}"
    exit 1
fi

# Запрос email для Let's Encrypt
read -p "Введите ваш email для Let's Encrypt (для уведомлений о сертификатах): " EMAIL
if [ -z "$EMAIL" ]; then
    echo -e "${RED}❌ Email не может быть пустым${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📦 Установка зависимостей...${NC}"

# Проверка и установка Nginx
if ! command -v nginx &> /dev/null; then
    echo "Установка Nginx..."
    apt-get update
    apt-get install -y nginx
else
    echo "✅ Nginx уже установлен"
fi

# Проверка и установка certbot
if ! command -v certbot &> /dev/null; then
    echo "Установка Certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
else
    echo "✅ Certbot уже установлен"
fi

echo ""
echo -e "${YELLOW}📝 Создание конфигурации Nginx...${NC}"

# Создание директории для конфигурации
NGINX_CONF_DIR="/etc/nginx/sites-available"
NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
CONF_FILE="$NGINX_CONF_DIR/veil-xray-api"

# Копирование шаблона конфигурации
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/nginx-veil-xray-api.conf"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}❌ Файл шаблона не найден: $TEMPLATE_FILE${NC}"
    exit 1
fi

# Замена домена в шаблоне
sed "s/veil-bear.ru/$DOMAIN/g" "$TEMPLATE_FILE" > "$CONF_FILE"

echo "✅ Конфигурация создана: $CONF_FILE"

# Создание символической ссылки
if [ -L "$NGINX_ENABLED_DIR/veil-xray-api" ]; then
    echo "⚠️  Символическая ссылка уже существует, удаляем..."
    rm "$NGINX_ENABLED_DIR/veil-xray-api"
fi

ln -s "$CONF_FILE" "$NGINX_ENABLED_DIR/veil-xray-api"
echo "✅ Символическая ссылка создана"

# Проверка конфигурации Nginx
echo ""
echo -e "${YELLOW}🔍 Проверка конфигурации Nginx...${NC}"
if nginx -t; then
    echo "✅ Конфигурация Nginx корректна"
else
    echo -e "${RED}❌ Ошибка в конфигурации Nginx${NC}"
    exit 1
fi

# Создание директории для Let's Encrypt challenge
mkdir -p /var/www/html/.well-known/acme-challenge
chown -R www-data:www-data /var/www/html

echo ""
echo -e "${YELLOW}🔐 Получение SSL сертификата от Let's Encrypt...${NC}"
echo "⚠️  Убедитесь, что:"
echo "   1. Домен $DOMAIN указывает на IP этого сервера"
echo "   2. Порты 80 и 443 открыты в firewall"
echo ""
read -p "Продолжить? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Прервано пользователем${NC}"
    exit 0
fi

# Получение сертификата
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ SSL сертификат успешно получен!${NC}"
else
    echo ""
    echo -e "${RED}❌ Ошибка при получении SSL сертификата${NC}"
    echo "Проверьте:"
    echo "  - Домен указывает на правильный IP"
    echo "  - Порты 80 и 443 открыты"
    echo "  - DNS записи корректны"
    exit 1
fi

# Перезагрузка Nginx
echo ""
echo -e "${YELLOW}🔄 Перезагрузка Nginx...${NC}"
systemctl reload nginx
echo "✅ Nginx перезагружен"

# Настройка автообновления сертификатов
echo ""
echo -e "${YELLOW}⏰ Настройка автообновления сертификатов...${NC}"
if [ -f /etc/cron.monthly/certbot ]; then
    echo "✅ Автообновление уже настроено"
else
    # Certbot автоматически создает cron задачу, но проверим
    systemctl enable certbot.timer 2>/dev/null || true
    echo "✅ Автообновление настроено"
fi

echo ""
echo -e "${GREEN}✅ HTTPS успешно настроен!${NC}"
echo ""
echo "📋 Информация:"
echo "   - API доступен по адресу: https://$DOMAIN"
echo "   - HTTP автоматически перенаправляется на HTTPS"
echo "   - Сертификат будет автоматически обновляться"
echo ""
echo "🔧 Полезные команды:"
echo "   - Проверка статуса Nginx: systemctl status nginx"
echo "   - Проверка сертификата: certbot certificates"
echo "   - Обновление сертификата вручную: certbot renew"
echo "   - Просмотр логов Nginx: tail -f /var/log/nginx/veil-xray-api-error.log"
echo ""

