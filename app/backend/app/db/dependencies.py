"""Database dependencies for FastAPI endpoints."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """Yield a transactional SQLAlchemy session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

