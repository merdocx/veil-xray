#!/bin/bash
# Скрипт проверки корректности настройки HTTPS после установки

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Проверка настройки HTTPS${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Функция для проверки
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
        return 0
    else
        echo -e "${RED}❌ $1${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

# Получение домена из конфигурации Nginx
NGINX_CONF="/etc/nginx/sites-available/veil-xray-api"
if [ -f "$NGINX_CONF" ]; then
    DOMAIN=$(grep -E "server_name" "$NGINX_CONF" | head -1 | sed -E "s/.*server_name\s+([^;]+);.*/\1/" | tr -d ' ')
    echo -e "${BLUE}📋 Домен из конфигурации Nginx: $DOMAIN${NC}"
else
    warn "Конфигурация Nginx не найдена: $NGINX_CONF"
    exit 1
fi

echo ""

# Проверка конфигурации Nginx
echo -e "${BLUE}🌐 Проверка Nginx...${NC}"
if nginx -t 2>&1 | grep -q "successful"; then
    check "Конфигурация Nginx корректна"
else
    nginx -t
    ERRORS=$((ERRORS + 1))
fi

if systemctl is-active --quiet nginx; then
    check "Nginx запущен"
else
    warn "Nginx не запущен"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Проверка SSL сертификата
echo -e "${BLUE}🔐 Проверка SSL сертификата...${NC}"
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

if [ -f "$CERT_PATH" ]; then
    check "SSL сертификат существует"
    
    if [ -f "$KEY_PATH" ]; then
        check "Приватный ключ существует"
    else
        warn "Приватный ключ не найден: $KEY_PATH"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Проверка срока действия
    if command -v openssl &> /dev/null; then
        EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_PATH" 2>/dev/null | cut -d= -f2)
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || echo "0")
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))
        
        if [ $DAYS_LEFT -gt 30 ]; then
            echo -e "${GREEN}✅ Сертификат действителен еще $DAYS_LEFT дней (до $EXPIRY)${NC}"
        elif [ $DAYS_LEFT -gt 0 ]; then
            warn "Сертификат истекает через $DAYS_LEFT дней (до $EXPIRY)"
        else
            warn "Сертификат истек!"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    warn "SSL сертификат не найден: $CERT_PATH"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Проверка доступности через HTTPS
echo -e "${BLUE}🌍 Проверка доступности через HTTPS...${NC}"
if command -v curl &> /dev/null; then
    # Проверка HTTPS
    HTTPS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://$DOMAIN/" 2>/dev/null || echo "000")
    if [ "$HTTPS_CODE" = "200" ] || [ "$HTTPS_CODE" = "301" ] || [ "$HTTPS_CODE" = "302" ]; then
        check "HTTPS доступен (код: $HTTPS_CODE)"
    else
        warn "HTTPS недоступен (код: $HTTPS_CODE)"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Проверка редиректа HTTP -> HTTPS
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "http://$DOMAIN/" 2>/dev/null || echo "000")
    HTTP_LOCATION=$(curl -s -o /dev/null -w "%{redirect_url}" --max-time 10 "http://$DOMAIN/" 2>/dev/null || echo "")
    
    if [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        if echo "$HTTP_LOCATION" | grep -q "https://"; then
            check "HTTP корректно редиректит на HTTPS"
        else
            warn "HTTP редиректит, но не на HTTPS"
        fi
    else
        warn "HTTP не редиректит на HTTPS (код: $HTTP_CODE)"
    fi
    
    # Проверка SSL
    if echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | grep -q "Verify return code: 0"; then
        check "SSL сертификат валиден"
    else
        warn "SSL сертификат не прошел проверку"
    fi
else
    warn "curl не установлен, пропуск проверки доступности"
fi

echo ""

# Проверка автообновления сертификатов
echo -e "${BLUE}⏰ Проверка автообновления сертификатов...${NC}"
if systemctl is-enabled --quiet certbot.timer 2>/dev/null; then
    check "Certbot timer включен"
else
    warn "Certbot timer не включен"
fi

if systemctl is-active --quiet certbot.timer 2>/dev/null; then
    check "Certbot timer активен"
else
    warn "Certbot timer не активен"
fi

echo ""

# Итоги
echo -e "${BLUE}📊 Итоги проверки:${NC}"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ Все проверки пройдены! HTTPS настроен корректно.${NC}"
    echo ""
    echo -e "${GREEN}🌐 API доступен по адресу: https://$DOMAIN${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Есть предупреждения ($WARNINGS), но HTTPS работает${NC}"
    exit 0
else
    echo -e "${RED}❌ Найдены ошибки ($ERRORS) и предупреждения ($WARNINGS)${NC}"
    echo -e "${YELLOW}Рекомендуется исправить ошибки${NC}"
    exit 1
fi



