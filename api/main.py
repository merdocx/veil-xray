"""Основной файл API сервера"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import time
import logging
from datetime import datetime

from api.database import get_db, Key, TrafficStats, init_db
from api.models import (
    KeyCreate, KeyResponse, KeyDeleteResponse,
    TrafficResponse, VlessLinkResponse, KeyListResponse
)
from api.xray_client import XrayClient
from api.xray_config import XrayConfigManager
from api.utils import generate_uuid, generate_short_id, build_vless_link
from config.settings import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(
    title="Veil Xray API",
    description="API для управления VLESS+Reality VPN сервером",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Инициализация Xray клиента и менеджера конфигурации
xray_client = XrayClient()
xray_config_manager = XrayConfigManager()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена авторизации"""
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return credentials.credentials


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Initializing database...")
    init_db()
    logger.info("API server started")


@app.get("/", tags=["Health"])
async def root():
    """Проверка работоспособности API"""
    return {"status": "ok", "service": "veil-xray-api"}


@app.post("/api/keys", response_model=KeyResponse, tags=["Keys"])
async def create_key(
    key_data: KeyCreate,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Создание нового ключа для VPN
    
    - Генерирует UUID и Short ID
    - Добавляет пользователя в Xray без перезагрузки
    - Сохраняет ключ в базу данных
    """
    try:
        # Генерация уникальных параметров
        uuid_value = generate_uuid()
        short_id = generate_short_id(8)
        
        # Проверка уникальности (на всякий случай)
        while db.query(Key).filter(Key.short_id == short_id).first():
            short_id = generate_short_id(8)
        
        # Создание записи в базе данных
        timestamp = int(time.time())
        new_key = Key(
            uuid=uuid_value,
            short_id=short_id,
            name=key_data.name,
            created_at=timestamp,
            is_active=1
        )
        
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        
        # Добавление пользователя в Xray через API и конфигурационный файл
        email = f"user_{new_key.id}_{uuid_value[:8]}"
        
        # Пытаемся добавить через Xray API (может не работать, если Xray не запущен)
        api_success = await xray_client.add_user(uuid_value, email)
        
        # Гарантированно добавляем в конфигурационный файл
        config_success = xray_config_manager.add_user_to_config(
            uuid=uuid_value,
            short_id=short_id,
            email=email
        )
        
        if not config_success:
            logger.error(f"Failed to add user to Xray config file: {new_key.id}")
            # Откатываем транзакцию, так как конфигурация не обновлена
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update Xray configuration"
            )
        
        if not api_success:
            logger.warning(f"Failed to add user to Xray via API, but config file updated: {new_key.id}")
            # Это не критично, конфигурация обновлена в файле
        
        # Инициализация статистики трафика
        traffic_stat = TrafficStats(
            key_id=new_key.id,
            upload=0,
            download=0,
            updated_at=timestamp
        )
        db.add(traffic_stat)
        db.commit()
        
        logger.info(f"Key created successfully: {new_key.id}, UUID: {uuid_value[:8]}...")
        
        return KeyResponse(
            key_id=new_key.id,
            uuid=new_key.uuid,
            short_id=new_key.short_id,
            name=new_key.name,
            created_at=new_key.created_at,
            is_active=bool(new_key.is_active)
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create key: {str(e)}"
        )


@app.delete("/api/keys/{key_id}", response_model=KeyDeleteResponse, tags=["Keys"])
async def delete_key(
    key_id: int,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Удаление ключа
    
    - Удаляет пользователя из Xray без перезагрузки
    - Удаляет ключ из базы данных
    """
    try:
        key = db.query(Key).filter(Key.id == key_id).first()
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with id {key_id} not found"
            )
        
        # Удаление пользователя из Xray через API и конфигурационный файл
        email = f"user_{key.id}_{key.uuid[:8]}"
        
        # Пытаемся удалить через Xray API
        await xray_client.remove_user(email)
        
        # Гарантированно удаляем из конфигурационного файла
        config_success = xray_config_manager.remove_user_from_config(
            uuid=key.uuid,
            short_id=key.short_id
        )
        
        if not config_success:
            logger.warning(f"Failed to remove user from Xray config file: {key_id}")
            # Продолжаем удаление из БД, даже если конфигурация не обновлена
        
        # Удаление из базы данных (каскадное удаление статистики)
        db.delete(key)
        db.commit()
        
        logger.info(f"Key deleted successfully: {key_id}")
        
        return KeyDeleteResponse(
            success=True,
            message=f"Key {key_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete key: {str(e)}"
        )


@app.get("/api/keys/{key_id}/traffic", response_model=TrafficResponse, tags=["Traffic"])
async def get_traffic(
    key_id: int,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Получение статистики трафика по ключу
    
    - Получает актуальную статистику из Xray
    - Обновляет данные в базе данных
    """
    try:
        key = db.query(Key).filter(Key.id == key_id).first()
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with id {key_id} not found"
            )
        
        # Получение статистики из Xray
        email = f"user_{key.id}_{key.uuid[:8]}"
        xray_stats = await xray_client.get_user_stats(email)
        
        upload = xray_stats.get("upload", 0)
        download = xray_stats.get("download", 0)
        
        # Обновление статистики в базе данных
        traffic_stat = db.query(TrafficStats).filter(TrafficStats.key_id == key_id).first()
        
        if traffic_stat:
            traffic_stat.upload = upload
            traffic_stat.download = download
            traffic_stat.updated_at = int(time.time())
        else:
            traffic_stat = TrafficStats(
                key_id=key_id,
                upload=upload,
                download=download,
                updated_at=int(time.time())
            )
            db.add(traffic_stat)
        
        db.commit()
        
        return TrafficResponse(
            key_id=key_id,
            upload=upload,
            download=download,
            total=upload + download,
            last_updated=traffic_stat.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting traffic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get traffic: {str(e)}"
        )


@app.get("/api/keys/{key_id}/link", response_model=VlessLinkResponse, tags=["Keys"])
async def get_vless_link(
    key_id: int,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Получение готовой VLESS ссылки для импорта в клиент
    
    - Формирует ссылку с оптимизацией для v2raytun
    - Включает все необходимые параметры Reality
    """
    try:
        key = db.query(Key).filter(Key.id == key_id).first()
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with id {key_id} not found"
            )
        
        # Получение публичного ключа Reality (должен быть сгенерирован при первом запуске)
        if not settings.reality_public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reality public key not configured"
            )
        
        # Построение VLESS ссылки
        vless_link = build_vless_link(
            uuid=key.uuid,
            short_id=key.short_id,
            server_address=settings.reality_server_name,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=settings.reality_public_key,
            dest=settings.reality_dest,
            flow="none"
        )
        
        return VlessLinkResponse(
            key_id=key_id,
            vless_link=vless_link
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating VLESS link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate VLESS link: {str(e)}"
        )


@app.get("/api/keys", response_model=KeyListResponse, tags=["Keys"])
async def list_keys(
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех ключей
    """
    try:
        keys = db.query(Key).all()
        
        key_responses = [
            KeyResponse(
                key_id=key.id,
                uuid=key.uuid,
                short_id=key.short_id,
                name=key.name,
                created_at=key.created_at,
                is_active=bool(key.is_active)
            )
            for key in keys
        ]
        
        return KeyListResponse(
            keys=key_responses,
            total=len(key_responses)
        )
        
    except Exception as e:
        logger.error(f"Error listing keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list keys: {str(e)}"
        )


@app.get("/api/keys/{key_id}", response_model=KeyResponse, tags=["Keys"])
async def get_key(
    key_id: int,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Получение информации о конкретном ключе
    """
    try:
        key = db.query(Key).filter(Key.id == key_id).first()
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with id {key_id} not found"
            )
        
        return KeyResponse(
            key_id=key.id,
            uuid=key.uuid,
            short_id=key.short_id,
            name=key.name,
            created_at=key.created_at,
            is_active=bool(key.is_active)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

