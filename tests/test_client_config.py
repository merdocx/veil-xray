"""Тесты генерации client-config."""

from api.utils import build_client_config
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
        o["tag"]
        for o in cfg["outbounds"]
        if o.get("protocol") in ("vless", "trojan")
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
        o["tag"]
        for o in cfg["outbounds"]
        if o.get("protocol") in ("vless", "trojan")
    ]
    assert "fast_vless_tcp_sni_b" in proxy_tags
    assert len(proxy_tags) == 5
