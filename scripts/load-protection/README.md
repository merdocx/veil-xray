# Скрипты: защита от перегрузки

**Пороги и cron для текущего prod:** [docs/operations/SERVER_PROFILE.md](../../docs/operations/SERVER_PROFILE.md).

| Скрипт | Назначение |
|--------|------------|
| `slo-thresholds.env` | Пороги SLO (2 vCPU / 4 GiB, ~100 ключей) |
| `check-slo.sh` | Сравнение с порогами → `/var/log/veil-slo.log` (5 мин) |
| `alert-slo-crit.sh` | Алерт при любом crit |
| `alert-tcp-pressure.sh` | Алерт при crit по FIN-WAIT |
| `slo-alert.env.example` | Шаблон `/etc/veil-slo-alert.env` |
| `monitor-baseline.sh` | Метрики раз в минуту → `veil-baseline.log` |
| `baseline-report.sh` | Отчёт за N дней из baseline |
| `apply-policy-recommended.sh` | Policy levels.0 по Xray docs (handshake, connIdle, buffer) |
| `sysctl-tcp-tuning.conf` | Шаблон `/etc/sysctl.d/99-veil-tcp.conf` |
| `logrotate-veil-ops.example` | Ротация `/var/log/veil-*.log` |
| `stress-mode-nft.sh` | Аварийный DROP новых TCP :443 |
| `check-ram-swap.sh` | Аудит RAM/swap |
| `systemd/xray.service.d-override.conf.example` | `MemoryMax=1G` |

**Ops (cron):** [../ops/install-ops-cron.sh](../ops/install-ops-cron.sh), [../ops/auto-restart-xray-on-tcp.sh](../ops/auto-restart-xray-on-tcp.sh), [../ops/cron-nightly-xray-restart.sh](../ops/cron-nightly-xray-restart.sh).

Документация: [docs/operations/load-protection/](../../docs/operations/load-protection/README.md).
