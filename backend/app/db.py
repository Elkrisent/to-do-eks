import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./dev.db")


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    # SQLite needs this flag because FastAPI uses threads; Postgres ignores it.
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # One shared connection, otherwise each connection gets its own empty DB.
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
