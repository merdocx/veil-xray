# Решение по ёмкости (capacity decision record)

Документ фиксирует **текущее состояние** узла и **варианты** при регулярных `crit` в SLO. Обновляйте после 1–2 недель baseline.

## Текущий профиль (v3091624, 2026-05-26)

| Параметр | Значение |
|----------|----------|
| vCPU / RAM | **2 / 4 GiB** (апгрейд VDSina, после перезагрузки) |
| Активных ключей | ~100 |
| TCP :443 established (типично) | пересмотр baseline после апгрейда |
| Xray RSS | `MemoryMax=1G` |
| SLO | пороги пересмотрены в `slo-thresholds.env` под 2 CPU / 4 GiB |

Пороги: [slo-thresholds.env](../../../scripts/load-protection/slo-thresholds.env). Эталон: [SERVER_PROFILE.md](../SERVER_PROFILE.md). Логи: `/var/log/veil-slo.log`, `/var/log/veil-baseline.log`.

## Критерии выбора варианта

```mermaid
flowchart TD
  start[SLO crit регулярно 1-2 нед]
  q1{Узкое место CPU/RAM/TCP на входе?}
  q2{Бюджет на второй VPS?}
  up[Апгрейд RAM/CPU того же VPS]
  split[Второй входной узел + DNS/LB]
  tune[Тюнинг без железа: TTL traffic sync, окна sync, снижение пиков]
  relay[Проверить релей WG - не заменяет входной CPU]
  start --> q1
  q1 -->|да| q2
  q1 -->|нет| relay
  q2 -->|да| split
  q2 -->|нет| up
  q1 -->|погранично| tune
```

## Варианты (решение)

| Вариант | Когда | Действия |
|---------|-------|----------|
| **A. Тюнинг** | crit эпизодический, дневной пик | Увеличить `traffic_cache_ttl_s`, не вызывать sync-config в пик; baseline 2 нед |
| **B. Апгрейд VPS** | crit >50% проверок 2 нед, 1 узел | 2–4 vCPU, 4 GiB RAM; перенос по playbook хостера |
| **C. Второй узел** | >150–200 ключей или отказоустойчивость | Клон стека, DNS RR / LB, см. [07-scaling.md](07-scaling.md) |
| **D. Снижение нагрузки** | Временная мера | Лимит новых ключей, информирование пользователей о пиках |

## Зафиксированное решение

| Поле | Значение |
|------|----------|
| **Дата решения** | 2026-05-26 |
| **Выбранный вариант** | **B (апгрейд VPS)** — выполнен: 2 vCPU, 4 GiB, 100 GiB, 32 TiB |
| **Обоснование** | На старом 1 vCPU / 2 GiB — FIN-WAIT >> ESTAB, `TCP: too many orphaned sockets`, жалобы «нет интернета». Тюнинг (1.3.15) + апгрейд. |
| **Срок пересмотра** | 2026-06-09 — baseline 7d на новом железе; при стабильном SLO второй узел не нужен до ~150–200 ключей |

## Команды для baseline перед решением

```bash
# Доля crit за последние 7 дней
grep 'level=crit' /var/log/veil-slo.log | wc -l
grep 'level=warn' /var/log/veil-slo.log | wc -l

# Пики TCP и RSS из baseline
awk '/est_tcp/ {print}' /var/log/veil-baseline.log | tail -500
```


## Обновление после внедрения 1.3.15 (2026-05-26)

| Метрика | До правок (пик 26.05) | После правок (днём) |
|---------|----------------------|---------------------|
| TCP ESTAB :443 max | 2888 | ~400–450 типично |
| FIN-WAIT :443 max | 4098 | ~700–800 (всё ещё > ESTAB) |
| connIdle | 1200 → **300** | Xray docs default (2026-05-26 evening) |
| traffic_cache_ttl_s | 1800 | **3600** (меньше SQLite в пик) |
| sync config | 101× save | **1× save** (`bulk_sync_vless_clients`) |

**connIdle:** с **2026-05-26** — **300** (recommended); пересмотр по `baseline-report.sh 7` на **2026-06-09** при обрывах или FIN-WAIT.

**Мониторинг:** `check-slo.sh` + `fin_wait_*`; `alert-tcp-pressure.sh`; опциональный `auto-restart-xray-on-tcp.sh` (3× crit подряд, max 1/h).

## Связанные документы

- [02-monitoring-baseline.md](02-monitoring-baseline.md)
- [07-scaling.md](07-scaling.md)
- [PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md)
