import os
import sys
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool


def _resolve_db_path() -> str:
    """Return a writable persistent database path for source and packaged builds."""
    if getattr(sys, "frozen", False):
        base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(base_dir, "SMSCaster")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "smscaster.db")

    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "smscaster.db")
    )


DB_PATH = _resolve_db_path()

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    poolclass=NullPool,
    connect_args={"check_same_thread": False},
)

SessionFactory = sessionmaker(bind=engine, autoflush=False)
Session = scoped_session(SessionFactory)


@contextmanager
def get_session():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    from .models import Base

    Base.metadata.create_all(bind=engine)
