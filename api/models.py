"""Pydantic модели для API"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class KeyCreate(BaseModel):
    """Модель для создания ключа"""
    name: Optional[str] = None


class KeyResponse(BaseModel):
    """Модель ответа с информацией о ключе"""
    key_id: int
    uuid: str
    short_id: str
    name: Optional[str]
    created_at: int
    is_active: bool
    
    class Config:
        from_attributes = True


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


class KeyListResponse(BaseModel):
    """Модель ответа со списком ключей"""
    keys: list[KeyResponse]
    total: int


