"""Модели базы данных"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    BigInteger,
    ForeignKey,
    Index,
)
from sqlalchemy import event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from config.settings import settings

Base = declarative_base()


class Key(Base):  # type: ignore
    """Модель ключа пользователя"""

    __tablename__ = "keys"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, nullable=False)
    short_id = Column(
        String(8), index=True, nullable=False
    )  # Убрано unique, так как используется общий short_id
    name = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    is_active = Column(Integer, default=1)
    last_used_at = Column(BigInteger, nullable=True)

    # Связь с статистикой трафика
    traffic_stats = relationship(
        "TrafficStats", back_populates="key", cascade="all, delete-orphan"
    )


class TrafficStats(Base):  # type: ignore
    """Модель статистики трафика"""

    __tablename__ = "traffic_stats"

    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(Integer, ForeignKey("keys.id"), nullable=False, index=True)
    upload = Column(BigInteger, default=0)
    download = Column(BigInteger, default=0)
    updated_at = Column(BigInteger, nullable=False)

    # Связь с ключом
    key = relationship("Key", back_populates="traffic_stats")

    # Индекс для быстрого поиска по key_id
    __table_args__ = (Index("idx_key_id", "key_id"),)


# Создание движка базы данных
# Для SQLite нужно убедиться, что директория существует
import os
from pathlib import Path

db_url = settings.database_url
if db_url.startswith("sqlite:///"):
    db_path = Path(db_url.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {}
engine_kwargs = {}

if "sqlite" in db_url:
    # SQLite под нагрузкой легко уходит в блокировки/ожидания. Нам важно:
    # - включить busy timeout
    # - включить WAL для конкурентных read/write
    # - не упираться в лимиты QueuePool при длинных запросах
    connect_args = {"check_same_thread": False, "timeout": 30}
    engine_kwargs = {"poolclass": NullPool}

engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)


if "sqlite" in db_url:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore[no-redef]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA temp_store=MEMORY;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=5000;")
        finally:
            cursor.close()


# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Получение сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
