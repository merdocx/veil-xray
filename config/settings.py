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
    api_allowed_ips: str = "127.0.0.1"

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
    reality_server_name: str = "your-domain.example"
    reality_sni: str = "microsoft.com"
    reality_fingerprint: str = "chrome"
    reality_dest: str = "www.microsoft.com:443"
    reality_port: int = 443
    # Дополнительные входы (anti-block fallback)
    reality_alt_port_tcp: int = 446
    # Happ / sing-box на iOS: inbound без Vision-flow (порт 448)
    reality_happ_port_tcp: int = 448
    reality_xhttp_port: int = 8445
    trojan_reality_port: int = 2085
    # XHTTP транспорт: path должен совпадать на клиенте/сервере
    reality_xhttp_path: str = "/a7f9d2c8"

    # Публичный и приватный ключи Reality (генерируются при первом запуске)
    reality_public_key: Optional[str] = None
    reality_private_key: Optional[str] = None

    # Общий short_id для всех пользователей (используется вместо индивидуальных)
    # Это позволяет избежать перезагрузки Xray при создании/удалении ключей
    reality_common_short_id: str = "7bb45050"  # Можно изменить через .env

    # Flow для VLESS (для Xray 26.x обязателен отличный от "none"; рекомендуется xtls-rprx-vision)
    reality_flow: str = "xtls-rprx-vision"

    # Домен / хост в VLESS-ссылках (IP или DNS)
    domain: str = "your-domain.example"

    # Имя в фрагменте vless://…#remark (пусто = DOMAIN)
    vless_link_remark: str = ""

    # Теги inbounds в Xray (должны совпадать с config.json)
    xray_vless_reality_inbound_tag: str = "vless-reality"
    xray_vless_reality_alt_inbound_tag: str = "vless-reality-alt"
    xray_vless_reality_happ_inbound_tag: str = "vless-reality-happ"
    xray_vless_reality_xhttp_inbound_tag: str = "vless-reality-xhttp"
    xray_trojan_reality_inbound_tag: str = "trojan-reality"

    # Второй REALITY-профиль (SNI-B), опционально
    reality_sni_b: Optional[str] = None
    reality_dest_b: str = "www.cloudflare.com:443"
    reality_fingerprint_b: Optional[str] = None
    reality_port_sni_b: int = 447
    reality_public_key_b: Optional[str] = None
    reality_private_key_b: Optional[str] = None
    reality_common_short_id_b: Optional[str] = None
    xray_vless_reality_sni_b_inbound_tag: str = "vless-reality-sni-b"

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
    def link_remark(self) -> str:
        remark = self.vless_link_remark.strip()
        return remark if remark else self.domain

    @property
    def allowed_ip_list(self) -> List[str]:
        return [x.strip() for x in self.api_allowed_ips.split(",") if x.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.api_cors_origins.strip():
            return []
        return [x.strip() for x in self.api_cors_origins.split(",") if x.strip()]

    @property
    def reality_sni_b_enabled(self) -> bool:
        return bool(
            self.reality_sni_b
            and self.reality_public_key_b
            and self.reality_private_key_b
        )

    @property
    def reality_short_id_b(self) -> str:
        return self.reality_common_short_id_b or self.reality_common_short_id

    @property
    def reality_fingerprint_b_value(self) -> str:
        return self.reality_fingerprint_b or self.reality_fingerprint

    def vless_inbound_tags(self) -> List[str]:
        tags = [
            self.xray_vless_reality_inbound_tag,
            self.xray_vless_reality_alt_inbound_tag,
            self.xray_vless_reality_happ_inbound_tag,
            self.xray_vless_reality_xhttp_inbound_tag,
        ]
        if self.reality_sni_b_enabled:
            tags.append(self.xray_vless_reality_sni_b_inbound_tag)
        return tags

    def vless_inbound_tags_without_flow(self) -> List[str]:
        """Inbounds для Happ / mobile: клиент без Vision-flow."""
        tags = [
            self.xray_vless_reality_happ_inbound_tag,
            self.xray_vless_reality_alt_inbound_tag,
        ]
        if self.reality_sni_b_enabled:
            tags.append(self.xray_vless_reality_sni_b_inbound_tag)
        return tags

    def all_user_inbound_tags(self) -> List[str]:
        return self.vless_inbound_tags() + [self.xray_trojan_reality_inbound_tag]


settings = Settings()
