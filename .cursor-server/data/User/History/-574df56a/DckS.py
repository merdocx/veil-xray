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
    
    # Домен
    domain: str = "veil-bear.ru"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

