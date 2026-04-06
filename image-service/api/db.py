from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import settings

DATABASE_URL = settings.resolved_database_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Validate the PostgreSQL connection at startup."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to PostgreSQL at {DATABASE_URL}: {exc}") from exc
