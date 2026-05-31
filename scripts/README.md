# Скрипты

| Назначение | Документ / каталог |
|------------|-------------------|
| Резервное копирование БД, логи API | [BACKUP_AND_LOGGING.md](BACKUP_AND_LOGGING.md) |
| Пример logrotate для `backup.log` | [logrotate/veil-xray-backup-log.example](logrotate/veil-xray-backup-log.example) |
| HTTPS | [HTTPS_SETUP.md](../HTTPS_SETUP.md); шаблоны `nginx-veil-xray-api.conf`, `nginx-api-prod-http-ip.conf`, `nginx-api-subdomain.conf` |
| Мониторинг нагрузки, baseline, stress-mode | [load-protection/README.md](load-protection/README.md) |
| Проверка egress через SOCKS-релей | `verify-egress-via-relay.sh` |
| Front relay (L4, вариант E) | [relay/README.md](relay/README.md) |
| Systemd unit-шаблоны | `veil-xray-api.service`, `xray.service` |

Общая эксплуатация: [../docs/OPERATIONS.md](../docs/OPERATIONS.md).
