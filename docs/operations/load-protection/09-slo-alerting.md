# SLO alerting (crit и FIN-WAIT)

Актуальные пороги: [slo-thresholds.env](../../../scripts/load-protection/slo-thresholds.env), таблица — [SERVER_PROFILE.md](../SERVER_PROFILE.md#6-slo-и-пороги).

## Компоненты

| Файл | Назначение |
|------|------------|
| `check-slo.sh` | Метрики → `/var/log/veil-slo.log`, exit `2` = crit |
| `alert-slo-crit.sh` | Любой crit → `logger` + webhook |
| `alert-tcp-pressure.sh` | Crit с `fin_wait` / `fin_wait_ratio` в reasons |
| `slo-alert.env.example` | Шаблон `/etc/veil-slo-alert.env` |

## Cron (prod)

Установка одной командой:

```bash
/root/veil-v2ray/scripts/ops/install-ops-cron.sh
```

В `/etc/cron.d/veil-xray` (каждые 5 мин):

- `check-slo.sh`
- `alert-slo-crit.sh`
- `alert-tcp-pressure.sh`
- `auto-restart-xray-on-tcp.sh` (рестарт Xray при устойчивом FIN-WAIT, max 1×/ч)

Проверка:

```bash
/root/veil-v2ray/scripts/load-protection/check-slo.sh; echo check_exit=$?
tail -1 /var/log/veil-slo.log
journalctl -t veil-slo --since "10 min ago" --no-pager
journalctl -t veil-tcp --since "10 min ago" --no-pager
```

## Webhook

```bash
sudo cp /root/veil-v2ray/scripts/load-protection/slo-alert.env.example /etc/veil-slo-alert.env
sudo chmod 600 /etc/veil-slo-alert.env
# SLO_ALERT_WEBHOOK_URL=https://...
```

Дедупликация: повтор не чаще **30 мин** (`SLO_ALERT_REPEAT_MIN`, state в `/var/lib/veil-slo-alert.state` и `/var/lib/veil-tcp-alert.state`).

## Пересмотр порогов

1–2 недели baseline на **новом железе** (2 CPU / 4 GiB) перед изменением чисел — см. [08-capacity-decision.md](08-capacity-decision.md) (пересмотр **2026-06-09**).
