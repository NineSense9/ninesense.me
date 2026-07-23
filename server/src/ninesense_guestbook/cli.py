import argparse
from getpass import getpass
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .admin_models import AdminLoginChallenge, AdminRecoveryCode
from .config import get_settings
from .db import build_session_factory
from .models import Admin, AdminSession
from .services.admin_notifications import create_notification
from .services.audit import record_audit
from .services.outbox import backup_database, cleanup_records, process_outbox_once
from .services.sessions import as_utc


def validate_admin_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    if not re.search(r"[a-z]", password):
        raise ValueError("password must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("password must contain an uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("password must contain a number")


def create_admin_record(db: Session, username: str, password: str) -> Admin:
    validate_admin_password(password)
    if db.scalar(select(Admin.id).limit(1)) is not None:
        raise ValueError("an admin account already exists")
    admin = Admin(
        username=username.strip(),
        password_hash=PasswordHasher().hash(password),
        active=True,
    )
    db.add(admin)
    db.commit()
    return admin


def reset_admin_password(db: Session, username: str, password: str) -> None:
    validate_admin_password(password)
    admin = db.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        raise ValueError("admin account does not exist")
    admin.password_hash = PasswordHasher().hash(password)
    db.commit()


def reset_admin_mfa(
    db: Session,
    username: str,
    password: str,
) -> None:
    admin = db.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        raise ValueError("admin account does not exist")
    try:
        valid = PasswordHasher().verify(admin.password_hash, password)
    except (VerificationError, VerifyMismatchError):
        valid = False
    if not valid:
        raise ValueError("password is incorrect")

    admin.totp_secret_nonce = None
    admin.totp_secret_ciphertext = None
    admin.totp_secret_key_version = None
    admin.totp_enabled_at = None
    db.execute(
        delete(AdminRecoveryCode).where(AdminRecoveryCode.admin_id == admin.id)
    )
    db.execute(
        delete(AdminLoginChallenge).where(AdminLoginChallenge.admin_id == admin.id)
    )
    db.execute(delete(AdminSession).where(AdminSession.admin_id == admin.id))
    create_notification(
        db,
        severity="warning",
        category="security",
        title="两步验证已从服务器终端重置",
        message="所有后台会话和恢复码均已撤销。",
    )
    record_audit(
        db,
        action="mfa.reset_from_cli",
        outcome="success",
        admin_id=admin.id,
    )
    db.commit()


def list_admin_sessions(db: Session, username: str) -> list[dict[str, str]]:
    admin = db.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        raise ValueError("admin account does not exist")
    rows = list(
        db.scalars(
            select(AdminSession)
            .where(AdminSession.admin_id == admin.id)
            .order_by(AdminSession.created_at.desc(), AdminSession.public_id.desc())
        )
    )
    return [
        {
            "public_id": row.public_id,
            "client_label": row.client_label,
            "expires_at": as_utc(row.expires_at).isoformat(),
        }
        for row in rows
    ]


def revoke_admin_sessions(db: Session, username: str) -> int:
    admin = db.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        raise ValueError("admin account does not exist")
    result = db.execute(delete(AdminSession).where(AdminSession.admin_id == admin.id))
    count = int(result.rowcount or 0)
    record_audit(
        db,
        action="session.revoked_from_cli",
        outcome="success",
        admin_id=admin.id,
        details={"record_count": count},
    )
    db.commit()
    return count


def prompt_password() -> str:
    password = getpass("Password: ")
    confirmation = getpass("Repeat password: ")
    if password != confirmation:
        raise ValueError("passwords do not match")
    validate_admin_password(password)
    return password


def prompt_current_password() -> str:
    password = getpass("Current password: ")
    confirmation = getpass("Repeat current password: ")
    if password != confirmation:
        raise ValueError("passwords do not match")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(prog="ninesense-guestbook")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-admin")
    create.add_argument("--username", required=True)
    reset = subparsers.add_parser("reset-admin-password")
    reset.add_argument("--username", required=True)
    reset_mfa = subparsers.add_parser("reset-admin-mfa")
    reset_mfa.add_argument("--username", required=True)
    list_sessions = subparsers.add_parser("list-admin-sessions")
    list_sessions.add_argument("--username", required=True)
    revoke_sessions = subparsers.add_parser("revoke-admin-sessions")
    revoke_sessions.add_argument("--username", required=True)
    subparsers.add_parser("process-outbox-once")
    subparsers.add_parser("cleanup")
    backup = subparsers.add_parser("backup-db")
    backup.add_argument("--output", required=True)
    args = parser.parse_args()

    settings = get_settings()
    if args.command == "backup-db":
        backup_database(settings.database_url, args.output)
        return

    engine, session_factory = build_session_factory(settings.database_url)
    try:
        if args.command in {
            "create-admin",
            "reset-admin-password",
            "reset-admin-mfa",
            "list-admin-sessions",
            "revoke-admin-sessions",
        }:
            with session_factory() as db:
                if args.command == "create-admin":
                    password = prompt_password()
                    create_admin_record(db, args.username, password)
                elif args.command == "reset-admin-password":
                    password = prompt_password()
                    reset_admin_password(db, args.username, password)
                elif args.command == "reset-admin-mfa":
                    reset_admin_mfa(db, args.username, prompt_current_password())
                elif args.command == "list-admin-sessions":
                    for item in list_admin_sessions(db, args.username):
                        print(
                            f"{item['public_id']}\t{item['client_label']}\t{item['expires_at']}"
                        )
                else:
                    count = revoke_admin_sessions(db, args.username)
                    print(f"revoked {count} session(s)")
        elif args.command == "process-outbox-once":
            process_outbox_once(session_factory, settings)
        elif args.command == "cleanup":
            cleanup_records(session_factory)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
