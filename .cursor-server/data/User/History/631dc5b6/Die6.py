"""Тесты для утилит"""
from api.utils import generate_uuid, generate_short_id, build_vless_link


def test_generate_uuid():
    """Тест генерации UUID"""
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    
    assert uuid1 != uuid2
    assert len(uuid1) == 36  # Стандартная длина UUID
    assert uuid1.count("-") == 4


def test_generate_short_id():
    """Тест генерации Short ID"""
    short_id1 = generate_short_id(8)
    short_id2 = generate_short_id(8)
    
    assert short_id1 != short_id2
    assert len(short_id1) == 8
    assert short_id1.isalnum() or all(c in '0123456789abcdef' for c in short_id1.lower())


def test_build_vless_link():
    """Тест построения VLESS ссылки"""
    uuid = "123e4567-e89b-12d3-a456-426614174000"
    short_id = "abcd1234"
    server_address = "veil-bear.ru"
    port = 443
    sni = "microsoft.com"
    fingerprint = "chrome"
    public_key = "test_public_key"
    dest = "www.microsoft.com:443"
    
    link = build_vless_link(
        uuid=uuid,
        short_id=short_id,
        server_address=server_address,
        port=port,
        sni=sni,
        fingerprint=fingerprint,
        public_key=public_key,
        dest=dest
    )
    
    assert link.startswith("vless://")
    assert uuid in link
    assert server_address in link
    assert str(port) in link
    assert short_id in link
    assert sni in link
    assert fingerprint in link
    assert public_key in link

