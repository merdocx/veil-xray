# systemd: лимиты для Xray (шаг 5)

## Текущий prod

| Параметр | Значение |
|----------|----------|
| `MemoryMax` | **1G** |
| Файл | `/etc/systemd/system/xray.service.d/override.conf` |
| Хост | 4 GiB RAM, 2 vCPU |

Сводка: [SERVER_PROFILE.md](../SERVER_PROFILE.md#2-сервисы-systemd).

## Пример drop-in

Файл-пример: [xray.service.d-override.conf.example](../../../scripts/load-protection/systemd/xray.service.d-override.conf.example)

```ini
[Service]
MemoryMax=1G
Restart=on-failure
RestartSec=3
```

Установка:

```bash
sudo install -d /etc/systemd/system/xray.service.d
sudo cp /root/veil-xray/scripts/load-protection/systemd/xray.service.d-override.conf.example \
  /etc/systemd/system/xray.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart xray
```

### Ориентиры по RAM хоста

| RAM хоста | Рекомендуемый MemoryMax для Xray |
|-----------|----------------------------------|
| ~2 GiB | 512M (исторически) |
| **4 GiB** | **1G** (текущий prod) |
| 8 GiB | 1.5G–2G (при росте числа клиентов) |

Слишком низкий **MemoryMax** → OOM kill Xray и обрыв всех VPN. Задавайте **выше пика RSS + запас** по `veil-baseline.log` / `check-slo.sh`.

## Имя юнита

Если сервис называется иначе (например `xray@.service`), скорректируйте путь drop-in.
