# Front relay (вариант E)

L4-проброс TCP с **front relay** на **veil-xray backend** (пользователь → релей → VPN → интернет).

| Файл | Назначение |
|------|------------|
| [nginx-stream-l4.conf.example](nginx-stream-l4.conf.example) | nginx `stream`: порты 443, 446–448, 8445, 2085 → backend |

Полный runbook: [docs/operations/relay-front-topology.md](../../docs/operations/relay-front-topology.md).

**Не путать** с egress-релеем (SOCKS/WG после VPN): [docs/operations/egress-modes.md](../../docs/operations/egress-modes.md).
