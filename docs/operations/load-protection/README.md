# Операции: гуманная защита от перегрузки (один сервер, один Xray)

Общая сводка: [../../OPERATIONS.md](../../OPERATIONS.md).

**Актуальные лимиты prod (2 vCPU / 4 GiB):** [../SERVER_PROFILE.md](../SERVER_PROFILE.md).

Пошаговые материалы:

| Шаг | Документ |
|-----|----------|
| 1 | [01-slo-template.md](01-slo-template.md) — пустой шаблон |
| 1b | [01-slo-draft-this-host.md](01-slo-draft-this-host.md) — **история:** 1 vCPU / 2 GiB (до апгрейда 2026-05-26) |
| 2 | [02-monitoring-baseline.md](02-monitoring-baseline.md) |
| 3 | [03-xray-policy.md](03-xray-policy.md) |
| 4 | [04-reject-new-connections.md](04-reject-new-connections.md) |
| 5 | [05-systemd-xray.md](05-systemd-xray.md) |
| 6 | [06-ram-swap.md](06-ram-swap.md) |
| 7 | [07-scaling.md](07-scaling.md) |
| 8 | [08-capacity-decision.md](08-capacity-decision.md) — **запись решения по ёмкости** |
| 9 | [09-slo-alerting.md](09-slo-alerting.md) — алерты при crit SLO |

**Скрипты:** [scripts/load-protection/](../../../scripts/load-protection/)

**Runbook:** [../PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md) · **Git deploy:** [../github-deploy.md](../github-deploy.md)

Пример `policy` с таймаутами для уровня пользователей: [xray/config.example.json](../../../xray/config.example.json).
