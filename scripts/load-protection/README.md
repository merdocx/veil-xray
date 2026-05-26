# Скрипты: защита от перегрузки

| Скрипт | Назначение |
|--------|------------|
| `slo-thresholds.env` | Числовые пороги SLO (load, RAM, RSS xray, TCP :443) |
| `check-slo.sh` | Сравнение с порогами → `/var/log/veil-slo.log` (cron раз в 5 мин) |
| `alert-slo-crit.sh` | Алерт в syslog (+ webhook) при exit 2 от check-slo |
| `slo-alert.env.example` | Шаблон `/etc/veil-slo-alert.env` |
| `monitor-baseline.sh` | Лог метрик раз в минуту (cron), шаг 2 |
| `stress-mode-nft.sh` | Опционально: DROP новых TCP на порт Xray, шаг 4 |
| `check-ram-swap.sh` | Краткий аудит RAM/swap, шаг 6 |
| `systemd/xray.service.d-override.conf.example` | Пример лимитов для юнита Xray, шаг 5 |

Документация: [docs/operations/load-protection/](../../docs/operations/load-protection/README.md).
