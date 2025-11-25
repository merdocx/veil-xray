"""Конфигурация для тестов"""
import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.database import Base, get_db
from api.main import app
from config.settings import settings


@pytest.fixture(scope="function")
def test_db():
    """Создание тестовой базы данных"""
    # Создание временной базы данных в памяти
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
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


@pytest.fixture
def client(test_db):
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов"""
    return {"Authorization": f"Bearer {settings.api_secret_key}"}

