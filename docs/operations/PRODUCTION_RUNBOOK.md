# Production runbook (veil-xray)

Краткие правила эксплуатации production-узла. **Лимиты и примеры .env:** [SERVER_PROFILE.md](SERVER_PROFILE.md). Подробнее: [OPERATIONS.md](../OPERATIONS.md), [load-protection/](load-protection/).

**Текущий узел:** 2 vCPU / 4 GiB · ~100 ключей · veil-xray **1.3.18**.

## Запрещено на production

| Действие | Почему |
|----------|--------|
| **`pytest` / `python -m pytest`** | Пишет в логи, создаёт временные записи в БД; используйте CI или отдельный staging |
| **`stress-mode-nft.sh` без playbook** | Может отрезать новых клиентов на :443 |
| **`git push` в `veilbot`** | Другой репозиторий (Telegram-бот) |

Тесты на prod изолированы в `tests/conftest.py` (`VEIL_SKIP_STARTUP`, отдельный `LOG_FILE`), но **запуск на prod всё равно нежелателен**.

## Осторожно в часы пик (08:00–23:59 MSK)

| Действие | Риск |
|----------|------|
| `POST /api/system/xray/sync-config` | **503 в пик** (автоблок); обход: `VEIL_ALLOW_SYNC_IN_PEAK=1` в env сервиса |
| `systemctl restart veil-xray-api` | Краткий простой API; не делать в пик без необходимости |
| `systemctl restart xray` | Обрыв всех VPN-сессий на 1–2 с — только `./scripts/ops/restart-xray-safe.sh` |

Проверка пика: `scripts/ops/is-peak-msk.sh` (exit 0 = пик).

## TCP tuning (применено на хосте)

Файл: `/etc/sysctl.d/99-veil-tcp.conf` (шаблон в `scripts/load-protection/sysctl-tcp-tuning.conf`), в т.ч. `tcp_max_orphans=16384`. Таблица параметров: [SERVER_PROFILE.md](SERVER_PROFILE.md#5-sysctl-tcp).

## Плановое обслуживание (cron)

Установка: `scripts/ops/install-ops-cron.sh`

| Расписание | Задача |
|------------|--------|
| `* * * * *` | `monitor-baseline.sh` → `/var/log/veil-baseline.log` (+ `fin_wait_443`, `tcp_orphan`) |
| `*/5 * * * *` | `check-slo.sh`, `alert-slo-crit.sh`, `alert-tcp-pressure.sh` (FIN-WAIT crit), `auto-restart-xray-on-tcp.sh` |
| `0 4 * * *` | Ночной рестарт Xray → `/var/log/veil-xray-restart.log` |
| `5 6 * * *` | Отчёт за 1 день → `/var/log/veil-baseline-report.log` |
| `10 6 * * 1` | Отчёт за 7 дней (понедельник) |

**policy:** handshake 4, connIdle 300, bufferSize 256 — `apply-policy-recommended.sh`; пересмотр connIdle через `baseline-report.sh`.

## Снижение посторонней нагрузки

- **Netdata** на prod отключён (`systemctl disable netdata`) — при необходимости: `systemctl enable --now netdata`.
- **Cursor IDE** (remote) потребляет RAM только пока открыта SSH-сессия разработки.

**Рекомендация:** массовый sync и рестарты API — в окно низкой нагрузки (ночь MSK) или после предупреждения пользователей.

## Рутинные операции

```bash
# Здоровье
curl -sS http://127.0.0.1:8000/health
systemctl is-active xray veil-xray-api nginx

# SLO (последняя строка)
tail -1 /var/log/veil-slo.log
/root/veil-xray/scripts/load-protection/check-slo.sh; echo "exit=$?"

# Обновление кода (после настройки deploy key)
cd /root/veil-xray && git pull --ff-only origin main
```

## Деплой

1. [github-deploy.md](github-deploy.md) — SSH deploy key
2. `git pull` → по [CHANGELOG.md](../../CHANGELOG.md) restart сервисов
3. Проверить `/health` и `tail` API-лога на ERROR

## Эскалация при crit SLO

1. `tail -20 /var/log/veil-slo.log` — какая метрика (TCP, xray_rss, MemAvail, load)
2. [08-capacity-decision.md](load-protection/08-capacity-decision.md) — матрица решений
3. Сверить с [SERVER_PROFILE.md](SERVER_PROFILE.md) и [08-capacity-decision.md](load-protection/08-capacity-decision.md); при устойчивом crit — второй узел ([07-scaling.md](load-protection/07-scaling.md)) или тюнинг policy/TCP

## Мониторинг

- Baseline: `/var/log/veil-baseline.log` (каждую минуту)
- SLO: `/var/log/veil-slo.log` (каждые 5 мин)
- Алерт crit: `alert-slo-crit.sh`, FIN-WAIT: `alert-tcp-pressure.sh` + `/etc/veil-slo-alert.env`
