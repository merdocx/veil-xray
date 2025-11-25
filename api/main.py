"""Основной файл API сервера"""
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from typing import List
import time
import logging
import asyncio
from datetime import datetime

from api.database import get_db, Key, TrafficStats, init_db
from api.models import (
    KeyCreate, KeyResponse, KeyDeleteResponse,
    TrafficResponse, VlessLinkResponse, KeyListResponse
)
from api.xray_client import XrayClient
from api.xray_config import XrayConfigManager
from api.task_queue import config_task_queue, TaskType
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

# Middleware для принудительного HTTPS (если используется reverse proxy)
class ForceHTTPSMiddleware(BaseHTTPMiddleware):
    """Middleware для принудительного перенаправления HTTP -> HTTPS"""
    
    async def dispatch(self, request: Request, call_next):
        # Проверяем заголовок X-Forwarded-Proto (устанавливается reverse proxy)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        host = request.headers.get("Host", "")
        
        # Если запрос пришел по HTTP через reverse proxy, перенаправляем на HTTPS
        if forwarded_proto == "http" and host:
            url = request.url
            https_url = url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        
        response = await call_next(request)
        return response

# Добавляем middleware для принудительного HTTPS (только если используется reverse proxy)
# Раскомментируйте следующую строку, если хотите включить принудительное перенаправление на уровне приложения
# app.add_middleware(ForceHTTPSMiddleware)

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


async def sync_users_with_xray():
    """
    Синхронизация пользователей из БД с Xray API при старте приложения
    
    Добавляет в Xray всех активных пользователей, которые есть в БД,
    но отсутствуют в Xray (например, если Xray был перезапущен или API был недоступен).
    Также обновляет конфигурационный файл для обеспечения консистентности.
    """
    logger.info("🔄 Starting synchronization of users with Xray API...")
    
    db: Session = next(get_db())
    try:
        # Получаем все активные ключи из БД
        keys = db.query(Key).filter(Key.is_active == 1).all()
        
        if not keys:
            logger.info("No active keys found in database. Nothing to sync.")
            return
        
        logger.info(f"Found {len(keys)} active key(s) in database. Syncing with Xray...")
        
        # Проверяем доступность Xray API
        xray_api_available = await xray_client.check_health()
        
        if not xray_api_available:
            logger.warning(
                "⚠️  Xray API is not available. Will sync config file only. "
                "Users will be available after Xray restart."
            )
        
        synced_api_count = 0
        synced_config_count = 0
        skipped_count = 0
        error_count = 0
        
        for key in keys:
            try:
                email = f"user_{key.id}_{key.uuid[:8]}"
                config_updated = False
                api_updated = False
                
                # Сначала обновляем конфигурационный файл (всегда)
                # Это гарантирует, что пользователь будет в конфиге даже если API недоступен
                try:
                    config_success = xray_config_manager.add_user_to_config(
                        uuid=key.uuid,
                        short_id=key.short_id,
                        email=email
                    )
                    if config_success:
                        config_updated = True
                        synced_config_count += 1
                        logger.debug(
                            f"✅ Added user {key.id} (UUID: {key.uuid[:8]}...) "
                            f"to Xray config file"
                        )
                except Exception as config_error:
                    logger.warning(
                        f"⚠️  Failed to add user {key.id} to config file: {config_error}"
                    )
                
                # Затем пытаемся добавить через Xray API (если доступен)
                if xray_api_available:
                    try:
                        api_success = await xray_client.add_user(
                            uuid=key.uuid,
                            email=email,
                            flow="none"
                        )
                        
                        if api_success:
                            api_updated = True
                            synced_api_count += 1
                            logger.info(
                                f"✅ Synced user {key.id} (UUID: {key.uuid[:8]}..., email: {email}) "
                                f"to Xray API"
                            )
                        else:
                            # Пользователь может уже существовать в Xray, это нормально
                            logger.debug(
                                f"⏭️  User {key.id} (UUID: {key.uuid[:8]}...) "
                                f"may already exist in Xray API"
                            )
                    except Exception as api_error:
                        logger.warning(
                            f"⚠️  Failed to add user {key.id} to Xray API: {api_error}"
                        )
                
                # Если ни API, ни конфиг не обновились, считаем пропущенным
                if not config_updated and not api_updated:
                    skipped_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(
                    f"❌ Error syncing user {key.id} (UUID: {key.uuid[:8]}...) "
                    f"to Xray: {e}"
                )
        
        logger.info(
            f"🔄 User synchronization completed: "
            f"{synced_api_count} synced via API, {synced_config_count} synced via config, "
            f"{skipped_count} skipped, {error_count} errors"
        )
        
    except Exception as e:
        logger.error(f"❌ Error during user synchronization: {e}")
    finally:
        db.close()


async def sync_all_traffic_stats():
    """Фоновая задача для синхронизации статистики всех ключей"""
    while True:
        try:
            await asyncio.sleep(60)  # Обновление каждую минуту
            
            db: Session = next(get_db())
            try:
                keys = db.query(Key).filter(Key.is_active == 1).all()
                
                for key in keys:
                    try:
                        email = f"user_{key.id}_{key.uuid[:8]}"
                        xray_stats = await xray_client.get_user_stats(email)
                        
                        upload = xray_stats.get("upload", 0)
                        download = xray_stats.get("download", 0)
                        
                        traffic_stat = db.query(TrafficStats).filter(
                            TrafficStats.key_id == key.id
                        ).order_by(TrafficStats.updated_at.desc()).first()
                        
                        if traffic_stat:
                            if traffic_stat.upload != upload or traffic_stat.download != download:
                                traffic_stat.upload = upload
                                traffic_stat.download = download
                                traffic_stat.updated_at = int(time.time())
                                logger.info(f"Auto-updated stats for key {key.id}: upload={upload}, download={download}")
                        else:
                            traffic_stat = TrafficStats(
                                key_id=key.id,
                                upload=upload,
                                download=download,
                                updated_at=int(time.time())
                            )
                            db.add(traffic_stat)
                            logger.info(f"Auto-created stats for key {key.id}")
                        
                        db.commit()
                    except Exception as e:
                        logger.error(f"Error syncing stats for key {key.id}: {e}")
                        db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in background traffic sync: {e}")


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("🚀 Starting Veil Xray API server...")
    
    # Инициализация базы данных
    logger.info("📦 Initializing database...")
    init_db()
    logger.info("✅ Database initialized")
    
    # Запуск очереди задач для обработки конфигурации Xray
    await config_task_queue.start()
    logger.info("✅ Config task queue started")
    
    # Синхронизация пользователей с Xray API
    await sync_users_with_xray()
    
    # Запускаем фоновую задачу для синхронизации статистики
    asyncio.create_task(sync_all_traffic_stats())
    logger.info("✅ Background traffic sync task started")
    
    logger.info("✅ API server started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Остановка при завершении работы"""
    logger.info("🛑 Shutting down Veil Xray API server...")
    
    # Остановка очереди задач
    await config_task_queue.stop()
    logger.info("✅ Config task queue stopped")
    
    logger.info("✅ API server stopped")


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
        # Используем try-except для обработки случая, когда таблица еще не создана
        try:
            while db.query(Key).filter(Key.short_id == short_id).first():
                short_id = generate_short_id(8)
        except Exception:
            # Если таблица не существует, просто продолжаем (она будет создана)
            pass
        
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
        
        # Добавляем задачу в очередь для последовательной обработки конфигурации
        # Это гарантирует отсутствие race conditions при параллельных запросах
        config_task_added = False
        try:
            await config_task_queue.add_task(
                task_type=TaskType.ADD_USER,
                uuid=uuid_value,
                short_id=short_id,
                email=email
            )
            config_task_added = True
            logger.debug(
                f"📥 Added ADD_USER task to queue for key {new_key.id} "
                f"(UUID: {uuid_value[:8]}...)"
            )
        except Exception as e:
            logger.error(f"Failed to add task to queue: {e}")
            # Если очередь недоступна, используем прямой вызов как fallback
            config_success = xray_config_manager.add_user_to_config(
                uuid=uuid_value,
                short_id=short_id,
                email=email
            )
            if not config_success:
                logger.error(f"Failed to add user to Xray config file: {new_key.id}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update Xray configuration"
                )
        
        if not api_success:
            logger.warning(
                f"⚠️  Failed to add user {new_key.id} (UUID: {uuid_value[:8]}...) "
                f"to Xray via API, but config task added to queue. "
                f"User will be available after Xray restart or will be synced automatically."
            )
            # Это не критично, задача добавлена в очередь
        
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
        
        # Добавляем задачу в очередь для последовательной обработки конфигурации
        # Это гарантирует отсутствие race conditions при параллельных запросах
        try:
            await config_task_queue.add_task(
                task_type=TaskType.REMOVE_USER,
                uuid=key.uuid,
                short_id=key.short_id,
                email=email
            )
            logger.debug(
                f"📥 Added REMOVE_USER task to queue for key {key_id} "
                f"(UUID: {key.uuid[:8]}...)"
            )
        except Exception as e:
            logger.error(f"Failed to add task to queue: {e}")
            # Если очередь недоступна, используем прямой вызов как fallback
            config_success = xray_config_manager.remove_user_from_config(
                uuid=key.uuid,
                short_id=key.short_id
            )
            if not config_success:
                logger.warning(
                    f"⚠️  Failed to remove user {key_id} (UUID: {key.uuid[:8]}...) "
                    f"from Xray config file. User removed from database but may still exist in config."
                )
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


@app.post("/api/traffic/sync", tags=["Traffic"])
async def sync_all_traffic(
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Ручная синхронизация статистики трафика для всех активных ключей
    """
    try:
        keys = db.query(Key).filter(Key.is_active == 1).all()
        
        updated_count = 0
        error_count = 0
        
        for key in keys:
            try:
                email = f"user_{key.id}_{key.uuid[:8]}"
                xray_stats = await xray_client.get_user_stats(email)
                
                upload = xray_stats.get("upload", 0)
                download = xray_stats.get("download", 0)
                
                traffic_stat = db.query(TrafficStats).filter(
                    TrafficStats.key_id == key.id
                ).order_by(TrafficStats.updated_at.desc()).first()
                
                if traffic_stat:
                    traffic_stat.upload = upload
                    traffic_stat.download = download
                    traffic_stat.updated_at = int(time.time())
                else:
                    traffic_stat = TrafficStats(
                        key_id=key.id,
                        upload=upload,
                        download=download,
                        updated_at=int(time.time())
                    )
                    db.add(traffic_stat)
                
                updated_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error syncing stats for key {key.id}: {e}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Synced {updated_count} keys, {error_count} errors",
            "updated": updated_count,
            "errors": error_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing all traffic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync traffic: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

