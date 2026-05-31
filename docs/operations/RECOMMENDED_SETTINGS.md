# Рекомендуемые настройки (prod)

**Актуально:** 2026-05-31 · Xray **26.x** · ~100 ключей · пример: вход **`<VPN_PUBLIC_IP>`** → egress через **релей** (WireGuard; `<RELAY_HOST>` — свой)

Единая шпаргалка по значениям из [Xray Policy](https://xtls.github.io/en/config/policy.html) и практик VLESS+Reality (2026). Эталон на сервере: [SERVER_PROFILE.md](SERVER_PROFILE.md).

---

## 1. Клиент (VLESS ссылка)

| Параметр | Значение |
|----------|----------|
| `type` | `tcp` |
| `security` | `reality` |
| `flow` | `xtls-rprx-vision` |
| `fp` | `chrome` (или fingerprint браузера на устройстве) |
| `sni` | `microsoft.com` (как на сервере) |
| `sid` | общий `REALITY_COMMON_SHORT_ID` (напр. `7bb45050`) |
| Порт | `443` |

Перед продакшеном: `xray run -test -config config.json` на сервере.

---

## 2. Xray `policy.levels."0"`

| Поле | Рекомендуемое | Применение |
|------|---------------|------------|
| `handshake` | **4** с | `apply-policy-recommended.sh` |
| `connIdle` | **300** с | то же; при обрывах idle → 600–900; при FIN-WAIT ↑ — не поднимать без baseline |
| `uplinkOnly` | **2** с | то же |
| `downlinkOnly` | **5** с | то же |
| `bufferSize` | **256** KiB | то же |
| `statsUserUplink` / `statsUserDownlink` | **true** | нужно API статистики |

```bash
/root/veil-xray/scripts/load-protection/apply-policy-recommended.sh
systemctl restart xray   # краткий обрыв у всех клиентов
```

Переопределение (разово):

```bash
POLICY_CONN_IDLE=600 /root/veil-xray/scripts/load-protection/apply-policy-recommended.sh
```

---

## 3. Маршрутизация (egress)

Релей — **любой** сервер; см. [egress-modes.md](egress-modes.md). На **входных** узлах с WG (пример в [SERVER_PROFILE.md](SERVER_PROFILE.md)):

| Правило | Outbound |
|---------|----------|
| `vless-reality` (весь трафик) | **`wg-egress`** (`freedom` + `sockopt.mark` **119** / `0x77`) |
| DNS :53 с inbound | `wg-egress` |
| IP релея (`RELAY_IP`) | `direct` (анти-петля) |
| `geoip:private` | `block` |

Проверка egress (WG):

```bash
curl -4 --interface wg0 https://api.ipify.org   # ожидается публичный IP релея, не входного узла
```

Шаблон SOCKS: `xray/config.example.json`. Edge без релея: только `direct` в `routing`.

---

## 4. Sysctl (`/etc/sysctl.d/99-veil-tcp.conf`)

Шаблон: [scripts/load-protection/sysctl-tcp-tuning.conf](../../scripts/load-protection/sysctl-tcp-tuning.conf)

| Параметр | Значение |
|----------|----------|
| `tcp_max_syn_backlog` / `somaxconn` | 8192 |
| `tcp_fin_timeout` | 30 |
| `tcp_max_orphans` | 16384 |
| `vm.swappiness` | 10 |

---

## 5. SLO и авто-рестарт TCP

Источник: [scripts/load-protection/slo-thresholds.env](../../scripts/load-protection/slo-thresholds.env)

| Метрика | Warn | Crit |
|---------|------|------|
| `load1 / ncpu` | 1.0 | 3.0 |
| MemAvailable | &lt; 1.5 GiB | &lt; 1 GiB |
| RSS xray | &gt; 512 MiB | &gt; 768 MiB |
| TCP ESTAB :443 | 2500 | 4000 |
| FIN-WAIT :443 | **500** | **800** |
| FIN-WAIT/ESTAB % | 150% | 250% (только если ESTAB ≥ 100) |

Авто-рестарт Xray: `FIN_WAIT_443` &gt; **800** три раза подряд (cron */5), не чаще 1×/час — [auto-restart-xray-on-tcp.sh](../../scripts/ops/auto-restart-xray-on-tcp.sh).

---

## 6. API / `.env` (фрагмент)

```env
REALITY_FLOW=xtls-rprx-vision
REALITY_COMMON_SHORT_ID=<REALITY_COMMON_SHORT_ID>
TRAFFIC_CACHE_TTL_S=3600
ENABLE_BACKGROUND_TRAFFIC_SYNC=true
BACKGROUND_TRAFFIC_SYNC_INTERVAL_S=600
```

Пик MSK 08:00–23:59: `POST /api/system/xray/sync-config` → **503** без `VEIL_ALLOW_SYNC_IN_PEAK=1`.

---

## 7. Деплой и git

```bash
cd /root/veil-xray
/root/veil-xray/scripts/ops/git-with-credentials.sh pull --ff-only origin main
/root/veil-xray/scripts/ops/deploy-prod.sh
```

См. [github-deploy.md](github-deploy.md), [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md).

---

## 8. Чего избегать

- Рестарт Xray/API днём без необходимости
- `pytest` на prod
- `stress-mode-nft.sh` без playbook
- Деплой целого `config.json` из example поверх prod без проверки WG/routing
- Порог FIN-WAIT 2500+ для алертов (проблема начинается раньше)
