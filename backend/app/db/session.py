import logging
from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")
settings = get_settings()
engine = create_engine(settings.active_database_url, pool_pre_ping=True) if settings.active_database_url else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False) if engine else None


def get_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    try:
        with SessionLocal() as session:
            yield session
    except OperationalError as error:
        logger.error("Database operational error: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable. Please try again.",
        ) from error
    except Exception as error:
        logger.error("Database session exception: %s", error)
        raise

