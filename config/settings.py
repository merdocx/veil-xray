"""Конфигурация приложения"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""

    # API настройки
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"

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
