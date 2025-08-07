from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from typing import Generator

# Base class for all models
Base = declarative_base()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading:trading@localhost:5432/tradingbot"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Ensures proper session lifecycle management.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all tables (use with caution!)."""
    Base.metadata.drop_all(bind=engine)