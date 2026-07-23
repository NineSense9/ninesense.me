from ninesense_guestbook.db import Base


def test_guestbook_models_register_all_tables():
    from ninesense_guestbook import models  # noqa: F401

    assert set(Base.metadata.tables) == {
        "messages",
        "admins",
        "admin_sessions",
        "outbox",
    }


def test_sqlite_connection_enables_integrity_pragmas(db_session):
    foreign_keys = db_session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one()
    busy_timeout = db_session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 5000

