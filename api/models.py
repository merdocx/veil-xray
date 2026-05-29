"""Pydantic модели для API"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional
from datetime import datetime


class KeyCreate(BaseModel):
    """Модель для создания ключа"""

    name: Optional[str] = Field(
        None, max_length=255, description="Имя ключа (максимум 255 символов)"
    )


class KeyResponse(BaseModel):
    """Модель ответа с информацией о ключе"""

    key_id: int
    uuid: str
    short_id: str
    name: Optional[str]
    created_at: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class KeyDeleteResponse(BaseModel):
    """Модель ответа при удалении ключа"""

    success: bool
    message: str


class TrafficResponse(BaseModel):
    """Модель ответа со статистикой трафика"""

    key_id: int
    upload: int
    download: int
    total: int
    last_updated: int


class VlessLinkResponse(BaseModel):
    """Модель ответа с VLESS ссылкой"""

    key_id: int
    vless_link: str


class KeyLinkProfile(BaseModel):
    """Один профиль подключения (ссылка) для ключа."""

    profile: Literal[
        "vless_tcp_443",
        "vless_tcp_alt",
        "vless_xhttp",
        "trojan_tcp",
        "vless_tcp_443_sni_b",
    ]
    link: str


class KeyLinksResponse(BaseModel):
    """Набор профилей подключения для одного ключа."""

    key_id: int
    links: list[KeyLinkProfile]


class KeyListResponse(BaseModel):
    """Модель ответа со списком ключей"""

    keys: list[KeyResponse]
    total: int


class TrafficResetResponse(BaseModel):
    """Модель ответа при обнулении трафика"""

    success: bool
    message: str
    key_id: int
    previous_upload: int
    previous_download: int
    previous_total: int


class XraySyncStartResponse(BaseModel):
    """Ответ при запуске фоновой синхронизации пользователей Xray."""

    success: bool
    status: Literal["started", "already_running"]
    message: str


class XraySyncStatusResponse(BaseModel):
    """Статус фоновой синхронизации пользователей Xray."""

    status: Literal["idle", "running", "completed", "failed"]
    trigger: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    synced_via_api: Optional[int] = None
    synced_via_config: Optional[int] = None
    skipped: Optional[int] = None
    errors: Optional[int] = None
    total_keys: Optional[int] = None
    error_message: Optional[str] = None
