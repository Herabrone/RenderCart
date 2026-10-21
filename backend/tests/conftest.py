from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from rendercart.auth import models as auth_models  # noqa: F401
from rendercart.auth import router as auth_router
from rendercart.core.db import Base, get_db
from rendercart.main import app


@pytest.fixture
def test_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        yield db
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, test_session: Session
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(auth_router, "enforce_auth_limits", lambda *args, **kwargs: None)

    def override_get_db() -> Generator[Session, None, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
