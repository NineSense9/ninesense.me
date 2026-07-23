from ninesense_guestbook.db import Base


def test_application_models_register_all_tables():
    from ninesense_guestbook import admin_models, models  # noqa: F401

    assert set(Base.metadata.tables) == {
        "messages",
        "admins",
        "admin_sessions",
        "admin_login_challenges",
        "admin_recovery_codes",
        "audit_events",
        "admin_notifications",
        "outbox",
    }


def test_sqlite_connection_enables_integrity_pragmas(db_session):
    foreign_keys = db_session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one()
    busy_timeout = db_session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 5000
