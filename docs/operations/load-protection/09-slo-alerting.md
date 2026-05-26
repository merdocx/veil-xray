# SLO alerting (crit)

## Компоненты

| Файл | Назначение |
|------|------------|
| `scripts/load-protection/check-slo.sh` | Метрики → `/var/log/veil-slo.log`, exit `2` = crit |
| `scripts/load-protection/alert-slo-crit.sh` | `logger` + опционально webhook/email |
| `scripts/load-protection/slo-alert.env.example` | Шаблон `/etc/veil-slo-alert.env` |

## Установка cron (root)

```cron
*/5 * * * * /root/veil-v2ray/scripts/load-protection/check-slo.sh
*/5 * * * * /root/veil-v2ray/scripts/load-protection/alert-slo-crit.sh
```

Проверка:

```bash
/root/veil-v2ray/scripts/load-protection/check-slo.sh; echo check_exit=$?
journalctl -t veil-slo --since "10 min ago" --no-pager
```

## Опциональный webhook

```bash
sudo cp /root/veil-v2ray/scripts/load-protection/slo-alert.env.example /etc/veil-slo-alert.env
sudo chmod 600 /etc/veil-slo-alert.env
# отредактировать SLO_ALERT_WEBHOOK_URL
```

Дедупликация: повтор алерта не чаще **30 минут** при непрерывном crit (`/var/lib/veil-slo-alert.state`).

## Baseline перед сменой порогов

1–2 недели не менять `slo-thresholds.env` без анализа `/var/log/veil-baseline.log` и доли `crit` в `veil-slo.log` (см. [08-capacity-decision.md](08-capacity-decision.md)).
