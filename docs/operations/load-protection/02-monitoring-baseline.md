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
/root/veil-v2ray/scripts/ops/install-ops-cron.sh
```

Файл `/etc/cron.d/veil-xray`: baseline, SLO, nightly Xray restart, daily/weekly `baseline-report.sh`.

Отчёт вручную: `scripts/load-protection/baseline-report.sh 7`

## Продакшен (текущий хост)

Полный перечень юнитов и путей к логам: [../../OPERATIONS.md](../../OPERATIONS.md).

На сервере с репозиторием в `/root/veil-v2ray` дополнительно настроено:

| Компонент | Состояние |
|-----------|-----------|
| **Netdata** | Установлен из пакета Ubuntu; веб **только на `127.0.0.1:19999`** (не торчит в интернет). Доступ с ноутбука: `ssh -L 19999:127.0.0.1:19999 root@<IP>` → браузер `http://127.0.0.1:19999`. В **Applications** процесс **xray** попадает в группу **vpn** (`/etc/netdata/apps_groups.conf`). |
| **Baseline cron** | Root crontab: раз в минуту `monitor-baseline.sh` → **`/var/log/veil-baseline.log`**. |
| **Ротация лога** | `/etc/logrotate.d/veil-baseline` (еженедельно, 8 архивов). |
