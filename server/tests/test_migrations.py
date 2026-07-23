from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_admin_foundation_migration_round_trip(tmp_path: Path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite3'}"
    monkeypatch.setenv("NINESENSE_DATABASE_URL", database_url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")
    upgraded = table_names(database_url)
    assert {
        "admin_login_challenges",
        "admin_recovery_codes",
        "audit_events",
        "admin_notifications",
    } <= upgraded

    command.downgrade(config, "0001_guestbook")
    downgraded = table_names(database_url)
    assert "audit_events" not in downgraded
    assert "admins" in downgraded
