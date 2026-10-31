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


def make_engine(*, migration=False):
    url = database_url()
    options = {}
    if url.startswith("postgresql"):
        statement, lock, idle = (
            (60000, 30000, 60000) if migration else (5000, 2000, 10000)
        )
        options["connect_args"] = {
            "connect_timeout": 5,
            "options": f"-c statement_timeout={statement} -c lock_timeout={lock} -c idle_in_transaction_session_timeout={idle}",
        }
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        pool_recycle=300,
        **options,
    )
