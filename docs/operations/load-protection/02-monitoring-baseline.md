# Мониторинг и базовая линия (шаг 2)

## Варианты стека

1. **Netdata** — быстрый старт, графики CPU/RAM/процессов из коробки.
2. **Prometheus + node_exporter + Grafana** — гибче, дольше настройка.
3. **Минимум:** скрипт [../../../scripts/load-protection/monitor-baseline.sh](../../../scripts/load-protection/monitor-baseline.sh) по **cron** (раз в минуту), лог для последующего разбора.

## Что смотреть

- CPU по ядрам; на VPS — **steal time**.
- RAM: **MemAvailable**, не только `free`.
- Диск: место и **iowait** (если логи или БД на том же диске).
- Сеть: трафик и **drops** на интерфейсе (`ip -s link`).
- Процесс **xray**: CPU и RSS.

## Базовая линия

Соберите **несколько дней** нормальной работы: пики по времени суток, типичный load при ожидаемом числе пользователей.

**Выход:** понимание, что упирается первым (CPU xray, память, диск, сеть) — от этого зависят настройки policy (шаг 3) и systemd (шаг 5).

## Минимальный cron

```bash
/root/veil-xray/scripts/ops/install-ops-cron.sh
```

Файл `/etc/cron.d/veil-xray`: baseline, SLO, nightly Xray restart, daily/weekly `baseline-report.sh`.

Отчёт вручную: `scripts/load-protection/baseline-report.sh 7`

## Продакшен (текущий хост, 2 vCPU / 4 GiB)

Эталон метрик и cron: [../SERVER_PROFILE.md](../SERVER_PROFILE.md). Сводка: [../../OPERATIONS.md](../../OPERATIONS.md).

| Компонент | Состояние |
|-----------|-----------|
| **Baseline** | `/etc/cron.d/veil-xray` → `monitor-baseline.sh` → `/var/log/veil-baseline.log` (1 мин). Поля: `est_tcp_sport_443`, `fin_wait_443`, `tcp_orphan`, `xray_rss_kb`, … |
| **SLO** | `check-slo.sh` каждые 5 мин → `/var/log/veil-slo.log` |
| **Отчёты** | `baseline-report.sh 1` (06:05), `7` (пн 06:10) |
| **Ротация** | `/etc/logrotate.d/veil-ops` (slo, baseline, restart-логи) |
| **Netdata** | **Отключён** на prod (`systemctl disable netdata`) — опционально: `enable`, доступ `ssh -L 19999:127.0.0.1:19999 root@<IP>` |
