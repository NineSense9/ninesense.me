from contextlib import closing
from pathlib import Path
import shutil
import sqlite3

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, select

from ninesense_guestbook.db import build_session_factory
from ninesense_guestbook.models import Message
from ninesense_guestbook.services.crypto import ContactCipher, EncryptedContact
from ninesense_guestbook.services.outbox import backup_database


SERVER_ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_migrated_database_can_be_backed_up_and_restored(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", sqlite_url(source))
    command.upgrade(config, "head")

    engine, session_factory = build_session_factory(sqlite_url(source))
    cipher = ContactCipher.from_urlsafe_key(TEST_KEY)
    encrypted = cipher.encrypt("restore@example.com")
    with session_factory() as session:
        session.add(
            Message(
                kind="private",
                status="pending",
                nickname="恢复测试",
                contact_type="email",
                contact_nonce=encrypted.nonce,
                contact_ciphertext=encrypted.ciphertext,
                contact_key_version=encrypted.key_version,
                content="确认备份恢复不会丢失私信",
                idempotency_key="r" * 32,
            )
        )
        session.commit()
    engine.dispose()

    backup_database(sqlite_url(source), backup)
    shutil.copy2(backup, restored)

    restored_engine = create_engine(sqlite_url(restored))
    with restored_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "0001_guestbook"
    with closing(sqlite3.connect(restored)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1

    restored_session_engine, restored_factory = build_session_factory(sqlite_url(restored))
    with restored_factory() as session:
        message = session.scalar(select(Message))
        recovered = cipher.decrypt(
            EncryptedContact(
                message.contact_nonce,
                message.contact_ciphertext,
                message.contact_key_version,
            )
        )
        assert recovered == "restore@example.com"
        assert message.content == "确认备份恢复不会丢失私信"
    restored_session_engine.dispose()
    restored_engine.dispose()
