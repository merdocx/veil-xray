"""Тесты для database модуля"""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base, Key, TrafficStats, init_db, get_db


def test_init_db():
    """Тест инициализации базы данных"""
    # Создаем временную базу данных
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        test_db_url = f"sqlite:///{db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        
        # Создаем таблицы
        Base.metadata.create_all(bind=test_engine)
        
        # Проверяем, что таблицы созданы
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        assert "keys" in tables
        assert "traffic_stats" in tables
        
        test_engine.dispose()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_db():
    """Тест получения сессии базы данных"""
    # Создаем временную базу данных
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        test_db_url = f"sqlite:///{db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=test_engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        
        # Тестируем get_db
        db_gen = get_db()
        db = next(db_gen)
        
        assert db is not None
        assert hasattr(db, 'query')
        
        # Закрываем генератор
        try:
            next(db_gen)
        except StopIteration:
            pass
        
        test_engine.dispose()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_key_model():
    """Тест модели Key"""
    assert hasattr(Key, '__tablename__')
    assert Key.__tablename__ == "keys"
    assert hasattr(Key, 'id')
    assert hasattr(Key, 'uuid')
    assert hasattr(Key, 'short_id')
    assert hasattr(Key, 'name')
    assert hasattr(Key, 'created_at')
    assert hasattr(Key, 'is_active')
    assert hasattr(Key, 'traffic_stats')


def test_traffic_stats_model():
    """Тест модели TrafficStats"""
    assert hasattr(TrafficStats, '__tablename__')
    assert TrafficStats.__tablename__ == "traffic_stats"
    assert hasattr(TrafficStats, 'id')
    assert hasattr(TrafficStats, 'key_id')
    assert hasattr(TrafficStats, 'upload')
    assert hasattr(TrafficStats, 'download')
    assert hasattr(TrafficStats, 'updated_at')
    assert hasattr(TrafficStats, 'key')


def test_key_traffic_stats_relationship():
    """Тест связи между Key и TrafficStats"""
    # Создаем временную базу данных
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        test_db_url = f"sqlite:///{db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=test_engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        
        db = TestingSessionLocal()
        
        # Создаем ключ
        import time
        key = Key(
            uuid="test-uuid-123",
            short_id="abcd1234",
            name="Test Key",
            created_at=int(time.time()),
            is_active=1
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        
        # Создаем статистику
        traffic_stat = TrafficStats(
            key_id=key.id,
            upload=1000,
            download=2000,
            updated_at=int(time.time())
        )
        db.add(traffic_stat)
        db.commit()
        
        # Проверяем связь
        assert len(key.traffic_stats) == 1
        assert traffic_stat.key.id == key.id
        
        db.close()
        test_engine.dispose()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

