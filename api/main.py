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
import logging.handlers
import asyncio
from datetime import datetime
from pathlib import Path

from api.database import get_db, Key, TrafficStats, init_db
from api.models import (
    KeyCreate,
    KeyResponse,
    KeyDeleteResponse,
    TrafficResponse,
    VlessLinkResponse,
    KeyListResponse,
    TrafficResetResponse,
)
from api.xray_client import XrayClient
from api.xray_config import XrayConfigManager
from api.task_queue import config_task_queue, TaskType
from api.utils import generate_uuid, generate_short_id, build_vless_link
from config.settings import settings

# Настройка логирования
def setup_logging():
    """Настройка логирования с файловым выводом и ротацией"""
    log_level = getattr(settings, "log_level", "INFO")
    log_file = getattr(settings, "log_file", "./logs/veil_xray_api.log")
    log_max_bytes = getattr(settings, "log_max_bytes", 10485760)  # 10MB
    log_backup_count = getattr(settings, "log_backup_count", 5)
    
    # Создаем директорию для логов если её нет
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Формат логов
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Удаляем существующие handlers
    root_logger.handlers.clear()
    
    # Handler для файла с ротацией
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Handler для консоли (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(
    title="Veil Xray API",
    description="API для управления VLESS+Reality VPN сервером",
    version="1.3.5",
)


# Middleware для логирования запросов и ошибок
class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех запросов и ошибок с полными деталями"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_path = str(request.url.path)
        request_method = request.method
        query_params = str(request.url.query) if request.url.query else ""
        full_path = f"{request_path}?{query_params}" if query_params else request_path

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            status_code = response.status_code

            # Логируем ошибки с более подробной информацией
            if status_code >= 400:
                logger.warning(
                    f"⚠️  {request_method} {full_path} - "
                    f"Status: {status_code} - "
                    f"Time: {process_time:.3f}s"
                )
            else:
                logger.info(
                    f"{request_method} {full_path} - "
                    f"Status: {status_code} - "
                    f"Time: {process_time:.3f}s"
                )
            return response
        except HTTPException as e:
            process_time = time.time() - start_time
            logger.error(
                f"❌ HTTPException in {request_method} {full_path} - "
                f"Status: {e.status_code} - "
                f"Detail: {e.detail} - "
                f"Time: {process_time:.3f}s"
            )
            raise
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                f"❌ Error processing {request_method} {full_path} - "
                f"Time: {process_time:.3f}s - "
                f"Error: {type(e).__name__}: {e}"
            )
            raise


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


# Добавляем middleware для логирования запросов и ошибок
app.add_middleware(LoggingMiddleware)

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
            detail="Invalid authentication token",
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

        logger.info(
            f"Found {len(keys)} active key(s) in database. Syncing with Xray..."
        )

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

        # Используем общий short_id для всех пользователей
        common_short_id = settings.reality_common_short_id

        for key in keys:
            try:
                email = f"user_{key.id}_{key.uuid[:8]}"
                config_updated = False
                api_updated = False

                # Сначала обновляем конфигурационный файл (всегда)
                # Это гарантирует, что пользователь будет в конфиге даже если API недоступен
                try:
                    config_success = xray_config_manager.add_user_to_config(
                        uuid=key.uuid, short_id=common_short_id, email=email
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
                            uuid=key.uuid, email=email, flow="none"
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

                        traffic_stat = (
                            db.query(TrafficStats)
                            .filter(TrafficStats.key_id == key.id)
                            .order_by(TrafficStats.updated_at.desc())
                            .first()
                        )

                        if traffic_stat:
                            if (
                                traffic_stat.upload != upload
                                or traffic_stat.download != download
                            ):
                                traffic_stat.upload = upload
                                traffic_stat.download = download
                                traffic_stat.updated_at = int(time.time())
                                logger.info(
                                    f"Auto-updated stats for key {key.id}: upload={upload}, download={download}"
                                )
                        else:
                            traffic_stat = TrafficStats(
                                key_id=key.id,
                                upload=upload,
                                download=download,
                                updated_at=int(time.time()),
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

    # Убеждаемся, что общий short_id присутствует в конфигурации Xray
    common_short_id = settings.reality_common_short_id
    xray_config_manager.ensure_common_short_id(common_short_id)
    logger.info(f"✅ Common short_id '{common_short_id}' ensured in Xray config")

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
    db: Session = Depends(get_db),
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
        # Используем общий short_id для всех пользователей
        common_short_id = settings.reality_common_short_id

        # Создание записи в базе данных
        timestamp = int(time.time())
        new_key = Key(
            uuid=uuid_value,
            short_id=common_short_id,  # Используем общий short_id
            name=key_data.name,
            created_at=timestamp,
            is_active=1,
        )

        db.add(new_key)
        db.commit()
        db.refresh(new_key)

        # Добавление пользователя в Xray через API и конфигурационный файл
        email = f"user_{new_key.id}_{uuid_value[:8]}"

        # Пытаемся добавить через Xray API (может не работать, если Xray не запущен)
        api_success = await xray_client.add_user(uuid_value, email)

        # Добавляем пользователя в конфигурационный файл и ждем выполнения
        # Это гарантирует, что пользователь будет добавлен в конфигурацию перед финальным коммитом
        config_success = False
        try:
            # Используем execute_task_and_wait для гарантированного выполнения
            config_success = await config_task_queue.execute_task_and_wait(
                task_type=TaskType.ADD_USER,
                uuid=uuid_value,
                short_id=common_short_id,  # Используем общий short_id
                email=email,
                timeout=30.0,  # Таймаут 30 секунд
            )
            if config_success:
                logger.info(
                    f"✅ User {new_key.id} (UUID: {uuid_value[:8]}...) added to Xray config file"
                )
            else:
                logger.error(
                    f"❌ Failed to add user {new_key.id} (UUID: {uuid_value[:8]}...) "
                    f"to Xray config file"
                )
                # Откатываем транзакцию, если не удалось добавить в конфигурацию
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update Xray configuration",
                )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Timeout waiting for config update for key {new_key.id} (UUID: {uuid_value[:8]}...). "
                f"Trying direct fallback..."
            )
            # Fallback: прямой вызов если очередь не отвечает
            try:
                config_success = xray_config_manager.add_user_to_config(
                    uuid=uuid_value, short_id=common_short_id, email=email
                )
                if not config_success:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update Xray configuration (timeout and fallback failed)",
                    )
            except Exception as e:
                logger.error(f"❌ Fallback config addition also failed: {e}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update Xray configuration: {str(e)}",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"❌ Error adding user {new_key.id} to config: {e}. Trying direct fallback..."
            )
            # Fallback: прямой вызов при ошибке
            try:
                config_success = xray_config_manager.add_user_to_config(
                    uuid=uuid_value, short_id=common_short_id, email=email
                )
                if not config_success:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update Xray configuration (fallback failed)",
                    )
            except HTTPException:
                raise
            except Exception as fallback_error:
                logger.error(
                    f"❌ Fallback config addition also failed: {fallback_error}"
                )
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update Xray configuration: {str(fallback_error)}",
                )

        if not api_success:
            logger.warning(
                f"⚠️  Failed to add user {new_key.id} (UUID: {uuid_value[:8]}...) "
                f"to Xray via API, but added to config file. "
                f"User will be available after Xray restart or will be synced automatically."
            )
            # Это не критично, пользователь добавлен в конфигурацию

        # Инициализация статистики трафика
        traffic_stat = TrafficStats(
            key_id=new_key.id, upload=0, download=0, updated_at=timestamp
        )
        db.add(traffic_stat)
        db.commit()

        logger.info(
            f"Key created successfully: {new_key.id}, UUID: {uuid_value[:8]}..."
        )

        return KeyResponse(
            key_id=new_key.id,  # type: ignore
            uuid=new_key.uuid,  # type: ignore
            short_id=common_short_id,  # Возвращаем общий short_id
            name=new_key.name,  # type: ignore
            created_at=new_key.created_at,  # type: ignore
            is_active=bool(new_key.is_active),  # type: ignore
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create key: {str(e)}",
        )


@app.delete("/api/keys/{identifier}", response_model=KeyDeleteResponse, tags=["Keys"])
async def delete_key(
    identifier: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Удаление ключа по UUID или key_id
    Поддерживает оба формата: /api/keys/{uuid} и /api/keys/{key_id}

    - Удаляет пользователя из Xray без перезагрузки
    - Удаляет ключ из базы данных
    """
    try:
        # Пытаемся определить, это UUID или key_id
        if "-" in identifier:
            # Это UUID
            key = db.query(Key).filter(Key.uuid == identifier).first()
        else:
            # Это key_id
            try:
                key_id = int(identifier)
                key = db.query(Key).filter(Key.id == key_id).first()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid identifier format: {identifier}. Expected UUID or key_id",
                )

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found",
            )

        key_id = key.id  # type: ignore

        # Удаление пользователя из Xray через API и конфигурационный файл
        email = f"user_{key.id}_{key.uuid[:8]}"

        # Пытаемся удалить через Xray API
        await xray_client.remove_user(email)

        # Удаляем пользователя из конфигурационного файла и ждем выполнения
        # Это гарантирует, что пользователь будет удален из конфигурации перед удалением из БД
        config_success = False
        try:
            # Используем общий short_id для всех пользователей
            common_short_id = settings.reality_common_short_id

            # Используем execute_task_and_wait для гарантированного выполнения
            config_success = await config_task_queue.execute_task_and_wait(
                task_type=TaskType.REMOVE_USER,
                uuid=key.uuid,  # type: ignore
                short_id=common_short_id,  # Используем общий short_id
                email=email,
                timeout=30.0,  # Таймаут 30 секунд
            )
            if config_success:
                logger.info(
                    f"✅ User {key_id} (UUID: {key.uuid[:8]}...) removed from Xray config file"
                )
            else:
                logger.warning(
                    f"⚠️  Failed to remove user {key_id} (UUID: {key.uuid[:8]}...) "
                    f"from Xray config file"
                )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Timeout waiting for config update for key {key_id} (UUID: {key.uuid[:8]}...). "
                f"Trying direct fallback..."
            )
            # Fallback: прямой вызов если очередь не отвечает
            try:
                common_short_id = settings.reality_common_short_id
                config_success = xray_config_manager.remove_user_from_config(
                    uuid=key.uuid, short_id=common_short_id  # type: ignore
                )
            except Exception as e:
                logger.error(f"❌ Fallback config removal also failed: {e}")
                config_success = False
        except Exception as e:
            logger.error(
                f"❌ Error removing user {key_id} from config: {e}. Trying direct fallback..."
            )
            # Fallback: прямой вызов при ошибке
            try:
                common_short_id = settings.reality_common_short_id
                config_success = xray_config_manager.remove_user_from_config(
                    uuid=key.uuid, short_id=common_short_id  # type: ignore
                )
            except Exception as fallback_error:
                logger.error(f"❌ Fallback config removal also failed: {fallback_error}")
                config_success = False

        # Если удаление из конфигурации не удалось, логируем предупреждение
        # но продолжаем удаление из БД (чтобы не блокировать операцию)
        if not config_success:
            logger.warning(
                f"⚠️  Key {key_id} will be removed from database, but user may still exist in Xray config file. "
                f"Manual cleanup may be required."
            )

        # Удаление из базы данных (каскадное удаление статистики)
        # Теперь это происходит ПОСЛЕ попытки удаления из конфигурации
        db.delete(key)
        db.commit()

        logger.info(f"Key deleted successfully: {key_id}")

        return KeyDeleteResponse(
            success=True, message=f"Key {key_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete key: {str(e)}",
        )


@app.get("/api/keys/{key_id}/traffic", response_model=TrafficResponse, tags=["Traffic"])
async def get_traffic(
    key_id: int, token: str = Depends(verify_token), db: Session = Depends(get_db)
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
                detail=f"Key with id {key_id} not found",
            )

        # Получение статистики из Xray
        email = f"user_{key.id}_{key.uuid[:8]}"
        xray_stats = await xray_client.get_user_stats(email)

        upload = xray_stats.get("upload", 0)
        download = xray_stats.get("download", 0)

        # Обновление статистики в базе данных
        traffic_stat = (
            db.query(TrafficStats).filter(TrafficStats.key_id == key_id).first()
        )

        if traffic_stat:
            traffic_stat.upload = upload  # type: ignore
            traffic_stat.download = download  # type: ignore
            traffic_stat.updated_at = int(time.time())  # type: ignore
        else:
            traffic_stat = TrafficStats(
                key_id=key_id,
                upload=upload,
                download=download,
                updated_at=int(time.time()),
            )
            db.add(traffic_stat)

        db.commit()

        return TrafficResponse(
            key_id=key_id,
            upload=upload,
            download=download,
            total=upload + download,
            last_updated=traffic_stat.updated_at,  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting traffic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get traffic: {str(e)}",
        )


@app.get("/api/keys/{identifier}/link", response_model=VlessLinkResponse, tags=["Keys"])
async def get_vless_link(
    identifier: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Получение готовой VLESS ссылки для импорта в клиент
    Поддерживает оба формата: /api/keys/{uuid}/link и /api/keys/{key_id}/link

    - Формирует ссылку с оптимизацией для v2raytun
    - Включает все необходимые параметры Reality
    """
    try:
        # Пытаемся определить, это UUID или key_id
        if "-" in identifier:
            # Это UUID
            key = db.query(Key).filter(Key.uuid == identifier).first()
        else:
            # Это key_id
            try:
                key_id = int(identifier)
                key = db.query(Key).filter(Key.id == key_id).first()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid identifier format: {identifier}. Expected UUID or key_id",
                )

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found",
            )

        # Получение публичного ключа Reality (должен быть сгенерирован при первом запуске)
        if not settings.reality_public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reality public key not configured",
            )

        # Конвертируем публичный ключ в URL-safe формат для использования в ссылке
        # Если ключ в стандартном base64 формате, конвертируем в URL-safe
        public_key = settings.reality_public_key
        try:
            import base64

            # Пробуем декодировать и перекодировать в URL-safe формат
            # Это нужно, если ключ хранится в стандартном base64 формате
            if "/" in public_key or "+" in public_key or public_key.endswith("="):
                # Стандартный base64, конвертируем в URL-safe
                decoded = base64.b64decode(
                    public_key + "==" if not public_key.endswith("=") else public_key
                )
                public_key = (
                    base64.urlsafe_b64encode(decoded).decode("utf-8").rstrip("=")
                )
        except Exception:
            # Если не удалось конвертировать, используем как есть
            pass

        # Построение VLESS ссылки
        # Используем общий short_id для всех пользователей (из настроек)
        # Это позволяет избежать перезагрузки Xray при создании/удалении ключей
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,  # Используем общий short_id из настроек
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,  # Используем URL-safe формат
            dest=settings.reality_dest,
            flow="none",
        )

        return VlessLinkResponse(key_id=key.id, vless_link=vless_link)  # type: ignore

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Error generating VLESS link for identifier '{identifier}': {type(e).__name__}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate VLESS link: {str(e)}",
        )


@app.get("/api/keys", response_model=KeyListResponse, tags=["Keys"])
async def list_keys(token: str = Depends(verify_token), db: Session = Depends(get_db)):
    """
    Получение списка всех ключей
    """
    try:
        keys = db.query(Key).all()

        # Используем общий short_id для всех пользователей
        common_short_id = settings.reality_common_short_id

        key_responses = [
            KeyResponse(
                key_id=key.id,  # type: ignore
                uuid=key.uuid,  # type: ignore
                short_id=common_short_id,  # Возвращаем общий short_id
                name=key.name,  # type: ignore
                created_at=key.created_at,  # type: ignore
                is_active=bool(key.is_active),  # type: ignore
            )
            for key in keys
        ]

        return KeyListResponse(keys=key_responses, total=len(key_responses))

    except Exception as e:
        logger.error(f"Error listing keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list keys: {str(e)}",
        )


@app.get(
    "/api/keys/{identifier}/config", response_model=VlessLinkResponse, tags=["Keys"]
)
async def get_key_config(
    identifier: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Получение конфигурации (VLESS ссылки) по UUID или key_id
    Поддерживает оба формата: /api/keys/{uuid}/config и /api/keys/{key_id}/config
    """
    try:
        # Пытаемся определить, это UUID или key_id
        # UUID содержит дефисы, key_id - число
        if "-" in identifier:
            # Это UUID
            key = db.query(Key).filter(Key.uuid == identifier).first()
        else:
            # Это key_id
            try:
                key_id = int(identifier)
                key = db.query(Key).filter(Key.id == key_id).first()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid identifier format: {identifier}. Expected UUID or key_id",
                )

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found",
            )

        # Получение публичного ключа Reality
        if not settings.reality_public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reality public key not configured",
            )

        # Конвертируем публичный ключ в URL-safe формат
        public_key = settings.reality_public_key
        try:
            import base64

            if "/" in public_key or "+" in public_key or public_key.endswith("="):
                decoded = base64.b64decode(
                    public_key + "==" if not public_key.endswith("=") else public_key
                )
                public_key = (
                    base64.urlsafe_b64encode(decoded).decode("utf-8").rstrip("=")
                )
        except Exception:
            pass

        # Построение VLESS ссылки
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            dest=settings.reality_dest,
            flow="none",
        )

        return VlessLinkResponse(
            key_id=key.id,  # type: ignore
            vless_link=vless_link,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Error getting key config for identifier '{identifier}': {type(e).__name__}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key config: {str(e)}",
        )


@app.get("/api/keys/{identifier}", response_model=KeyResponse, tags=["Keys"])
async def get_key(
    identifier: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Получение информации о ключе по UUID или key_id
    Поддерживает оба формата: /api/keys/{uuid} и /api/keys/{key_id}
    """
    try:
        # Пытаемся определить, это UUID или key_id
        if "-" in identifier:
            # Это UUID
            key = db.query(Key).filter(Key.uuid == identifier).first()
        else:
            # Это key_id
            try:
                key_id = int(identifier)
                key = db.query(Key).filter(Key.id == key_id).first()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid identifier format: {identifier}. Expected UUID or key_id",
                )

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found",
            )

        # Используем общий short_id для всех пользователей
        common_short_id = settings.reality_common_short_id

        return KeyResponse(
            key_id=key.id,  # type: ignore
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,  # Возвращаем общий short_id
            name=key.name,  # type: ignore
            created_at=key.created_at,  # type: ignore
            is_active=bool(key.is_active),  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key: {str(e)}",
        )


@app.get("/api/keys/uuid/{uuid}", response_model=KeyResponse, tags=["Keys"])
async def get_key_by_uuid(
    uuid: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Получение информации о ключе по UUID
    """
    try:
        key = db.query(Key).filter(Key.uuid == uuid).first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with uuid {uuid} not found",
            )

        # Используем общий short_id для всех пользователей
        common_short_id = settings.reality_common_short_id

        return KeyResponse(
            key_id=key.id,  # type: ignore
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,  # Возвращаем общий short_id
            name=key.name,  # type: ignore
            created_at=key.created_at,  # type: ignore
            is_active=bool(key.is_active),  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting key by UUID '{uuid}': {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key: {str(e)}",
        )


@app.get(
    "/api/keys/uuid/{uuid}/config", response_model=VlessLinkResponse, tags=["Keys"]
)
async def get_key_config_by_uuid(
    uuid: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Получение конфигурации (VLESS ссылки) по UUID
    Алиас для GET /api/keys/{key_id}/link, но работает с UUID
    """
    try:
        key = db.query(Key).filter(Key.uuid == uuid).first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with uuid {uuid} not found",
            )

        # Получение публичного ключа Reality
        if not settings.reality_public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reality public key not configured",
            )

        # Конвертируем публичный ключ в URL-safe формат
        public_key = settings.reality_public_key
        try:
            import base64

            if "/" in public_key or "+" in public_key or public_key.endswith("="):
                decoded = base64.b64decode(
                    public_key + "==" if not public_key.endswith("=") else public_key
                )
                public_key = (
                    base64.urlsafe_b64encode(decoded).decode("utf-8").rstrip("=")
                )
        except Exception:
            pass

        # Построение VLESS ссылки
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            dest=settings.reality_dest,
            flow="none",
        )

        return VlessLinkResponse(
            key_id=key.id,  # type: ignore
            vless_link=vless_link,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Error getting key config by UUID '{uuid}': {type(e).__name__}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key config: {str(e)}",
        )


@app.delete("/api/keys/uuid/{uuid}", response_model=KeyDeleteResponse, tags=["Keys"])
async def delete_key_by_uuid(
    uuid: str, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Удаление ключа по UUID
    Алиас для DELETE /api/keys/{key_id}, но работает с UUID
    """
    try:
        key = db.query(Key).filter(Key.uuid == uuid).first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with uuid {uuid} not found",
            )

        key_id = key.id  # type: ignore

        # Удаление пользователя из Xray через API и конфигурационный файл
        email = f"user_{key.id}_{key.uuid[:8]}"

        # Пытаемся удалить через Xray API
        await xray_client.remove_user(email)

        # Удаляем пользователя из конфигурационного файла
        config_success = False
        try:
            common_short_id = settings.reality_common_short_id

            config_success = await config_task_queue.execute_task_and_wait(
                task_type=TaskType.REMOVE_USER,
                uuid=key.uuid,  # type: ignore
                short_id=common_short_id,
                email=email,
                timeout=30.0,
            )
            if config_success:
                logger.info(
                    f"✅ User {key_id} (UUID: {key.uuid[:8]}...) removed from Xray config file"
                )
            else:
                logger.warning(
                    f"⚠️  Failed to remove user {key_id} (UUID: {key.uuid[:8]}...) "
                    f"from Xray config file"
                )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Timeout waiting for config update for key {key_id} (UUID: {key.uuid[:8]}...). "
                f"Trying direct fallback..."
            )
            try:
                common_short_id = settings.reality_common_short_id
                config_success = xray_config_manager.remove_user_from_config(
                    uuid=key.uuid, short_id=common_short_id  # type: ignore
                )
            except Exception as e:
                logger.error(f"❌ Fallback config removal also failed: {e}")
                config_success = False
        except Exception as e:
            logger.error(
                f"❌ Error removing user {key_id} from config: {e}. Trying direct fallback..."
            )
            try:
                common_short_id = settings.reality_common_short_id
                config_success = xray_config_manager.remove_user_from_config(
                    uuid=key.uuid, short_id=common_short_id  # type: ignore
                )
            except Exception as fallback_error:
                logger.error(f"❌ Fallback config removal also failed: {fallback_error}")
                config_success = False

        if not config_success:
            logger.warning(
                f"⚠️  Key {key_id} will be removed from database, but user may still exist in Xray config file. "
                f"Manual cleanup may be required."
            )

        # Удаление из базы данных
        db.delete(key)
        db.commit()

        logger.info(f"Key deleted successfully: {key_id}")

        return KeyDeleteResponse(
            success=True, message=f"Key {key_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting key by UUID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete key: {str(e)}",
        )


@app.post("/api/traffic/sync", tags=["Traffic"])
async def sync_all_traffic(
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
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

                traffic_stat = (
                    db.query(TrafficStats)
                    .filter(TrafficStats.key_id == key.id)
                    .order_by(TrafficStats.updated_at.desc())
                    .first()
                )

                if traffic_stat:
                    traffic_stat.upload = upload  # type: ignore
                    traffic_stat.download = download  # type: ignore
                    traffic_stat.updated_at = int(time.time())  # type: ignore
                else:
                    traffic_stat = TrafficStats(
                        key_id=key.id,
                        upload=upload,
                        download=download,
                        updated_at=int(time.time()),
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
            "errors": error_count,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing all traffic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync traffic: {str(e)}",
        )


@app.post(
    "/api/keys/{key_id}/traffic/reset",
    response_model=TrafficResetResponse,
    tags=["Traffic"],
)
async def reset_traffic(
    key_id: int, token: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """
    Обнуление статистики трафика по конкретному ключу

    - Обнуляет значения upload и download в базе данных
    - Сохраняет предыдущие значения в ответе
    - Обновляет timestamp последнего обновления
    """
    try:
        key = db.query(Key).filter(Key.id == key_id).first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key with id {key_id} not found",
            )

        # Получаем текущую статистику
        traffic_stat = (
            db.query(TrafficStats).filter(TrafficStats.key_id == key_id).first()
        )

        if not traffic_stat:
            # Если статистики нет, создаем новую запись с нулевыми значениями
            traffic_stat = TrafficStats(
                key_id=key_id, upload=0, download=0, updated_at=int(time.time())
            )
            db.add(traffic_stat)
            previous_upload = 0
            previous_download = 0
        else:
            # Сохраняем предыдущие значения
            previous_upload = traffic_stat.upload  # type: ignore
            previous_download = traffic_stat.download  # type: ignore

            # Обнуляем статистику
            traffic_stat.upload = 0  # type: ignore
            traffic_stat.download = 0  # type: ignore
            traffic_stat.updated_at = int(time.time())  # type: ignore

        db.commit()

        logger.info(
            f"🔄 Traffic reset for key {key_id}: "
            f"previous upload={previous_upload}, download={previous_download}"
        )

        return TrafficResetResponse(
            success=True,
            message=f"Traffic reset successfully for key {key_id}",
            key_id=key_id,
            previous_upload=previous_upload,
            previous_download=previous_download,
            previous_total=previous_upload + previous_download,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting traffic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset traffic: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
