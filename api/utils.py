"""Вспомогательные функции"""
import uuid
import secrets
import string
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

    # Кодирование в base64
    # Для приватного ключа используем стандартный base64 (для конфигурации Xray)
    private_key_b64 = base64.b64encode(private_bytes).decode("utf-8")
    # Для публичного ключа используем URL-safe base64 (для VLESS ссылок)
    # Это необходимо, так как ключ будет использоваться в URL параметрах
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
    flow: str = "none",
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
    # Формирование параметров
    params = {
        "type": "tcp",
        "security": "reality",
        "sni": sni,
        "fp": fingerprint,
        "pbk": public_key,
        "sid": short_id,
        "spx": "/",
        "flow": flow,
    }

    # Формирование параметров запроса
    query_params = "&".join([f"{k}={v}" for k, v in params.items()])

    # Формирование VLESS ссылки
    vless_link = f"vless://{uuid}@{server_address}:{port}" f"?{query_params}" f"#{dest}"

    return vless_link
