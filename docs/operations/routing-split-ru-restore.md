# Восстановление split RU / зарубеж (после режима «всё через relay»)

Сейчас в `config.json` может быть **упрощённый** `routing`: весь трафик `vless-reality` → `upstream` (SOCKS на **релей**), кроме IP релея → `direct`, **UDP/TCP :53** → `direct` (DNS), и `geoip:private` → `block`.

Замените `<RELAY_IP>` в фрагменте ниже на IP **вашего** релея. См. [egress-modes.md](egress-modes.md).

Чтобы **вернуть** разделение (RU `direct`, зарубеж `upstream`, правила Meta и DNS), замените массив `routing.rules` на фрагмент ниже (проверьте `xray -test` и пути `geoip.dat` / `geosite.dat`).

```json
"rules": [
  {
    "type": "field",
    "inboundTag": ["api-in"],
    "outboundTag": "api"
  },
  {
    "type": "field",
    "ip": ["<RELAY_IP>"],
    "outboundTag": "direct"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "domain": [
      "geosite:facebook",
      "geosite:instagram",
      "geosite:meta",
      "geosite:whatsapp",
      "domain:fbcdn.net",
      "domain:fbcdn.com",
      "domain:cdninstagram.com",
      "domain:instagram.com",
      "domain:fb.com",
      "domain:facebook.com",
      "domain:messenger.com",
      "domain:threads.net",
      "domain:whatsapp.com",
      "domain:whatsapp.net",
      "domain:fbsbx.com",
      "domain:facebook.net",
      "domain:igsonar.com",
      "domain:igamecdn.com",
      "domain:c10r.facebook.com",
      "domain:cdn.whatsapp.net"
    ],
    "outboundTag": "upstream"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "domain": ["geosite:category-ru"],
    "outboundTag": "direct"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "ip": ["geoip:facebook"],
    "outboundTag": "upstream"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "ip": ["geoip:ru"],
    "outboundTag": "direct"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "network": "udp",
    "port": "53",
    "outboundTag": "direct"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "network": "tcp",
    "port": "53",
    "outboundTag": "direct"
  },
  {
    "type": "field",
    "inboundTag": ["vless-reality"],
    "outboundTag": "upstream"
  },
  {
    "type": "field",
    "ip": ["geoip:private"],
    "outboundTag": "block"
  }
]
```

Подробности схемы split см. во внутренней документации проекта (план «split RU / foreign»), если он у вас ведётся.
