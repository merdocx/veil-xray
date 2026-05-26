# systemd: лимиты для Xray (шаг 5)

## Пример drop-in

Файл-пример: [xray.service.d-override.conf.example](../../../scripts/load-protection/systemd/xray.service.d-override.conf.example)

На текущем прод-сервере установлено **`MemoryMax=512M`** по [01-slo-draft-this-host.md](01-slo-draft-this-host.md) (`/etc/systemd/system/xray.service.d/override.conf`).

Установка:

```bash
sudo install -d /etc/systemd/system/xray.service.d
sudo cp xray.service.d-override.conf.example /etc/systemd/system/xray.service.d/override.conf
# Отредактируйте MemoryMax / CPUQuota по графикам базовой линии
sudo systemctl daemon-reload
sudo systemctl restart xray
```

Слишком низкий **MemoryMax** приведёт к OOM kill процесса Xray и обрыву всех клиентов сразу — значение задаётся **выше пика RSS + запас**.

## Имя юнита

Если сервис называется иначе (например `xray@.service`), скорректируйте путь drop-in.
