"""Database connection and session management."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

# Database URL from environment or default to SQLite for development
ENV = os.getenv("ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Default to SQLite for development
    DATABASE_URL = "sqlite:///./trading_platform.db"

# Create engine with appropriate settings
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}

if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif "postgresql" in DATABASE_URL:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)


def get_session():
    """Dependency for getting database session."""
    with SessionLocal() as session:
        yield session


def init_db():
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


async def init_db_async():
    """Async version of database initialization."""
    init_db()
