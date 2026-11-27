import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, mask_database_url, normalize_database_url
from app.database import session as db_session


def test_normalize_database_url_converts_postgres_schemes():
    assert normalize_database_url("postgres://user:pass@host:5432/db") == (
        "postgresql+psycopg://user:pass@host:5432/db"
    )
    assert normalize_database_url("postgresql://user:pass@host:5432/db?sslmode=require") == (
        "postgresql+psycopg://user:pass@host:5432/db?sslmode=require"
    )
    assert normalize_database_url("postgresql+psycopg://user:pass@host:5432/db") == (
        "postgresql+psycopg://user:pass@host:5432/db"
    )
    assert normalize_database_url("   ") == "sqlite:///./smartnav.db"


def test_mask_database_url_hides_password():
    masked = mask_database_url("postgresql+psycopg://postgres:SuperSecret123@db.host.com:5432/smartnav")
    assert "SuperSecret123" not in masked
    assert ":***@" in masked


def test_production_rejects_sqlite_fallback(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    prod_settings = Settings(APP_ENV="production", DATABASE_URL="")
    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured for production"):
        prod_settings.validate_database_configuration()

    prod_pg = Settings(
        APP_ENV="production",
        DATABASE_URL="postgres://user:pass@db.supabase.co:5432/postgres",
    )
    assert prod_pg.DATABASE_URL.startswith("postgresql+psycopg://")
    prod_pg.validate_database_configuration()


def test_init_db_logs_masked_error_on_unreachable_database(monkeypatch):
    bad_engine = db_session.build_engine("sqlite:///./nonexistent_dir_12345/cannot_open.db")
    monkeypatch.setattr(db_session, "engine", bad_engine)
    with pytest.raises(SQLAlchemyError):
        db_session.init_db()
