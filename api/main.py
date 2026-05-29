"""Основной файл API сервера"""

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    Request,
    Path as PathParam,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from typing import Any, List, Optional
import time
import logging
import logging.handlers
import asyncio
import os
import secrets
import base64
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import api.database as db_module
from api.database import get_db, Key, TrafficStats, init_db
from api.errors import raise_http_for_db_error
from api.models import (
    KeyCreate,
    KeyResponse,
    KeyDeleteResponse,
    TrafficResponse,
    VlessLinkResponse,
    KeyLinksResponse,
    KeyLinkProfile,
    KeyListResponse,
    TrafficResetResponse,
    XraySyncStartResponse,
    XraySyncStatusResponse,
)
from api.xray_client import XrayClient
from api.xray_config import XrayConfigManager
from api.task_queue import config_task_queue, TaskType
from api.utils import (
    generate_uuid,
    generate_short_id,
    build_vless_link,
    build_vless_link_with_transport,
    build_trojan_reality_link,
    parse_key_identifier,
    normalize_reality_public_key,
    build_client_config,
    build_happ_singbox_config,
    build_auto_subscription_links,
    build_auto_singbox_subscription_config,
)
from config.settings import settings

# Простой in-memory кэш для статистики трафика
traffic_cache: dict[
    int, tuple[int, int, int, int]
] = {}  # key_id -> (upload, download, cached_at, updated_at)
ENABLE_BACKGROUND_TRAFFIC_SYNC = settings.enable_background_traffic_sync
BACKGROUND_TRAFFIC_SYNC_INTERVAL_S = settings.background_traffic_sync_interval_s
BACKGROUND_TRAFFIC_SYNC_BATCH_SIZE = settings.background_traffic_sync_batch_size
_traffic_sync_lock = asyncio.Lock()
_traffic_sync_cursor = 0

# Фоновая синхронизация пользователей БД → Xray (startup / sync-config)
_user_sync_task: Optional[asyncio.Task] = None
_user_sync_state: dict[str, Any] = {"status": "idle"}


def _sync_iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_user_sync_status() -> dict[str, Any]:
    """Снимок состояния синхронизации (для API)."""
    return dict(_user_sync_state)


def schedule_user_sync(trigger: str) -> str:
    """
    Запускает sync в фоне. Возвращает 'started' или 'already_running'.
    Вызывать только из running event loop.
    """
    global _user_sync_task
    if _user_sync_task is not None and not _user_sync_task.done():
        return "already_running"
    _user_sync_state.update(
        {
            "status": "running",
            "trigger": trigger,
            "started_at": _sync_iso_now(),
            "finished_at": None,
            "synced_via_api": None,
            "synced_via_config": None,
            "skipped": None,
            "errors": None,
            "total_keys": None,
            "error_message": None,
        }
    )
    _user_sync_task = asyncio.create_task(_run_user_sync_job(trigger))
    return "started"


async def _run_user_sync_job(trigger: str) -> None:
    try:
        result = await sync_users_with_xray()
        _user_sync_state.update(
            {
                "status": "completed",
                "trigger": trigger,
                "finished_at": _sync_iso_now(),
                "synced_via_api": result.get("synced_api_count", 0),
                "synced_via_config": result.get("synced_config_count", 0),
                "skipped": result.get("skipped_count", 0),
                "errors": result.get("error_count", 0),
                "total_keys": result.get("total_keys", 0),
                "error_message": None,
            }
        )
    except asyncio.CancelledError:
        _user_sync_state.update(
            {
                "status": "idle",
                "finished_at": _sync_iso_now(),
                "error_message": "cancelled",
            }
        )
        raise
    except Exception as e:
        logger.error(f"❌ Background user sync failed ({trigger}): {e}")
        _user_sync_state.update(
            {
                "status": "failed",
                "trigger": trigger,
                "finished_at": _sync_iso_now(),
                "error_message": str(e),
            }
        )


# Публичные пути без IP whitelist (health для мониторинга)
_PUBLIC_PATHS = frozenset({"/", "/health"})

# Типовые пути сканеров — не засоряют WARNING в логах
_SCANNER_PROBE_EXACT = frozenset(
    {
        "/",
        "/favicon.ico",
        "/robots.txt",
        "/sitemap.xml",
        "/metrics",
        "/.env",
        "/health",
    }
)
_SCANNER_PROBE_SUBSTRINGS = (
    ".env",
    ".git",
    "wp-",
    "phpmyadmin",
    "/admin",
    "/.well-known",
    "/actuator",
)


def _is_scanner_probe(path: str) -> bool:
    """Запросы ботов/сканеров — логируем на DEBUG."""
    if path in _SCANNER_PROBE_EXACT:
        return True
    lower = path.lower()
    return any(marker in lower for marker in _SCANNER_PROBE_SUBSTRINGS)


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
            encoding="utf-8",
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

# Инициализация FastAPI (документация включается только при API_ENABLE_DOCS=true)
_docs_kw = {}
if not settings.api_enable_docs:
    _docs_kw = {"docs_url": None, "redoc_url": None, "openapi_url": None}


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

            if status_code >= 400:
                log_msg = (
                    f"⚠️  {request_method} {full_path} - "
                    f"Status: {status_code} - "
                    f"Time: {process_time:.3f}s"
                )
                if status_code == 403 and _is_scanner_probe(request_path):
                    logger.debug(log_msg)
                else:
                    logger.warning(log_msg)
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


def _is_trusted_local_proxy(host: str | None) -> bool:
    """True если соединение с loopback (в т.ч. ::ffff:127.0.0.1 от Nginx → Uvicorn)."""
    if host is None:
        return False
    if host in ("127.0.0.1", "::1"):
        return True
    # IPv4-mapped IPv6 (часто так приходит peer за reverse proxy)
    if host.startswith("::ffff:") and host.rsplit(":", 1)[-1] == "127.0.0.1":
        return True
    return False


def _get_client_ip(request: Request) -> str | None:
    """
    IP клиента для политики доступа.

    Заголовки X-Real-IP / X-Forwarded-For учитываем только если соединение
    пришло с доверенного reverse proxy (loopback на том же хосте).
    Иначе используется только request.client.host — подделка заголовков не проходит.

    Если request.client отсутствует (бывает за Nginx + uvicorn), доверяем заголовкам:
    до приложения снаружи доступен только 127.0.0.1, заголовки выставляет Nginx.
    """
    direct = request.client.host if request.client else None
    if _is_trusted_local_proxy(direct):
        xri = request.headers.get("X-Real-IP")
        if xri:
            return xri.strip().split(",")[0].strip()
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return direct

    # Uvicorn/Starlette иногда не заполняют client за reverse proxy
    if direct is None:
        xri = request.headers.get("X-Real-IP")
        if xri:
            return xri.strip().split(",")[0].strip()
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()

    return direct


# Middleware для проверки IP whitelist
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки IP whitelist - разрешает запросы только с разрешенных IP"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        allowed_ips = set(settings.allowed_ip_list)
        if not allowed_ips:
            logger.warning(
                f"⚠️  Access denied: API_ALLOWED_IPS is empty for {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Access denied. API IP whitelist is not configured."
                },
            )

        client_ip = _get_client_ip(request)

        if not client_ip:
            logger.warning(
                f"⚠️  Access denied: IP address could not be determined for {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied. Your IP address is not authorized."},
            )

        if client_ip in allowed_ips:
            return await call_next(request)

        deny_msg = f"⚠️  Access denied for IP {client_ip} to {request.url.path}"
        if _is_scanner_probe(request.url.path):
            logger.debug(deny_msg)
        else:
            logger.warning(deny_msg)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Access denied. Your IP address is not authorized."},
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


# Security
security = HTTPBearer()

# Инициализация Xray клиента и менеджера конфигурации
xray_client = XrayClient()
xray_config_manager = XrayConfigManager()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена авторизации"""
    token = credentials.credentials
    key = settings.api_secret_key
    if len(token) != len(key) or not secrets.compare_digest(token, key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return token


async def sync_users_with_xray() -> dict[str, int]:
    """
    Синхронизация пользователей из БД с Xray API.

    Добавляет в Xray всех активных пользователей, которые есть в БД,
    но отсутствуют в Xray (например, если Xray был перезапущен или API был недоступен).
    Также обновляет конфигурационный файл для обеспечения консистентности.
    """
    logger.info("🔄 Starting synchronization of users with Xray API...")
    empty = {
        "synced_api_count": 0,
        "synced_config_count": 0,
        "skipped_count": 0,
        "error_count": 0,
        "total_keys": 0,
    }

    db: Session = next(get_db())
    try:
        # Получаем все активные ключи из БД
        keys = db.query(Key).filter(Key.is_active == 1).all()

        if not keys:
            logger.info("No active keys found in database. Nothing to sync.")
            return empty

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

        users_for_config = [(key.uuid, f"user_{key.id}_{key.uuid[:8]}") for key in keys]
        try:
            bulk = xray_config_manager.bulk_sync_vless_clients(users_for_config)
            if bulk.get("saved"):
                synced_config_count = bulk.get("added", 0) + bulk.get(
                    "already_present", 0
                )
                logger.info(
                    "✅ Bulk config sync: "
                    f"added={bulk.get('added')} "
                    f"already_present={bulk.get('already_present')} "
                    "(single save_config)"
                )
            elif bulk.get("error"):
                error_count += 1
                logger.error(f"Bulk config sync failed: {bulk.get('error')}")
        except Exception as config_error:
            error_count += 1
            logger.error(f"Bulk config sync exception: {config_error}")

        for key in keys:
            try:
                email = f"user_{key.id}_{key.uuid[:8]}"
                api_updated = False

                if xray_api_available:
                    try:
                        api_success = await xray_client.add_user(
                            uuid=key.uuid, email=email, flow=settings.reality_flow
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

                if not api_updated:
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
        return {
            "synced_api_count": synced_api_count,
            "synced_config_count": synced_config_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "total_keys": len(keys),
        }

    except Exception as e:
        logger.error(f"❌ Error during user synchronization: {e}")
        raise
    finally:
        db.close()


async def sync_all_traffic_stats():
    """Фоновая задача для синхронизации статистики всех ключей"""
    global _traffic_sync_cursor

    if not ENABLE_BACKGROUND_TRAFFIC_SYNC:
        logger.info(
            "⏸️  Background traffic sync is disabled (ENABLE_BACKGROUND_TRAFFIC_SYNC=false)"
        )
        return

    while True:
        try:
            await asyncio.sleep(BACKGROUND_TRAFFIC_SYNC_INTERVAL_S)

            if _traffic_sync_lock.locked():
                continue

            async with _traffic_sync_lock:
                with db_module.SessionLocal() as db:
                    keys = (
                        db.query(Key.id, Key.uuid)
                        .filter(Key.is_active == 1)
                        .order_by(Key.id.asc())
                        .all()
                    )

                if not keys:
                    continue

                start = _traffic_sync_cursor % len(keys)
                batch = keys[start : start + BACKGROUND_TRAFFIC_SYNC_BATCH_SIZE]
                if len(batch) < BACKGROUND_TRAFFIC_SYNC_BATCH_SIZE:
                    batch += keys[: BACKGROUND_TRAFFIC_SYNC_BATCH_SIZE - len(batch)]
                _traffic_sync_cursor = (start + len(batch)) % len(keys)

                now = int(time.time())
                stats_by_key: dict[int, tuple[int, int, int]] = {}

                for key_id, key_uuid in batch:
                    try:
                        email = f"user_{key_id}_{str(key_uuid)[:8]}"
                        xray_stats = await xray_client.get_user_stats(email)
                        upload = int(xray_stats.get("upload", 0) or 0)
                        download = int(xray_stats.get("download", 0) or 0)
                        stats_by_key[int(key_id)] = (upload, download, now)
                    except Exception as e:
                        logger.debug(f"Traffic sync skipped for key {key_id}: {e}")

                if not stats_by_key:
                    continue

                key_ids = list(stats_by_key.keys())
                try:
                    with db_module.SessionLocal() as db:
                        existing = {
                            ts.key_id: ts
                            for ts in db.query(TrafficStats)
                            .filter(TrafficStats.key_id.in_(key_ids))
                            .all()
                        }
                        for key_id, (
                            upload,
                            download,
                            updated_at,
                        ) in stats_by_key.items():
                            ts = existing.get(key_id)
                            if ts:
                                ts.upload = upload  # type: ignore
                                ts.download = download  # type: ignore
                                ts.updated_at = updated_at  # type: ignore
                            else:
                                db.add(
                                    TrafficStats(
                                        key_id=key_id,
                                        upload=upload,
                                        download=download,
                                        updated_at=updated_at,
                                    )
                                )
                        db.commit()
                except Exception as e:
                    logger.warning(f"Background traffic sync DB update failed: {e}")

        except Exception as e:
            logger.error(f"Error in background traffic sync: {e}")


async def _app_startup() -> None:
    """Инициализация при запуске."""
    logger.info("🚀 Starting Veil Xray API server...")

    logger.info("📦 Initializing database...")
    init_db()
    logger.info("✅ Database initialized")

    await config_task_queue.start()
    logger.info("✅ Config task queue started")

    common_short_id = settings.reality_common_short_id
    xray_config_manager.ensure_common_short_id(common_short_id)
    logger.info(f"✅ Common short_id '{common_short_id}' ensured in Xray config")

    schedule_user_sync("startup")
    logger.info("✅ User sync scheduled in background (startup)")

    if ENABLE_BACKGROUND_TRAFFIC_SYNC:
        asyncio.create_task(sync_all_traffic_stats())
        logger.info("✅ Background traffic sync task started")
    else:
        logger.info("⏸️  Background traffic sync task is disabled")

    logger.info("✅ API server started successfully")


async def _app_shutdown() -> None:
    """Остановка при завершении работы."""
    global _user_sync_task
    logger.info("🛑 Shutting down Veil Xray API server...")
    if _user_sync_task is not None and not _user_sync_task.done():
        _user_sync_task.cancel()
        try:
            await _user_sync_task
        except asyncio.CancelledError:
            pass
    await config_task_queue.stop()
    logger.info("✅ Config task queue stopped")
    logger.info("✅ API server stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup / shutdown."""
    if os.getenv("VEIL_SKIP_STARTUP") != "1":
        await _app_startup()
    yield
    if os.getenv("VEIL_SKIP_STARTUP") != "1":
        await _app_shutdown()


app = FastAPI(
    title="Veil Xray API",
    description="API для управления VLESS+Reality VPN сервером",
    version="1.3.18",
    lifespan=lifespan,
    **_docs_kw,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(IPWhitelistMiddleware)
# app.add_middleware(ForceHTTPSMiddleware)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _is_peak_hours_msk() -> bool:
    """08:00–23:59 MSK — не запускать тяжёлый sync-config (см. PRODUCTION_RUNBOOK)."""
    hour = datetime.now(ZoneInfo("Europe/Moscow")).hour
    return 8 <= hour <= 23


def _health_payload() -> dict[str, str]:
    return {"status": "ok", "service": "veil-xray-api"}


@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def root():
    """Проверка работоспособности API (корень и /health для мониторинга)."""
    return _health_payload()


@app.get(
    "/api/system/xray/sync-status",
    response_model=XraySyncStatusResponse,
    tags=["System"],
)
async def get_xray_sync_status(token: str = Depends(verify_token)):
    """Статус фоновой синхронизации пользователей БД → Xray."""
    return XraySyncStatusResponse(**get_user_sync_status())


@app.post(
    "/api/system/xray/sync-config",
    response_model=XraySyncStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["System"],
)
async def sync_xray_config(token: str = Depends(verify_token)):
    """
    Запуск синхронизации активных ключей в фоне (не блокирует HTTP).
    Статус: GET /api/system/xray/sync-status
    """
    if _is_peak_hours_msk() and os.getenv("VEIL_ALLOW_SYNC_IN_PEAK") != "1":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "sync-config disabled during peak hours (08:00–23:59 MSK). "
                "Retry off-peak or set VEIL_ALLOW_SYNC_IN_PEAK=1 on server."
            ),
        )
    outcome = schedule_user_sync("api")
    if outcome == "already_running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Xray user sync is already in progress",
        )
    return XraySyncStartResponse(
        success=True,
        status="started",
        message="Xray user synchronization started in background",
    )


@app.post("/api/keys", response_model=KeyResponse, tags=["Keys"])
async def create_key(
    key_data: KeyCreate,
    background_tasks: BackgroundTasks,
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
        db.flush()
        db.add(
            TrafficStats(key_id=new_key.id, upload=0, download=0, updated_at=timestamp)
        )
        db.commit()
        db.refresh(new_key)

        key_id = int(new_key.id)  # type: ignore
        email = f"user_{key_id}_{uuid_value[:8]}"

        async def _provision_user() -> None:
            try:
                ok = await xray_client.add_user(uuid_value, email)
                if not ok:
                    logger.warning(
                        f"⚠️  Xray API add_user returned false for key {key_id}. "
                        f"User may become available after restart/sync."
                    )
            except Exception as e:
                logger.warning(f"⚠️  Xray API add_user failed for key {key_id}: {e}")

            try:
                await config_task_queue.add_task(
                    task_type=TaskType.ADD_USER,
                    uuid=uuid_value,
                    short_id=common_short_id,  # Используем общий short_id
                    email=email,
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Config queue add_task failed for key {key_id}: {e}"
                )

        background_tasks.add_task(_provision_user)

        logger.info(f"Key created successfully: {key_id}, UUID: {uuid_value[:8]}...")

        return KeyResponse(
            key_id=key_id,
            uuid=new_key.uuid,  # type: ignore
            short_id=common_short_id,  # Возвращаем общий short_id
            name=new_key.name,  # type: ignore
            created_at=new_key.created_at,  # type: ignore
            is_active=bool(new_key.is_active),  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_http_for_db_error(
            e,
            operation="create_key",
            default_detail="Failed to create key",
            integrity_conflict_detail=(
                "A key with this UUID already exists. Please try again."
            ),
            db=db,
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
        # Определяем тип идентификатора (UUID или key_id)
        try:
            uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if is_uuid:
            key = db.query(Key).filter(Key.uuid == uuid_value).first()
        else:
            key = db.query(Key).filter(Key.id == key_id_value).first()

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
        raise_http_for_db_error(
            e,
            operation="delete_key",
            default_detail="Failed to delete key",
            db=db,
        )


@app.get("/api/keys/{key_id}/traffic", response_model=TrafficResponse, tags=["Traffic"])
async def get_traffic(
    key_id: int = PathParam(
        ..., gt=0, description="ID ключа (должен быть положительным числом)"
    ),
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
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

        # Проверяем кэш статистики трафика
        current_time = int(time.time())
        cached_stats = traffic_cache.get(key_id)

        if (
            cached_stats
            and (current_time - cached_stats[2]) < settings.traffic_cache_ttl_s
        ):
            # Используем кэшированные значения
            upload = cached_stats[0]
            download = cached_stats[1]
            updated_at = cached_stats[3]
            return TrafficResponse(
                key_id=key_id,
                upload=upload,
                download=download,
                total=upload + download,
                last_updated=updated_at,
            )
        else:
            # Освобождаем DB-сессию перед медленными операциями (Xray stats)
            try:
                db.close()
            except Exception:
                pass

            # Получение статистики из Xray
            email = f"user_{key.id}_{key.uuid[:8]}"
            xray_stats = await xray_client.get_user_stats(email)

            upload = xray_stats.get("upload", 0)
            download = xray_stats.get("download", 0)
            updated_at = int(time.time())

            # Сохраняем в кэш
            traffic_cache[key_id] = (upload, download, current_time, updated_at)

            # Обновление статистики в базе данных короткой транзакцией
            try:
                with db_module.SessionLocal() as db2:
                    traffic_stat = (
                        db2.query(TrafficStats)
                        .filter(TrafficStats.key_id == key_id)
                        .first()
                    )

                    if traffic_stat:
                        traffic_stat.upload = upload  # type: ignore
                        traffic_stat.download = download  # type: ignore
                        traffic_stat.updated_at = updated_at  # type: ignore
                    else:
                        db2.add(
                            TrafficStats(
                                key_id=key_id,
                                upload=upload,
                                download=download,
                                updated_at=updated_at,
                            )
                        )

                    db2.commit()
            except Exception as e:
                logger.warning(f"Traffic DB update failed for key {key_id}: {e}")

        return TrafficResponse(
            key_id=key_id,
            upload=upload,
            download=download,
            total=upload + download,
            last_updated=updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_http_for_db_error(
            e,
            operation="get_traffic",
            default_detail="Failed to get traffic",
            db=db,
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
        # Определяем тип идентификатора (UUID или key_id)
        try:
            uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if is_uuid:
            key = db.query(Key).filter(Key.uuid == uuid_value).first()
        else:
            key = db.query(Key).filter(Key.id == key_id_value).first()

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

        # Построение VLESS (основной профиль: tcp:443)
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,  # Используем общий short_id из настроек
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,  # Используем URL-safe формат
            dest="vless_tcp_443",
            flow=settings.reality_flow,
        )

        return VlessLinkResponse(key_id=key.id, vless_link=vless_link)  # type: ignore

    except HTTPException:
        raise
    except Exception as e:
        raise_http_for_db_error(
            e,
            operation=f"get_vless_link:{identifier}",
            default_detail="Failed to generate VLESS link",
            db=db,
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
        raise_http_for_db_error(
            e,
            operation="list_keys",
            default_detail="Failed to list keys",
            db=db,
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
        # Определяем тип идентификатора (UUID или key_id)
        try:
            uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if is_uuid:
            key = db.query(Key).filter(Key.uuid == uuid_value).first()
        else:
            key = db.query(Key).filter(Key.id == key_id_value).first()

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

        # Построение VLESS (основной профиль: tcp:443)
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            dest="vless_tcp_443",
            flow=settings.reality_flow,
        )

        return VlessLinkResponse(
            key_id=key.id,  # type: ignore
            vless_link=vless_link,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_http_for_db_error(
            e,
            operation=f"get_key_config:{identifier}",
            default_detail="Failed to get key config",
            db=db,
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
        # Определяем тип идентификатора (UUID или key_id)
        try:
            uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if is_uuid:
            key = db.query(Key).filter(Key.uuid == uuid_value).first()
        else:
            key = db.query(Key).filter(Key.id == key_id_value).first()

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
        raise_http_for_db_error(
            e,
            operation=f"get_key:{identifier}",
            default_detail="Failed to get key",
            db=db,
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
        raise_http_for_db_error(
            e,
            operation=f"get_key_by_uuid:{uuid}",
            default_detail="Failed to get key",
            db=db,
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

        # Построение VLESS (основной профиль: tcp:443)
        common_short_id = settings.reality_common_short_id
        vless_link = build_vless_link(
            uuid=key.uuid,  # type: ignore
            short_id=common_short_id,
            server_address=settings.domain,
            port=settings.reality_port,
            sni=settings.reality_sni,
            fingerprint=settings.reality_fingerprint,
            public_key=public_key,
            dest="vless_tcp_443",
            flow=settings.reality_flow,
        )

        return VlessLinkResponse(
            key_id=key.id,  # type: ignore
            vless_link=vless_link,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_http_for_db_error(
            e,
            operation=f"get_key_config_by_uuid:{uuid}",
            default_detail="Failed to get key config",
            db=db,
        )


@app.get(
    "/api/keys/{identifier}/links",
    response_model=KeyLinksResponse,
    tags=["Keys"],
)
async def get_key_links(
    identifier: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Получение набора профилей подключения для ключа.

    Профили:
    - vless_tcp_443: основной (как раньше)
    - vless_tcp_alt: fallback tcp на альтернативном порту
    - vless_xhttp: fallback транспорт xhttp
    - trojan_tcp: fallback trojan+reality
    """
    # Определяем тип идентификатора (UUID или key_id)
    try:
        uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if is_uuid:
        key = db.query(Key).filter(Key.uuid == uuid_value).first()
    else:
        key = db.query(Key).filter(Key.id == key_id_value).first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found",
        )

    if not settings.reality_public_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reality public key not configured",
        )

    public_key = normalize_reality_public_key(settings.reality_public_key)
    public_key_b = (
        normalize_reality_public_key(settings.reality_public_key_b)
        if settings.reality_sni_b_enabled and settings.reality_public_key_b
        else None
    )

    sid = settings.reality_common_short_id

    links: list[KeyLinkProfile] = []

    links.append(
        KeyLinkProfile(
            profile="vless_tcp_443",
            link=build_vless_link_with_transport(
                uuid=key.uuid,  # type: ignore
                short_id=sid,
                server_address=settings.domain,
                port=settings.reality_port,
                sni=settings.reality_sni,
                fingerprint=settings.reality_fingerprint,
                public_key=public_key,
                flow=settings.reality_flow,
                transport="tcp",
                path="/",
                remark="vless_tcp_443",
            ),
        )
    )

    links.append(
        KeyLinkProfile(
            profile="vless_tcp_alt",
            link=build_vless_link_with_transport(
                uuid=key.uuid,  # type: ignore
                short_id=sid,
                server_address=settings.domain,
                port=settings.reality_alt_port_tcp,
                sni=settings.reality_sni,
                fingerprint=settings.reality_fingerprint,
                public_key=public_key,
                flow=settings.reality_flow,
                transport="tcp",
                path="/",
                remark="vless_tcp_alt",
            ),
        )
    )

    links.append(
        KeyLinkProfile(
            profile="vless_xhttp",
            link=build_vless_link_with_transport(
                uuid=key.uuid,  # type: ignore
                short_id=sid,
                server_address=settings.domain,
                port=settings.reality_xhttp_port,
                sni=settings.reality_sni,
                fingerprint=settings.reality_fingerprint,
                public_key=public_key,
                transport="xhttp",
                path=settings.reality_xhttp_path,
                remark="vless_xhttp",
            ),
        )
    )

    links.append(
        KeyLinkProfile(
            profile="trojan_tcp",
            link=build_trojan_reality_link(
                password=key.uuid,  # type: ignore
                server_address=settings.domain,
                port=settings.trojan_reality_port,
                sni=settings.reality_sni,
                fingerprint=settings.reality_fingerprint,
                public_key=public_key,
                short_id=sid,
                path="/",
                remark="trojan_tcp",
            ),
        )
    )

    if public_key_b and settings.reality_sni_b:
        links.append(
            KeyLinkProfile(
                profile="vless_tcp_443_sni_b",
                link=build_vless_link_with_transport(
                    uuid=key.uuid,  # type: ignore
                    short_id=settings.reality_short_id_b,
                    server_address=settings.domain,
                    port=settings.reality_port_sni_b,
                    sni=settings.reality_sni_b,
                    fingerprint=settings.reality_fingerprint_b_value,
                    public_key=public_key_b,
                    flow=settings.reality_flow,
                    transport="tcp",
                    path="/",
                    remark="vless_tcp_443_sni_b",
                ),
            )
        )

    return KeyLinksResponse(key_id=key.id, links=links)  # type: ignore


@app.get(
    "/api/keys/{identifier}/client-config",
    tags=["Keys"],
)
async def get_client_config(
    identifier: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Готовый клиентский JSON-конфиг с несколькими профилями и автопереключением по пингу.
    """
    try:
        uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if is_uuid:
        key = db.query(Key).filter(Key.uuid == uuid_value).first()
    else:
        key = db.query(Key).filter(Key.id == key_id_value).first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found",
        )

    if not settings.reality_public_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reality public key not configured",
        )

    public_key = normalize_reality_public_key(settings.reality_public_key)
    public_key_b = None
    if settings.reality_sni_b_enabled and settings.reality_public_key_b:
        public_key_b = normalize_reality_public_key(settings.reality_public_key_b)

    cfg = build_client_config(
        key_id=int(key.id),  # type: ignore
        uuid=str(key.uuid),  # type: ignore
        public_key=public_key,
        public_key_b=public_key_b,
    )
    return JSONResponse(content=cfg)


@app.get(
    "/api/keys/{identifier}/subscription",
    tags=["Keys"],
)
async def get_key_subscription(
    identifier: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
    format: str = "base64",
    profiles: str = "auto",
):
    """
    Подписка с несколькими профилями и автовыбором.

    profiles:
    - auto (по умолчанию): 448/446/447/443 — безопасный набор для мобильных + автоподбор
    - happ: как auto (совместимость)
    - primary / stable / all: наборы ссылок без sing-box urltest

    format:
    - base64 / plain: список vless:// (клиент сам выбирает по ping)
    - singbox / happ_json: JSON sing-box с urltest (рекомендуется для Happ)
    - singbox_b64: base64(JSON) — URL подписки для Happ «добавить по ссылке»
    """
    try:
        uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if is_uuid:
        key = db.query(Key).filter(Key.uuid == uuid_value).first()
    else:
        key = db.query(Key).filter(Key.id == key_id_value).first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found",
        )
    if not settings.reality_public_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reality public key not configured",
        )

    public_key = normalize_reality_public_key(settings.reality_public_key)
    public_key_b = None
    if settings.reality_sni_b_enabled and settings.reality_public_key_b:
        public_key_b = normalize_reality_public_key(settings.reality_public_key_b)
    uid = str(key.uuid)  # type: ignore

    if profiles in ("auto", "happ"):
        lines = build_auto_subscription_links(
            uuid=uid, public_key=public_key, public_key_b=public_key_b
        )
    else:
        links_resp = await get_key_links(identifier=identifier, token=token, db=db)
        profile_filter: dict[str, set[str]] = {
            "primary": {"vless_tcp_443"},
            "stable": {"vless_tcp_443", "vless_tcp_alt"},
            "all": {
                "vless_tcp_443",
                "vless_tcp_alt",
                "vless_xhttp",
                "trojan_tcp",
                "vless_tcp_443_sni_b",
            },
        }
        allowed = profile_filter.get(profiles)
        if allowed is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid profiles. Use 'auto', 'happ', 'primary', 'stable', or 'all'.",
            )
        lines = [x.link for x in links_resp.links if x.profile in allowed]

    if not lines:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No links matched the requested profile set",
        )

    if format in ("singbox", "happ_json"):
        cfg = build_auto_singbox_subscription_config(
            uuid=uid, public_key=public_key, public_key_b=public_key_b
        )
        return JSONResponse(content=cfg)

    if format == "singbox_b64":
        cfg = build_auto_singbox_subscription_config(
            uuid=uid, public_key=public_key, public_key_b=public_key_b
        )
        raw = json.dumps(cfg, ensure_ascii=False, separators=(",", ":"))
        b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return Response(content=b64, media_type="text/plain; charset=utf-8")

    payload = "\n".join(lines) + "\n"

    if format == "plain":
        return Response(content=payload, media_type="text/plain; charset=utf-8")

    if format != "base64":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid format. Use 'base64', 'plain', 'singbox', 'singbox_b64', or 'happ_json'.",
        )

    b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return Response(content=b64, media_type="text/plain; charset=utf-8")


@app.get(
    "/api/keys/{identifier}/happ-config",
    tags=["Keys"],
)
async def get_happ_config(
    identifier: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    sing-box JSON для Happ (iOS): DNS через proxy, порт 448 без Vision-flow.
    Импорт в Happ: Профиль → Импорт → из буфера / файла JSON.
    """
    try:
        uuid_value, key_id_value, is_uuid = parse_key_identifier(identifier)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if is_uuid:
        key = db.query(Key).filter(Key.uuid == uuid_value).first()
    else:
        key = db.query(Key).filter(Key.id == key_id_value).first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found",
        )

    if not settings.reality_public_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reality public key not configured",
        )

    public_key = normalize_reality_public_key(settings.reality_public_key)
    cfg = build_happ_singbox_config(uuid=str(key.uuid), public_key=public_key)  # type: ignore
    return JSONResponse(content=cfg)


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
        raise_http_for_db_error(
            e,
            operation=f"delete_key_by_uuid:{uuid}",
            default_detail="Failed to delete key",
            db=db,
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
        keys = db.query(Key.id, Key.uuid).filter(Key.is_active == 1).all()

        # Освобождаем DB-сессию перед потенциально долгими вызовами к Xray
        try:
            db.close()
        except Exception:
            pass

        updated_at = int(time.time())
        stats_by_key: dict[int, tuple[int, int, int]] = {}
        error_count = 0

        for key_id, key_uuid in keys:
            try:
                email = f"user_{key_id}_{str(key_uuid)[:8]}"
                xray_stats = await xray_client.get_user_stats(email)
                upload = int(xray_stats.get("upload", 0) or 0)
                download = int(xray_stats.get("download", 0) or 0)
                stats_by_key[int(key_id)] = (upload, download, updated_at)
            except Exception as e:
                error_count += 1
                logger.debug(f"Traffic sync skipped for key {key_id}: {e}")

        updated_count = 0
        if stats_by_key:
            key_ids = list(stats_by_key.keys())
            with db_module.SessionLocal() as db2:
                existing = {
                    ts.key_id: ts
                    for ts in db2.query(TrafficStats)
                    .filter(TrafficStats.key_id.in_(key_ids))
                    .all()
                }
                for key_id, (upload, download, ts_updated_at) in stats_by_key.items():
                    ts = existing.get(key_id)
                    if ts:
                        ts.upload = upload  # type: ignore
                        ts.download = download  # type: ignore
                        ts.updated_at = ts_updated_at  # type: ignore
                    else:
                        db2.add(
                            TrafficStats(
                                key_id=key_id,
                                upload=upload,
                                download=download,
                                updated_at=ts_updated_at,
                            )
                        )
                    updated_count += 1
                db2.commit()

        return {
            "success": True,
            "message": f"Synced {updated_count} keys, {error_count} errors",
            "updated": updated_count,
            "errors": error_count,
        }

    except Exception as e:
        raise_http_for_db_error(
            e,
            operation="sync_all_traffic",
            default_detail="Failed to sync traffic",
            db=db,
        )


@app.post(
    "/api/keys/{key_id}/traffic/reset",
    response_model=TrafficResetResponse,
    tags=["Traffic"],
)
async def reset_traffic(
    key_id: int = PathParam(
        ..., gt=0, description="ID ключа (должен быть положительным числом)"
    ),
    token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Обнуление статистики трафика по конкретному ключу

    - Обнуляет значения upload и download в базе данных
    - Обнуляет счётчики этого пользователя в Xray (statsquery -reset=true)
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

        # Проверяем, что ключ активен
        if not key.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reset traffic for inactive key {key_id}",
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

            # Обнуляем статистику в БД
            traffic_stat.upload = 0  # type: ignore
            traffic_stat.download = 0  # type: ignore
            traffic_stat.updated_at = int(time.time())  # type: ignore

        db.commit()

        # Сохраняем идентификатор Xray до закрытия сессии БД
        key_uuid = key.uuid  # type: ignore
        email = f"user_{key_id}_{str(key_uuid)[:8]}"

        # Очищаем кэш статистики для этого ключа
        traffic_cache.pop(key_id, None)

        # Освобождаем DB-сессию перед вызовом Xray (subprocess в thread)
        try:
            db.close()
        except Exception:
            pass

        # Обнуляем статистику в Xray через statsquery -reset=true (только счётчики этого пользователя)
        try:
            reset_ok = await xray_client.reset_user_stats(email)
            if not reset_ok:
                logger.warning(
                    f"⚠️  Failed to reset Xray stats for {email}. "
                    f"Traffic reset in DB completed, but Xray may still show old values until next sync."
                )
        except Exception as xray_error:
            logger.warning(
                f"⚠️  Error resetting traffic in Xray for key {key_id}: {xray_error}. "
                f"Traffic reset in DB completed successfully."
            )

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
        raise_http_for_db_error(
            e,
            operation=f"reset_traffic:{key_id}",
            default_detail="Failed to reset traffic",
            db=db,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
