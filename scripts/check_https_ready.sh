#!/bin/bash
# Скрипт проверки готовности к настройке HTTPS

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Проверка готовности к настройке HTTPS${NC}"
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

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  Скрипт запущен не от root. Некоторые проверки могут быть пропущены.${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Проверка наличия домена в настройках
echo -e "${BLUE}📋 Проверка настроек...${NC}"
if [ -f "/root/config/settings.py" ]; then
    DOMAIN=$(grep -E "domain.*=" /root/config/settings.py | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/" | head -1)
    if [ ! -z "$DOMAIN" ] && [ "$DOMAIN" != "veil-bear.ru" ]; then
        echo -e "${GREEN}✅ Домен найден в настройках: $DOMAIN${NC}"
    else
        warn "Домен не найден в настройках или используется значение по умолчанию"
    fi
else
    warn "Файл настроек не найден: /root/config/settings.py"
fi

echo ""

# Проверка DNS
echo -e "${BLUE}🌐 Проверка DNS...${NC}"
if [ ! -z "$DOMAIN" ]; then
    # Получаем IP домена
    DOMAIN_IP=$(dig +short $DOMAIN 2>/dev/null | tail -1)
    if [ ! -z "$DOMAIN_IP" ]; then
        echo -e "${GREEN}✅ DNS запись найдена: $DOMAIN -> $DOMAIN_IP${NC}"
        
        # Получаем IP сервера
        SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "")
        if [ ! -z "$SERVER_IP" ]; then
            if [ "$DOMAIN_IP" = "$SERVER_IP" ]; then
                echo -e "${GREEN}✅ Домен указывает на IP этого сервера ($SERVER_IP)${NC}"
            else
                warn "Домен указывает на другой IP ($DOMAIN_IP), а не на IP сервера ($SERVER_IP)"
            fi
        else
            warn "Не удалось определить IP сервера"
        fi
    else
        warn "DNS запись для домена $DOMAIN не найдена"
    fi
else
    warn "Домен не определен, пропуск проверки DNS"
fi

echo ""

# Проверка портов
echo -e "${BLUE}🔌 Проверка портов...${NC}"
if command -v netstat &> /dev/null; then
    PORT_80=$(netstat -tln 2>/dev/null | grep ":80 " || true)
    PORT_443=$(netstat -tln 2>/dev/null | grep ":443 " || true)
    
    if [ ! -z "$PORT_80" ]; then
        echo -e "${GREEN}✅ Порт 80 слушается${NC}"
    else
        warn "Порт 80 не слушается (может быть закрыт firewall)"
    fi
    
    if [ ! -z "$PORT_443" ]; then
        echo -e "${GREEN}✅ Порт 443 слушается${NC}"
    else
        warn "Порт 443 не слушается (может быть закрыт firewall)"
    fi
elif command -v ss &> /dev/null; then
    PORT_80=$(ss -tln 2>/dev/null | grep ":80 " || true)
    PORT_443=$(ss -tln 2>/dev/null | grep ":443 " || true)
    
    if [ ! -z "$PORT_80" ]; then
        echo -e "${GREEN}✅ Порт 80 слушается${NC}"
    else
        warn "Порт 80 не слушается (может быть закрыт firewall)"
    fi
    
    if [ ! -z "$PORT_443" ]; then
        echo -e "${GREEN}✅ Порт 443 слушается${NC}"
    else
        warn "Порт 443 не слушается (может быть закрыт firewall)"
    fi
else
    warn "Не удалось проверить порты (netstat/ss не найдены)"
fi

echo ""

# Проверка firewall
echo -e "${BLUE}🔥 Проверка firewall...${NC}"
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1 || echo "inactive")
    if echo "$UFW_STATUS" | grep -q "active"; then
        echo -e "${GREEN}✅ UFW активен${NC}"
        UFW_80=$(ufw status | grep "80/tcp" || true)
        UFW_443=$(ufw status | grep "443/tcp" || true)
        
        if [ ! -z "$UFW_80" ]; then
            echo -e "${GREEN}✅ Порт 80 открыт в UFW${NC}"
        else
            warn "Порт 80 не открыт в UFW"
        fi
        
        if [ ! -z "$UFW_443" ]; then
            echo -e "${GREEN}✅ Порт 443 открыт в UFW${NC}"
        else
            warn "Порт 443 не открыт в UFW"
        fi
    else
        warn "UFW не активен"
    fi
else
    warn "UFW не установлен (проверьте iptables вручную)"
fi

echo ""

# Проверка API сервера
echo -e "${BLUE}🚀 Проверка API сервера...${NC}"
API_PORT=$(netstat -tln 2>/dev/null | grep ":8000 " || ss -tln 2>/dev/null | grep ":8000 " || true)
if [ ! -z "$API_PORT" ]; then
    echo -e "${GREEN}✅ API сервер слушает порт 8000${NC}"
    
    # Проверка доступности API
    if command -v curl &> /dev/null; then
        API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
        if [ "$API_RESPONSE" = "200" ]; then
            echo -e "${GREEN}✅ API сервер отвечает на запросы${NC}"
        else
            warn "API сервер не отвечает корректно (код: $API_RESPONSE)"
        fi
    fi
else
    warn "API сервер не слушает порт 8000"
fi

echo ""

# Проверка Nginx
echo -e "${BLUE}🌐 Проверка Nginx...${NC}"
if command -v nginx &> /dev/null; then
    echo -e "${GREEN}✅ Nginx установлен${NC}"
    
    # Проверка конфигурации
    if nginx -t 2>/dev/null; then
        echo -e "${GREEN}✅ Конфигурация Nginx корректна${NC}"
    else
        warn "Конфигурация Nginx содержит ошибки"
    fi
    
    # Проверка статуса
    if systemctl is-active --quiet nginx 2>/dev/null; then
        echo -e "${GREEN}✅ Nginx запущен${NC}"
    else
        warn "Nginx не запущен"
    fi
else
    warn "Nginx не установлен"
fi

echo ""

# Проверка Certbot
echo -e "${BLUE}🔐 Проверка Certbot...${NC}"
if command -v certbot &> /dev/null; then
    echo -e "${GREEN}✅ Certbot установлен${NC}"
    
    # Проверка сертификатов
    if [ ! -z "$DOMAIN" ]; then
        CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
        if [ -f "$CERT_PATH" ]; then
            echo -e "${GREEN}✅ SSL сертификат для $DOMAIN уже существует${NC}"
            
            # Проверка срока действия
            if command -v openssl &> /dev/null; then
                EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_PATH" 2>/dev/null | cut -d= -f2)
                echo -e "${GREEN}✅ Сертификат действителен до: $EXPIRY${NC}"
            fi
        else
            echo -e "${YELLOW}ℹ️  SSL сертификат для $DOMAIN еще не получен${NC}"
        fi
    fi
else
    warn "Certbot не установлен"
fi

echo ""

# Итоги
echo -e "${BLUE}📊 Итоги проверки:${NC}"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ Все проверки пройдены! Можно запускать setup_https.sh${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Есть предупреждения ($WARNINGS), но можно продолжать${NC}"
    exit 0
else
    echo -e "${RED}❌ Найдены ошибки ($ERRORS) и предупреждения ($WARNINGS)${NC}"
    echo -e "${YELLOW}Рекомендуется исправить ошибки перед настройкой HTTPS${NC}"
    exit 1
fi



