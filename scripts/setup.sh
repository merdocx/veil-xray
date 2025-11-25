#!/bin/bash
# Скрипт для первоначальной настройки проекта

set -e

echo "Setting up Veil Xray project..."

# Создание директорий
mkdir -p database
mkdir -p logs

# Копирование .env.example в .env если его нет
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your settings!"
fi

# Генерация ключей Reality если их нет
if [ ! -f config/reality_keys.txt ]; then
    echo "Generating Reality keys..."
    python3 scripts/init_reality_keys.py
    echo "Please add the keys to your .env file and Xray config!"
fi

echo "Setup complete!"
echo "Next steps:"
echo "1. Edit .env file with your settings"
echo "2. Configure Xray with the private key"
echo "3. Start Xray service"
echo "4. Run: python -m api.main"


