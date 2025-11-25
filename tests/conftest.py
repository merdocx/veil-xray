"""Конфигурация для тестов"""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.database import Base, get_db
from api.main import app, xray_client
from config.settings import settings


@pytest.fixture(scope="function", autouse=True)
def test_db(monkeypatch):
    """Создание тестовой базы данных (автоматически для всех тестов)"""
    # Создание временной базы данных в памяти
    test_db_url = "sqlite:///:memory:"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    
    # Создаем таблицы ПЕРЕД созданием SessionLocal
    Base.metadata.create_all(bind=engine)
    
    # Переопределяем database_url в settings для тестов
    monkeypatch.setattr('config.settings.settings.database_url', test_db_url)
    
    # Переопределяем engine и SessionLocal в api.database
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr('api.database.engine', engine)
    monkeypatch.setattr('api.database.SessionLocal', TestingSessionLocal)
    
    # Переопределяем init_db чтобы использовать наш engine
    def test_init_db():
        Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('api.database.init_db', test_init_db)
    
    # Переопределяем get_db чтобы использовать наш SessionLocal
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield engine
    
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


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
    monkeypatch.setattr('api.main.xray_client', mock_client)
    
    return mock_client


@pytest.fixture(autouse=True)
def mock_reality_settings(monkeypatch):
    """Мок для настроек Reality (чтобы VLESS ссылки работали в тестах)"""
    # Устанавливаем тестовый публичный ключ
    monkeypatch.setattr('config.settings.settings.reality_public_key', 'test_public_key_for_tests')
    monkeypatch.setattr('api.main.settings.reality_public_key', 'test_public_key_for_tests')


@pytest.fixture
def client(test_db, mock_xray_client):
    """Тестовый клиент FastAPI с замокированным XrayClient"""
    # Убеждаемся, что БД инициализирована
    from api.database import init_db
    init_db()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов"""
    return {"Authorization": f"Bearer {settings.api_secret_key}"}

