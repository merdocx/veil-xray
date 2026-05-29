# RAM и swap (шаг 6)

## Текущий prod (4 GiB)

| Параметр | Типичное значение |
|----------|-------------------|
| MemTotal | ~3.8 GiB |
| MemAvailable | **2.5–2.9 GiB** (вне пика) |
| Swap | 1 GiB, обычно **не используется** |
| `vm.swappiness` | **10** (`99-veil-tcp.conf`) |
| Xray `MemoryMax` | **1G** |

SLO: warn если MemAvailable **&lt; 1.5 GiB**, crit **&lt; 1 GiB** — см. [SERVER_PROFILE.md](../SERVER_PROFILE.md).

## Чеклист

1. Сверить с [SERVER_PROFILE.md](../SERVER_PROFILE.md) и `/var/log/veil-baseline.log`.
2. Проверить `vm.swappiness` — на VPN-хосте держим **10**, не 60–100.
3. Убрать постороннюю нагрузку (IDE на prod, лишние демоны).
4. При стабильном swap &gt; 0 и crit по MemAvail — уже апгрейдили до 4 GiB; дальше — policy/`connIdle` или второй узел ([07-scaling.md](07-scaling.md)).

## Скрипт

[check-ram-swap.sh](../../../scripts/load-protection/check-ram-swap.sh) — краткая сводка для ручного аудита.

```bash
/root/veil-xray/scripts/load-protection/check-ram-swap.sh
free -h
```
