import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be configured")
    return url


def make_engine():
    return create_engine(
        database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5
    )
