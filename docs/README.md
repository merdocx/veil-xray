# Документация проекта veil-xray

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Установка, быстрый старт, API в общих чертах |
| [OPERATIONS.md](OPERATIONS.md) | **Сервисы, логи, ротация, автозапуск, мониторинг** |
| [../API_DOCUMENTATION.md](../API_DOCUMENTATION.md) | REST API; UX пользователя и интеграция с veilbot |
| [../HTTPS_SETUP.md](../HTTPS_SETUP.md) | HTTPS и Nginx |
| [../CHANGELOG.md](../CHANGELOG.md) | История изменений |
| [operations/egress-modes.md](operations/egress-modes.md) | **Egress: direct / SOCKS / WireGuard, релей на любом сервере** |
| [../xray/README.md](../xray/README.md) | Пример `config.example.json` и теги inbounds |
| [operations/SERVER_PROFILE.md](operations/SERVER_PROFILE.md) | **Эталон лимитов и настроек prod (2 vCPU / 4 GiB)** |
| [operations/RECOMMENDED_SETTINGS.md](operations/RECOMMENDED_SETTINGS.md) | **Рекомендуемые policy, SLO, routing, деплой** |
| [operations/SERVER_REQUIREMENTS.md](operations/SERVER_REQUIREMENTS.md) | **Требования к VPS, мониторинг, автозапуск, logrotate** |
| [operations/FIRST_DEPLOY.md](operations/FIRST_DEPLOY.md) | **Первый деплой на VPS (UFW, Reality, veilbot)** |
| [operations/load-protection/](operations/load-protection/) | SLO, baseline, policy Xray, systemd, stress-mode |
| [operations/routing-split-ru-restore.md](operations/routing-split-ru-restore.md) | Опционально: split RU/foreign (geoip/geosite) |
| [operations/ru-bridge-chain.md](operations/ru-bridge-chain.md) | **Топологии A–E:** база, front relay, egress SOCKS/WG, RU-мост |
| [operations/relay-front-topology.md](operations/relay-front-topology.md) | **E:** пользователь → релей (L4) → VPN → интернет |
| [../scripts/BACKUP_AND_LOGGING.md](../scripts/BACKUP_AND_LOGGING.md) | Бэкапы SQLite и логирование API |
| [../scripts/load-protection/README.md](../scripts/load-protection/README.md) | Скрипты baseline и stress-mode |
