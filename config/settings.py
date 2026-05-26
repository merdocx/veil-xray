"""Конфигурация приложения"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """Настройки приложения"""

    # API настройки
    # По умолчанию только loopback: прод-схема Nginx → 127.0.0.1:port
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"

    # Список IP, с которых разрешён доступ к API (через запятую).
    # Административные сервера + 127.0.0.1 для локальных проверок на хосте.
    api_allowed_ips: str = "127.0.0.1,89.110.76.53,91.184.245.209"

    # Swagger/ReDoc/OpenAPI (в проде обычно выключено)
    api_enable_docs: bool = False

    # CORS: пустая строка — без CORS (подходит для server-to-server / curl).
    # Через запятую: https://a.com,https://b.com
    api_cors_origins: str = ""

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

    # Фоновая синхронизация трафика Xray → SQLite
    enable_background_traffic_sync: bool = False
    background_traffic_sync_interval_s: int = 600
    background_traffic_sync_batch_size: int = 50

    # Кэш статистики трафика в памяти (секунды; 1800 = 30 мин)
    traffic_cache_ttl_s: int = 3600

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def allowed_ip_list(self) -> List[str]:
        return [x.strip() for x in self.api_allowed_ips.split(",") if x.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.api_cors_origins.strip():
            return []
        return [x.strip() for x in self.api_cors_origins.split(",") if x.strip()]


settings = Settings()
