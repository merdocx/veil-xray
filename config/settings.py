"""Конфигурация приложения"""
from pydantic_settings import BaseSettings
from typing import List, Optional


def parse_csv_list(value: str) -> List[str]:
    """Разбор списка значений через запятую из .env."""
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Настройки приложения"""

    # API настройки
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"

    # IP whitelist (через запятую). Пусто — блокировать все, кроме GET /
    api_allowed_ips: str = (
        "77.246.105.29,46.151.31.105,212.118.52.195,95.142.47.150,89.110.76.53,127.0.0.1"
    )

    # CORS: origins через запятую; пусто — middleware CORS не подключается
    cors_origins: str = ""
    cors_allow_credentials: bool = False

    # База данных
    database_url: str = "sqlite:///./database/veil_xray.db"

    # Xray настройки
    xray_api_host: str = "127.0.0.1"
    xray_api_port: int = 10085
    xray_config_path: str = "/usr/local/etc/xray/config.json"

    # Reality настройки (универсальные параметры)
    reality_server_name: str = "veil-bear.ru"
    reality_sni: str = "microsoft.com"
    reality_fingerprint: str = "chrome"
    reality_dest: str = "www.microsoft.com:443"
    reality_port: int = 443

    # Публичный и приватный ключи Reality (генерируются при первом запуске)
    reality_public_key: Optional[str] = None
    reality_private_key: Optional[str] = None

    # Общий short_id для всех пользователей (используется вместо индивидуальных)
    # Это позволяет избежать перезагрузки Xray при создании/удалении ключей
    reality_common_short_id: str = "7bb45050"  # Можно изменить через .env

    # Flow для VLESS (для Xray 26.x обязателен отличный от "none"; рекомендуется xtls-rprx-vision)
    reality_flow: str = "xtls-rprx-vision"

    # Домен
    domain: str = "veil-bear.ru"

    # Логирование
    log_level: str = "INFO"
    log_file: Optional[str] = "./logs/veil_xray_api.log"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5  # Хранить 5 ротированных файлов

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()


def get_allowed_ips() -> List[str]:
    return parse_csv_list(settings.api_allowed_ips)


def get_cors_origins() -> List[str]:
    return parse_csv_list(settings.cors_origins)
