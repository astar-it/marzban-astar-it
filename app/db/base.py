from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_POOL_SIZE,
    SQLIALCHEMY_MAX_OVERFLOW,
)

# Fix for postgres:// URLs - SQLAlchemy 1.4+ requires postgresql://
# This handles common URLs from services like Heroku, Render, etc.
_DB_URL = SQLALCHEMY_DATABASE_URL
if _DB_URL.startswith('postgres://'):
    _DB_URL = _DB_URL.replace('postgres://', 'postgresql://', 1)

IS_SQLITE = _DB_URL.startswith('sqlite')
IS_POSTGRESQL = _DB_URL.startswith('postgresql')
IS_MYSQL = _DB_URL.startswith('mysql')

if IS_SQLITE:
    engine = create_engine(
        _DB_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        _DB_URL,
        pool_size=SQLALCHEMY_POOL_SIZE,
        max_overflow=SQLIALCHEMY_MAX_OVERFLOW,
        pool_recycle=3600,
        pool_timeout=10,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
