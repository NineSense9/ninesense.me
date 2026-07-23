from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ninesense_guestbook import models as _models  # noqa: F401
from ninesense_guestbook.app import create_app
from ninesense_guestbook.config import Settings
from ninesense_guestbook.db import Base


@pytest.fixture
def app(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        contact_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        session_pepper="test-session-pepper",
        rate_limit_key="test-rate-limit-key",
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(app):
    with app.state.session_factory() as session:
        yield session

