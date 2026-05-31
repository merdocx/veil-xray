"""Тесты генерации client-config."""

from api.utils import (
    build_auto_singbox_subscription_config,
    build_client_config,
    build_auto_subscription_links,
)
from config.settings import settings


def test_build_client_config_four_outbounds(monkeypatch):
    monkeypatch.setattr(settings, "reality_sni_b", None)
    monkeypatch.setattr(settings, "reality_public_key_b", None)
    monkeypatch.setattr(settings, "reality_private_key_b", None)

    cfg = build_client_config(
        key_id=1,
        uuid="00000000-0000-4000-8000-000000000001",
        public_key="test_public_key",
    )

    proxy_tags = [
        o["tag"] for o in cfg["outbounds"] if o.get("protocol") in ("vless", "trojan")
    ]
    assert "fast_vless_tcp" in proxy_tags
    assert "fast_vless_tcp_alt" in proxy_tags
    assert "fast_trojan_tcp" in proxy_tags
    assert "fast_vless_xhttp" in proxy_tags
    assert len(proxy_tags) == 4

    assert cfg["burstObservatory"]["subjectSelector"] == proxy_tags

    balancer = next(b for b in cfg["routing"]["balancers"] if b["tag"] == "fast-all")
    assert balancer["strategy"]["type"] == "leastPing"
    assert set(balancer["selector"]) == {
        "fast_vless_tcp",
        "fast_vless_tcp_alt",
        "fast_trojan_tcp",
        "fast_vless_xhttp",
    }


def test_build_client_config_includes_sni_b(monkeypatch):
    monkeypatch.setattr(settings, "reality_sni_b", "cloudflare.com")
    monkeypatch.setattr(settings, "reality_public_key_b", "pk_b")
    monkeypatch.setattr(settings, "reality_private_key_b", "sk_b")

    cfg = build_client_config(
        key_id=2,
        uuid="00000000-0000-4000-8000-000000000002",
        public_key="pk_a",
        public_key_b="pk_b",
    )

    proxy_tags = [
        o["tag"] for o in cfg["outbounds"] if o.get("protocol") in ("vless", "trojan")
    ]
    assert "fast_vless_tcp_sni_b" in proxy_tags
    assert len(proxy_tags) == 5


def test_build_auto_subscription_single_happ_port(monkeypatch):
    monkeypatch.setattr(settings, "domain", "vpn.example.com")
    links = build_auto_subscription_links(
        uuid="00000000-0000-4000-8000-000000000099",
        public_key="pk_test",
    )
    assert len(links) == 1
    assert ":448" in links[0]


def test_build_auto_singbox_urltest_when_sni_b(monkeypatch):
    monkeypatch.setattr(settings, "domain", "vpn.example.com")
    monkeypatch.setattr(settings, "reality_sni_b", "cloudflare.com")
    monkeypatch.setattr(settings, "reality_public_key_b", "pk_b")
    monkeypatch.setattr(settings, "reality_private_key_b", "sk_b")

    cfg = build_auto_singbox_subscription_config(
        uuid="00000000-0000-4000-8000-000000000099",
        public_key="pk_a",
        public_key_b="pk_b",
    )
    urltest = next((o for o in cfg["outbounds"] if o.get("type") == "urltest"), None)
    assert urltest is not None
    assert urltest["tag"] == "proxy"
    assert set(urltest["outbounds"]) == {"member-448", "member-447"}

