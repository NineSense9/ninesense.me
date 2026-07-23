from pathlib import Path
import shutil

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from ninesense_guestbook.app import create_app
from ninesense_guestbook.config import Settings
from ninesense_guestbook.services.outbox import backup_database


CONTACT_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
SECURITY_KEY = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="

def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def row_counts(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return {
                table: connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table}"
                ).scalar_one()
                for table in ("messages", "admins", "outbox", "admin_sessions")
            }
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


def test_legacy_business_data_survives_backup_upgrade_and_rollback(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "backups" / "legacy-backup.sqlite3"
    isolated = tmp_path / "migration-check" / "guestbook.sqlite3"
    source_url = f"sqlite:///{source.as_posix()}"
    isolated_url = f"sqlite:///{isolated.as_posix()}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    monkeypatch.setenv("NINESENSE_DATABASE_URL", source_url)
    command.upgrade(config, "0001_guestbook")
    engine = create_engine(source_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO admins (id, username, password_hash, active) "
                "VALUES (1, 'owner', 'legacy-password-hash', 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO messages "
                "(id, kind, status, nickname, content, idempotency_key, "
                "submitted_at, published_at, updated_at) VALUES "
                "(?, 'public', 'published', '旧站访客', '迁移保留测试', ?, ?, ?, ?)",
                (
                    "a" * 32,
                    "b" * 64,
                    "2026-07-20 08:00:00",
                    "2026-07-20 09:00:00",
                    "2026-07-20 09:00:00",
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO outbox "
                "(id, message_id, attempts, next_attempt_at, last_error) "
                "VALUES (1, ?, 2, '2026-07-21 08:00:00', 'legacy-error')",
                ("a" * 32,),
            )
            connection.exec_driver_sql(
                "INSERT INTO admin_sessions "
                "(id_hash, admin_id, csrf_hash, expires_at) VALUES (?, 1, ?, ?)",
                ("c" * 64, "d" * 64, "2026-07-30 08:00:00"),
            )
    finally:
        engine.dispose()

    before = row_counts(source_url)
    assert before == {
        "messages": 1,
        "admins": 1,
        "outbox": 1,
        "admin_sessions": 1,
    }
    backup_database(source_url, backup)
    isolated.parent.mkdir(parents=True)
    shutil.copy2(backup, isolated)

    monkeypatch.setenv("NINESENSE_DATABASE_URL", isolated_url)
    command.upgrade(config, "head")
    upgraded = row_counts(isolated_url)
    assert upgraded == {
        "messages": 1,
        "admins": 1,
        "outbox": 1,
        "admin_sessions": 0,
    }

    settings = Settings(
        database_url=isolated_url,
        contact_key=CONTACT_KEY,
        security_key=SECURITY_KEY,
        session_pepper="migration-session-pepper",
        rate_limit_key="migration-rate-limit-key",
    )
    application = create_app(settings)
    with TestClient(application) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        feed = client.get("/api/guestbook/messages")
        assert feed.status_code == 200
        assert [item["content"] for item in feed.json()["items"]] == [
            "迁移保留测试"
        ]
    application.state.engine.dispose()

    command.downgrade(config, "0001_guestbook")
    assert row_counts(isolated_url) == upgraded
    command.upgrade(config, "head")
    assert row_counts(isolated_url) == upgraded
