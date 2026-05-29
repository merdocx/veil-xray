"""Вспомогательные функции"""

import uuid
import secrets
import string
import re
from typing import Any, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
import base64
from config.settings import settings


def generate_uuid() -> str:
    """Генерация UUID для VLESS"""
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """Генерация Short ID для Reality (hex, 8 символов)"""
    return secrets.token_hex(length // 2)


def generate_reality_keys():
    """
    Генерация пары ключей для Reality (публичный и приватный)

    Returns:
        tuple: (public_key, private_key) в формате base64
    """
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Сериализация приватного ключа
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Сериализация публичного ключа
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )

    # Кодирование как в `xray x25519`: base64.RawURLEncoding без padding (иначе Xray: invalid privateKey)
    private_key_b64 = (
        base64.urlsafe_b64encode(private_bytes).decode("utf-8").rstrip("=")
    )
    public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode("utf-8").rstrip("=")

    return public_key_b64, private_key_b64


def build_vless_link(
    uuid: str,
    short_id: str,
    server_address: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    dest: str,
    flow: Optional[str] = None,
) -> str:
    """
    Построение VLESS ссылки для клиента

    Args:
        uuid: UUID пользователя
        short_id: Short ID для Reality
        server_address: Адрес сервера
        port: Порт сервера
        sni: SNI (Server Name Indication)
        fingerprint: Fingerprint для TLS
        public_key: Публичный ключ Reality
        dest: Dest (сайт-приманка)
        flow: Flow для VLESS

    Returns:
        VLESS ссылка в формате vless://...
    """
    return build_vless_link_with_transport(
        uuid=uuid,
        short_id=short_id,
        server_address=server_address,
        port=port,
        sni=sni,
        fingerprint=fingerprint,
        public_key=public_key,
        flow=flow,
        transport="tcp",
        path="/",
        remark=dest,
    )

def build_vless_link_with_transport(
    *,
    uuid: str,
    short_id: str,
    server_address: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    transport: str,
    path: str,
    remark: str,
    flow: Optional[str] = None,
) -> str:
    """
    Универсальное построение VLESS ссылки (tcp / xhttp и т.п.).

    Примечание: `remark` кладём в fragment (#...), чтобы в клиентах он отображался как имя профиля.
    """
    if flow is not None:
        flow_val = flow
    elif transport == "tcp":
        flow_val = settings.reality_flow
    else:
        flow_val = ""
    # Happ (sing-box) ожидает encryption=none; для tcp без spx/path (spx ломает часть клиентов)
    params: dict[str, str] = {
        "encryption": "none",
        "security": "reality",
        "sni": sni,
        "fp": fingerprint,
        "pbk": public_key,
        "sid": short_id,
        "type": transport,
    }

    if transport == "xhttp" and path:
        params["path"] = path

    if flow_val and flow_val.lower() != "none":
        params["flow"] = flow_val

    query_params = "&".join([f"{k}={v}" for k, v in params.items()])

    # Формирование VLESS ссылки
    vless_link = (
        f"vless://{uuid}@{server_address}:{port}" f"?{query_params}" f"#{remark}"
    )

    return vless_link


def build_trojan_reality_link(
    *,
    password: str,
    server_address: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    short_id: str,
    path: str,
    remark: str,
) -> str:
    """
    Построение Trojan+REALITY ссылки.

    Большинство клиентов понимают формат:
    trojan://password@host:port?type=tcp&security=reality&sni=...&fp=...&pbk=...&sid=...&spx=/...
    """
    params: dict[str, str] = {
        "encryption": "none",
        "type": "tcp",
        "security": "reality",
        "sni": sni,
        "fp": fingerprint,
        "pbk": public_key,
        "sid": short_id,
    }
    query_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"trojan://{password}@{server_address}:{port}" f"?{query_params}" f"#{remark}"


def parse_key_identifier(identifier: str) -> Tuple[Optional[str], Optional[int], bool]:
    """
    Определение типа идентификатора ключа (UUID или key_id)

    Args:
        identifier: Идентификатор ключа (может быть UUID или key_id)

    Returns:
        Кортеж (uuid, key_id, is_uuid):
        - uuid: UUID строка, если identifier является UUID, иначе None
        - key_id: Целое число, если identifier является key_id, иначе None
        - is_uuid: True если это UUID, False если key_id

    Raises:
        ValueError: Если формат идентификатора неверный
    """
    # UUID содержит дефисы и имеет формат: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    if "-" in identifier:
        # Проверяем, является ли это валидным UUID
        if uuid_pattern.match(identifier):
            return identifier, None, True
        else:
            raise ValueError(f"Invalid UUID format: {identifier}")
    else:
        # Пытаемся преобразовать в key_id
        try:
            key_id = int(identifier)
            if key_id <= 0:
                raise ValueError(f"key_id must be positive, got: {key_id}")
            return None, key_id, False
        except ValueError:
            raise ValueError(
                f"Invalid identifier format: {identifier}. Expected UUID or positive integer key_id"
            )


def normalize_reality_public_key(public_key: str) -> str:
    """Привести pbk к URL-safe base64 без padding (как ожидает Xray-клиент)."""
    try:
        if "/" in public_key or "+" in public_key or public_key.endswith("="):
            decoded = base64.b64decode(
                public_key + "==" if not public_key.endswith("=") else public_key
            )
            return base64.urlsafe_b64encode(decoded).decode("utf-8").rstrip("=")
    except Exception:
        pass
    return public_key


def _client_sockopt() -> dict[str, Any]:
    return {
        "tcpFastOpen": True,
        "tcpKeepAliveInterval": 15,
        "tcpNoDelay": True,
    }


def build_client_vless_tcp_outbound(
    *,
    tag: str,
    uuid: str,
    domain: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    short_id: str,
    flow: str,
) -> dict[str, Any]:
    """VLESS+REALITY TCP outbound для client-config."""
    return {
        "protocol": "vless",
        "tag": tag,
        "settings": {
            "vnext": [
                {
                    "address": domain,
                    "port": port,
                    "users": [
                        {
                            "id": uuid,
                            "encryption": "none",
                            "flow": flow,
                        }
                    ],
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "fingerprint": fingerprint,
                "publicKey": public_key,
                "serverName": sni,
                "shortId": short_id,
            },
            "sockopt": _client_sockopt(),
        },
    }


def build_client_trojan_tcp_outbound(
    *,
    tag: str,
    uuid: str,
    domain: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    short_id: str,
) -> dict[str, Any]:
    """Trojan+REALITY TCP outbound для client-config."""
    return {
        "protocol": "trojan",
        "tag": tag,
        "settings": {
            "servers": [
                {
                    "address": domain,
                    "port": port,
                    "password": str(uuid),
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "fingerprint": fingerprint,
                "publicKey": public_key,
                "serverName": sni,
                "shortId": short_id,
            },
            "sockopt": _client_sockopt(),
        },
    }


def build_client_vless_xhttp_outbound(
    *,
    tag: str,
    uuid: str,
    domain: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    short_id: str,
    xhttp_path: str,
) -> dict[str, Any]:
    """VLESS+REALITY XHTTP outbound для client-config."""
    return {
        "protocol": "vless",
        "tag": tag,
        "settings": {
            "vnext": [
                {
                    "address": domain,
                    "port": port,
                    "users": [{"id": uuid, "encryption": "none"}],
                }
            ]
        },
        "streamSettings": {
            "network": "xhttp",
            "security": "reality",
            "realitySettings": {
                "fingerprint": fingerprint,
                "publicKey": public_key,
                "serverName": sni,
                "shortId": short_id,
            },
            "sockopt": _client_sockopt(),
            "xhttpSettings": {"mode": "stream-one", "path": xhttp_path},
        },
    }


def build_client_config(
    *,
    key_id: int,
    uuid: str,
    public_key: str,
    public_key_b: Optional[str] = None,
) -> dict[str, Any]:
    """
    Полный клиентский JSON: 4+ outbounds, burstObservatory, balancers.
    """
    tag_vless_tcp = "fast_vless_tcp"
    tag_vless_tcp_alt = "fast_vless_tcp_alt"
    tag_trojan = "fast_trojan_tcp"
    tag_vless_xhttp = "fast_vless_xhttp"
    tag_vless_sni_b = "fast_vless_tcp_sni_b"

    proxy_outbounds: list[dict[str, Any]] = [
        build_client_vless_tcp_outbound(
            tag=tag_vless_tcp,
            uuid=uuid,
            domain=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            short_id=settings.reality_common_short_id,
            flow=settings.reality_flow,
        ),
        build_client_vless_tcp_outbound(
            tag=tag_vless_tcp_alt,
            uuid=uuid,
            domain=settings.domain,
            port=settings.reality_alt_port_tcp,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            short_id=settings.reality_common_short_id,
            flow=settings.reality_flow,
        ),
        build_client_trojan_tcp_outbound(
            tag=tag_trojan,
            uuid=uuid,
            domain=settings.domain,
            port=settings.trojan_reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            short_id=settings.reality_common_short_id,
        ),
        build_client_vless_xhttp_outbound(
            tag=tag_vless_xhttp,
            uuid=uuid,
            domain=settings.domain,
            port=settings.reality_xhttp_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            short_id=settings.reality_common_short_id,
            xhttp_path=settings.reality_xhttp_path,
        ),
    ]

    observatory_tags = [tag_vless_tcp, tag_vless_tcp_alt, tag_trojan, tag_vless_xhttp]
    all_proxy_selector = list(observatory_tags)

    if settings.reality_sni_b_enabled and public_key_b:
        proxy_outbounds.append(
            build_client_vless_tcp_outbound(
                tag=tag_vless_sni_b,
                uuid=uuid,
                domain=settings.domain,
                port=settings.reality_port_sni_b,
                sni=settings.reality_sni_b,  # type: ignore[arg-type]
                fingerprint=settings.reality_fingerprint_b_value,
                public_key=public_key_b,
                short_id=settings.reality_short_id_b,
                flow=settings.reality_flow,
            )
        )
        observatory_tags.append(tag_vless_sni_b)
        all_proxy_selector.append(tag_vless_sni_b)

    return {
        "remarks": f"[Auto] {settings.domain} key_{key_id}",
        "log": {"loglevel": "warning"},
        "dns": {
            "queryStrategy": "UseIPv4",
            "servers": [
                {
                    "address": "https+local://77.88.8.8/dns-query",
                    "domains": ["regexp:.*\\.ru$", "regexp:.*\\.su$"],
                    "queryStrategy": "UseIPv4",
                },
                {
                    "address": "https+local://1.1.1.1/dns-query",
                    "queryStrategy": "UseIPv4",
                },
            ],
        },
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10808,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {
                    "enabled": True,
                    "routeOnly": True,
                    "destOverride": ["http", "tls", "quic"],
                },
                "tag": "socks",
            },
            {
                "listen": "127.0.0.1",
                "port": 10809,
                "protocol": "http",
                "settings": {"allowTransparent": False},
                "sniffing": {
                    "enabled": True,
                    "routeOnly": True,
                    "destOverride": ["http", "tls", "quic"],
                },
                "tag": "http",
            },
        ],
        "burstObservatory": {
            "pingConfig": {
                "destination": "https://connectivitycheck.gstatic.com/generate_204",
                "httpMethod": "HEAD",
                "interval": "360s",
                "sampling": 3,
                "timeout": "5s",
            },
            "subjectSelector": observatory_tags,
        },
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
            *proxy_outbounds,
        ],
        "policy": {
            "levels": {
                "0": {
                    "bufferSize": 4,
                    "connIdle": 600,
                    "downlinkOnly": 60,
                    "handshake": 8,
                    "uplinkOnly": 30,
                }
            }
        },
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "balancers": [
                {
                    "tag": "fast-all",
                    "selector": all_proxy_selector,
                    "strategy": {"type": "leastPing"},
                },
            ],
            "rules": [
                {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"},
                {
                    "type": "field",
                    "ip": [
                        "127.0.0.0/8",
                        "10.0.0.0/8",
                        "172.16.0.0/12",
                        "192.168.0.0/16",
                        "169.254.0.0/16",
                        "::1/128",
                        "fc00::/7",
                        "fe80::/10",
                    ],
                    "outboundTag": "direct",
                },
                {
                    "type": "field",
                    "domain": [
                        "localhost",
                        "*.local",
                        "*.localdomain",
                        "*.lan",
                        "*.internal",
                    ],
                    "outboundTag": "direct",
                },
                {
                    "type": "field",
                    "balancerTag": "fast-all",
                    "network": "tcp,udp",
                },
            ],
        },
    }


def _singbox_vless_outbound(
    *,
    tag: str,
    uuid: str,
    port: int,
    sni: str,
    fingerprint: str,
    public_key: str,
    short_id: str,
) -> dict[str, Any]:
    return {
        "type": "vless",
        "tag": tag,
        "server": settings.domain,
        "server_port": port,
        "uuid": uuid,
        "packet_encoding": "xudp",
        "tls": {
            "enabled": True,
            "server_name": sni,
            "utls": {"enabled": True, "fingerprint": fingerprint},
            "reality": {
                "enabled": True,
                "public_key": public_key,
                "short_id": short_id,
            },
        },
    }


def build_auto_subscription_links(
    *,
    uuid: str,
    public_key: str,
    public_key_b: Optional[str] = None,
) -> list[str]:
    """
    Набор ссылок для подписки с автовыбором в клиенте (urltest / ping).
    Без Trojan и XHTTP+flow — ломают Happ на iOS.
    """
    sid = settings.reality_common_short_id
    lines = [
        build_vless_link_with_transport(
            uuid=uuid,
            short_id=sid,
            server_address=settings.domain,
            port=settings.reality_happ_port_tcp,
            sni=settings.reality_sni,
            fingerprint="ios",
            public_key=public_key,
            flow="",
            transport="tcp",
            path="/",
            remark="auto_448",
        ),
        build_vless_link_with_transport(
            uuid=uuid,
            short_id=sid,
            server_address=settings.domain,
            port=settings.reality_alt_port_tcp,
            sni=settings.reality_sni,
            fingerprint="ios",
            public_key=public_key,
            flow="",
            transport="tcp",
            path="/",
            remark="auto_446",
        ),
        build_vless_link_with_transport(
            uuid=uuid,
            short_id=sid,
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint="chrome",
            public_key=public_key,
            flow=settings.reality_flow,
            transport="tcp",
            path="/",
            remark="auto_443",
        ),
    ]
    if public_key_b and settings.reality_sni_b:
        lines.append(
            build_vless_link_with_transport(
                uuid=uuid,
                short_id=settings.reality_short_id_b,
                server_address=settings.domain,
                port=settings.reality_port_sni_b,
                sni=settings.reality_sni_b,
                fingerprint="ios",
                public_key=public_key_b,
                flow="",
                transport="tcp",
                path="/",
                remark="auto_447",
            )
        )
    return lines


def build_auto_singbox_subscription_config(
    *,
    uuid: str,
    public_key: str,
    public_key_b: Optional[str] = None,
) -> dict[str, Any]:
    """
    sing-box профиль: несколько outbounds + urltest (автовыбор по задержке) для Happ/iOS.
    """
    sid = settings.reality_common_short_id
    proxy_tags = ["auto_448", "auto_446"]
    proxy_outbounds: list[dict[str, Any]] = [
        _singbox_vless_outbound(
            tag="auto_448",
            uuid=uuid,
            port=settings.reality_happ_port_tcp,
            sni=settings.reality_sni,
            fingerprint="ios",
            public_key=public_key,
            short_id=sid,
        ),
        _singbox_vless_outbound(
            tag="auto_446",
            uuid=uuid,
            port=settings.reality_alt_port_tcp,
            sni=settings.reality_sni,
            fingerprint="ios",
            public_key=public_key,
            short_id=sid,
        ),
    ]
    if public_key_b and settings.reality_sni_b:
        proxy_tags.append("auto_447")
        proxy_outbounds.append(
            _singbox_vless_outbound(
                tag="auto_447",
                uuid=uuid,
                port=settings.reality_port_sni_b,
                sni=settings.reality_sni_b,
                fingerprint="ios",
                public_key=public_key_b,
                short_id=settings.reality_short_id_b,
            )
        )

    return {
        "log": {"disabled": False, "level": "warn"},
        "dns": {
            "servers": [
                {"tag": "dns-proxy", "address": "8.8.8.8", "detour": "auto"},
                {"tag": "dns-local", "address": "local"},
                {"tag": "fakeip", "address": "fakeip"},
            ],
            "rules": [{"query_type": ["A", "AAAA"], "server": "fakeip"}],
            "final": "dns-proxy",
            "strategy": "ipv4_only",
            "independent_cache": True,
        },
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "inet4_address": "172.19.0.1/30",
                "mtu": 1400,
                "auto_route": True,
                "strict_route": True,
                "stack": "system",
                "sniff": True,
                "sniff_override_destination": True,
            }
        ],
        "outbounds": [
            *proxy_outbounds,
            {"type": "direct", "tag": "direct"},
            {"type": "dns", "tag": "dns-out"},
            {"type": "block", "tag": "block"},
            {
                "type": "urltest",
                "tag": "auto",
                "outbounds": proxy_tags,
                "url": "https://connectivitycheck.gstatic.com/generate_204",
                "interval": "5m",
                "tolerance": 100,
            },
        ],
        "route": {
            "rules": [
                {"protocol": "dns", "outbound": "dns-out"},
                {"ip_is_private": True, "outbound": "direct"},
            ],
            "final": "auto",
            "auto_detect_interface": True,
        },
    }


def build_happ_singbox_config(*, uuid: str, public_key: str) -> dict[str, Any]:
    """Алиас: полный auto-профиль с urltest."""
    public_key_b = None
    if settings.reality_sni_b_enabled and settings.reality_public_key_b:
        public_key_b = normalize_reality_public_key(settings.reality_public_key_b)
    return build_auto_singbox_subscription_config(
        uuid=uuid, public_key=public_key, public_key_b=public_key_b
    )
