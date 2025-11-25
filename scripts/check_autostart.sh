#!/bin/bash
# Скрипт для проверки настроек автозапуска

echo "=========================================="
echo "Проверка настроек автозапуска"
echo "=========================================="
echo ""

echo "1. Статус сервисов:"
echo "   Xray:"
systemctl is-enabled xray >/dev/null 2>&1 && echo "     ✅ Автозапуск включен" || echo "     ❌ Автозапуск выключен"
systemctl is-active xray >/dev/null 2>&1 && echo "     ✅ Сервис запущен" || echo "     ❌ Сервис не запущен"

echo ""
echo "   API:"
systemctl is-enabled veil-xray-api >/dev/null 2>&1 && echo "     ✅ Автозапуск включен" || echo "     ❌ Автозапуск выключен"
systemctl is-active veil-xray-api >/dev/null 2>&1 && echo "     ✅ Сервис запущен" || echo "     ❌ Сервис не запущен"

echo ""
echo "2. Процессы:"
if pgrep -f "/usr/local/bin/xray" >/dev/null; then
    echo "   ✅ Xray процесс запущен (PID: $(pgrep -f '/usr/local/bin/xray'))"
else
    echo "   ❌ Xray процесс не найден"
fi

if pgrep -f "uvicorn api.main:app" >/dev/null; then
    echo "   ✅ API процесс запущен (PID: $(pgrep -f 'uvicorn api.main:app'))"
else
    echo "   ❌ API процесс не найден"
fi

echo ""
echo "3. Проверка доступности:"
if curl -s http://localhost:8000/ >/dev/null 2>&1; then
    echo "   ✅ API сервер отвечает"
else
    echo "   ❌ API сервер не отвечает"
fi

echo ""
echo "4. Service файлы:"
if [ -f /etc/systemd/system/xray.service ]; then
    echo "   ✅ /etc/systemd/system/xray.service существует"
else
    echo "   ❌ /etc/systemd/system/xray.service не найден"
fi

if [ -f /etc/systemd/system/veil-xray-api.service ]; then
    echo "   ✅ /etc/systemd/system/veil-xray-api.service существует"
else
    echo "   ❌ /etc/systemd/system/veil-xray-api.service не найден"
fi

echo ""
echo "=========================================="
echo "Итог:"
if systemctl is-enabled xray >/dev/null 2>&1 && systemctl is-enabled veil-xray-api >/dev/null 2>&1; then
    echo "✅ Автозапуск настроен для обоих сервисов"
    echo "   Сервисы будут автоматически запускаться при загрузке системы"
else
    echo "❌ Автозапуск не настроен полностью"
    echo "   Выполните: sudo systemctl enable xray veil-xray-api"
fi
echo "=========================================="

