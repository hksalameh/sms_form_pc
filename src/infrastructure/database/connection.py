import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "smscaster.db")

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
