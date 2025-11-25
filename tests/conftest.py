"""Конфигурация для тестов"""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.database import (
    Base,
    get_db,
    init_db,
    Key,
    TrafficStats,
)  # Импортируем модели для регистрации в Base
from api.main import app, xray_client
from config.settings import settings


@pytest.fixture(scope="function", autouse=True)
def test_db(monkeypatch):
    """Создание тестовой базы данных (автоматически для всех тестов)"""
    # Создание временной базы данных в файле (in-memory имеет проблемы с соединениями)
    import tempfile

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)  # Закрываем файловый дескриптор, SQLAlchemy откроет файл сам
    test_db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

    # Переопределяем database_url в settings для тестов
    monkeypatch.setattr("config.settings.settings.database_url", test_db_url)

    # Переопределяем engine и SessionLocal в api.database
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    # Переопределяем engine и SessionLocal
    monkeypatch.setattr("api.database.engine", test_engine)
    monkeypatch.setattr("api.database.SessionLocal", TestingSessionLocal)

    # Создаем таблицы СРАЗУ
    Base.metadata.create_all(bind=test_engine)

    # Переопределяем init_db чтобы использовать наш engine
    def test_init_db():
        Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr("api.database.init_db", test_init_db)

    # Переопределяем get_db чтобы использовать наш SessionLocal
    # ВАЖНО: Используем замыкание для доступа к TestingSessionLocal
    def override_get_db():
        # Используем TestingSessionLocal из замыкания
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Убеждаемся, что override применяется ДО создания клиента
    # Очищаем все предыдущие overrides
    app.dependency_overrides.clear()

    # Устанавливаем наш override
    app.dependency_overrides[get_db] = override_get_db

    # Проверяем, что override установлен
    assert (
        get_db in app.dependency_overrides
    ), f"get_db override не установлен! Overrides: {list(app.dependency_overrides.keys())}"

    # Дополнительная проверка: убеждаемся, что override работает
    test_db_gen = override_get_db()
    test_db_session = next(test_db_gen)
    try:
        test_db_engine = test_db_session.get_bind()
        assert (
            str(test_db_engine.url) == test_db_url
        ), f"Engine URL не совпадает! Got: {test_db_engine.url}, Expected: {test_db_url}"
    finally:
        test_db_session.close()

    yield test_engine

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()  # Закрываем соединения
    # Удаляем временный файл БД
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture(autouse=True)
def disable_startup_event(monkeypatch):
    """Отключаем startup_event в тестах, чтобы избежать проблем с БД"""

    # Отключаем startup_event полностью
    async def mock_startup():
        # В тестах не нужно инициализировать БД или запускать фоновые задачи
        pass

    # Заменяем startup_event на мок ПЕРЕД созданием клиента
    monkeypatch.setattr("api.main.startup_event", mock_startup)

    # Также отключаем вызов startup_event при создании TestClient
    # TestClient не должен вызывать startup события
    original_startup = None
    try:
        from fastapi.applications import FastAPI

        # Отключаем автоматический вызов startup событий
        pass
    except:
        pass


@pytest.fixture(autouse=True)
def mock_xray_client(monkeypatch):
    """Мок для XrayClient (автоматически применяется ко всем тестам)"""
    mock_client = AsyncMock()

    # Мокируем методы XrayClient
    mock_client.add_user = AsyncMock(return_value=True)
    mock_client.remove_user = AsyncMock(return_value=True)
    mock_client.get_stats = AsyncMock(return_value={"stat": []})
    mock_client.get_user_stats = AsyncMock(return_value={"upload": 0, "download": 0})

    # Заменяем глобальный xray_client на мок
    monkeypatch.setattr("api.main.xray_client", mock_client)

    return mock_client


@pytest.fixture(autouse=True)
def mock_reality_settings(monkeypatch):
    """Мок для настроек Reality (чтобы VLESS ссылки работали в тестах)"""
    # Устанавливаем тестовый публичный ключ
    monkeypatch.setattr(
        "config.settings.settings.reality_public_key", "test_public_key_for_tests"
    )
    monkeypatch.setattr(
        "api.main.settings.reality_public_key", "test_public_key_for_tests"
    )


@pytest.fixture
def client(test_db, mock_xray_client, disable_startup_event):
    """Тестовый клиент FastAPI с замокированным XrayClient"""
    # Таблицы уже созданы в test_db fixture
    # dependency_overrides уже применены в test_db fixture
    # Создаем клиент - startup_event отключен через disable_startup_event

    # Убеждаемся, что override применен
    assert (
        get_db in app.dependency_overrides
    ), f"get_db override не применен! Overrides: {list(app.dependency_overrides.keys())}"

    # Создаем TestClient БЕЗ вызова startup событий
    # Используем TestClient с явным указанием, что startup события не нужны
    test_client = TestClient(app)

    # Убеждаемся, что override все еще применен после создания клиента
    assert (
        get_db in app.dependency_overrides
    ), f"get_db override потерян после создания TestClient! Overrides: {list(app.dependency_overrides.keys())}"

    return test_client


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов"""
    return {"Authorization": f"Bearer {settings.api_secret_key}"}
