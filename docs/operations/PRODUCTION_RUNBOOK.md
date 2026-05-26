# Production runbook (veil-xray)

Краткие правила эксплуатации production-узла. Подробнее: [OPERATIONS.md](../OPERATIONS.md), [load-protection/](load-protection/).

## Запрещено на production

| Действие | Почему |
|----------|--------|
| **`pytest` / `python -m pytest`** | Пишет в логи, создаёт временные записи в БД; используйте CI или отдельный staging |
| **`stress-mode-nft.sh` без playbook** | Может отрезать новых клиентов на :443 |
| **`git push` в `veilbot`** | Другой репозиторий (Telegram-бот) |

Тесты на prod изолированы в `tests/conftest.py` (`VEIL_SKIP_STARTUP`, отдельный `LOG_FILE`), но **запуск на prod всё равно нежелателен**.

## Осторожно в часы пик

| Действие | Риск |
|----------|------|
| `POST /api/system/xray/sync-config` | Запускает фоновый sync (~14 с на 101 ключ); не дублировать, пока `GET .../sync-status` = `running` |
| `systemctl restart veil-xray-api` | Блокирующий startup sync до готовности |
| `systemctl restart xray` | Обрыв активных VPN-сессий |

**Рекомендация:** массовый sync и рестарты API — в окно низкой нагрузки (ночь MSK) или после предупреждения пользователей.

## Рутинные операции

```bash
# Здоровье
curl -sS http://127.0.0.1:8000/health
systemctl is-active xray veil-xray-api nginx

# SLO (последняя строка)
tail -1 /var/log/veil-slo.log
/root/veil-v2ray/scripts/load-protection/check-slo.sh; echo "exit=$?"

# Обновление кода (после настройки deploy key)
cd /root/veil-v2ray && git pull --ff-only origin main
```

## Деплой

1. [github-deploy.md](github-deploy.md) — SSH deploy key
2. `git pull` → по [CHANGELOG.md](../../CHANGELOG.md) restart сервисов
3. Проверить `/health` и `tail` API-лога на ERROR

## Эскалация при crit SLO

1. `tail -20 /var/log/veil-slo.log` — какая метрика (TCP, xray_rss, MemAvail, load)
2. [08-capacity-decision.md](load-protection/08-capacity-decision.md) — матрица решений
3. При устойчивом crit > 1–2 нед — апгрейд VPS или второй узел ([07-scaling.md](load-protection/07-scaling.md))

## Мониторинг

- Baseline: `/var/log/veil-baseline.log` (каждую минуту)
- SLO: `/var/log/veil-slo.log` (каждые 5 мин)
- Алерт crit: `alert-slo-crit.sh` + опционально `/etc/veil-slo-alert.env`
