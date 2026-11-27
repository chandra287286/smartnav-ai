import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings, mask_database_url

logger = logging.getLogger("smartnav.database")


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif url.startswith("postgresql"):
        connect_args = {"connect_timeout": 10}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Validate database configuration, enable PostGIS on PostgreSQL, and create tables."""
    from app.models import entities  # noqa: F401

    settings = get_settings()
    settings.validate_database_configuration()

    masked = mask_database_url(str(engine.url))
    logger.info("Connecting to database (%s): %s", engine.dialect.name, masked)

    try:
        if engine.dialect.name == "postgresql":
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        logger.error(
            "Database initialization failed for %s: %s. "
            "Check DATABASE_URL, network/firewall reachability, SSL mode, and database credentials.",
            masked,
            exc,
        )
        raise


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
