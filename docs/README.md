# Документация проекта veil-v2ray

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Установка, быстрый старт, API в общих чертах |
| [OPERATIONS.md](OPERATIONS.md) | **Сервисы, логи, ротация, автозапуск, мониторинг** |
| [../API_DOCUMENTATION.md](../API_DOCUMENTATION.md) | Полное описание REST API |
| [../HTTPS_SETUP.md](../HTTPS_SETUP.md) | HTTPS и Nginx |
| [../TZ.md](../TZ.md) | Техническое задание (если есть) |
| [../CHANGELOG.md](../CHANGELOG.md) | История изменений |
| [operations/SERVER_PROFILE.md](operations/SERVER_PROFILE.md) | **Эталон лимитов и настроек prod (2 vCPU / 4 GiB)** |
| [operations/load-protection/](operations/load-protection/) | SLO, baseline, policy Xray, systemd, stress-mode |
| [operations/routing-split-ru-restore.md](operations/routing-split-ru-restore.md) | Восстановление split RU/foreign после режима «всё через relay» |
| [operations/routing-all-via-relay.md](operations/routing-all-via-relay.md) | Аудит: весь трафик через релей и допустимые исключения |
| [../scripts/BACKUP_AND_LOGGING.md](../scripts/BACKUP_AND_LOGGING.md) | Бэкапы SQLite и логирование API |
| [../scripts/README_HTTPS.md](../scripts/README_HTTPS.md) | Скрипты проверки/настройки HTTPS |
| [../scripts/load-protection/README.md](../scripts/load-protection/README.md) | Скрипты baseline и stress-mode |
