"""Конфигурация для тестов"""

import os
import tempfile

# До импорта приложения: отдельный лог и без тяжёлого startup (Xray sync).
os.environ["VEIL_SKIP_STARTUP"] = "1"
_test_log_fd, _test_log_path = tempfile.mkstemp(suffix="_pytest.log")
os.close(_test_log_fd)
os.environ["LOG_FILE"] = _test_log_path

import pytest
from unittest.mock import AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.database import (
    Base,
    get_db,
    init_db,
    Key,
    TrafficStats,
)
from api.main import app, xray_client
from config.settings import settings


@pytest.fixture(scope="function", autouse=True)
def test_db(monkeypatch):
    """Создание тестовой базы данных (автоматически для всех тестов)"""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    test_db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

    monkeypatch.setattr("config.settings.settings.database_url", test_db_url)

    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    monkeypatch.setattr("api.database.engine", test_engine)
    monkeypatch.setattr("api.database.SessionLocal", TestingSessionLocal)

    Base.metadata.create_all(bind=test_engine)

    def test_init_db():
        Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr("api.database.init_db", test_init_db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    assert get_db in app.dependency_overrides

    test_db_gen = override_get_db()
    test_db_session = next(test_db_gen)
    try:
        test_db_engine = test_db_session.get_bind()
        assert str(test_db_engine.url) == test_db_url
    finally:
        test_db_session.close()

    yield test_engine

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def mock_xray_client(monkeypatch):
    """Мок для XrayClient (автоматически применяется ко всем тестам)"""
    mock_client = AsyncMock()
    mock_client.add_user = AsyncMock(return_value=True)
    mock_client.remove_user = AsyncMock(return_value=True)
    mock_client.reset_user_stats = AsyncMock(return_value=True)
    mock_client.get_stats = AsyncMock(return_value={"stat": []})
    mock_client.get_user_stats = AsyncMock(return_value={"upload": 0, "download": 0})
    monkeypatch.setattr("api.main.xray_client", mock_client)
    return mock_client


@pytest.fixture(autouse=True)
def clear_traffic_cache():
    """Глобальный traffic_cache в api.main не должен протекать между тестами."""
    import api.main as main_module

    main_module.traffic_cache.clear()
    yield
    main_module.traffic_cache.clear()


@pytest.fixture(autouse=True)
def expand_allowed_ips_for_tests(monkeypatch):
    """Starlette TestClient подставляет client host 'testclient'."""
    monkeypatch.setattr(
        settings,
        "api_allowed_ips",
        settings.api_allowed_ips + ",testclient",
    )


@pytest.fixture(autouse=True)
def mock_reality_settings(monkeypatch):
    """Мок для настроек Reality (чтобы VLESS ссылки работали в тестах)"""
    monkeypatch.setattr(
        "config.settings.settings.reality_public_key", "test_public_key_for_tests"
    )
    monkeypatch.setattr(
        "api.main.settings.reality_public_key", "test_public_key_for_tests"
    )


@pytest.fixture
def client(test_db, mock_xray_client):
    """Тестовый клиент FastAPI с замокированным XrayClient"""
    assert get_db in app.dependency_overrides
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов"""
    return {"Authorization": f"Bearer {settings.api_secret_key}"}
