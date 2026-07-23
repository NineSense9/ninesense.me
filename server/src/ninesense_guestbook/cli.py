import argparse
from getpass import getpass
import re

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import build_session_factory
from .models import Admin
from .services.outbox import backup_database, cleanup_records, process_outbox_once


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


def prompt_password() -> str:
    password = getpass("Password: ")
    confirmation = getpass("Repeat password: ")
    if password != confirmation:
        raise ValueError("passwords do not match")
    validate_admin_password(password)
    return password


def main() -> None:
    parser = argparse.ArgumentParser(prog="ninesense-guestbook")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-admin")
    create.add_argument("--username", required=True)
    reset = subparsers.add_parser("reset-admin-password")
    reset.add_argument("--username", required=True)
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
        if args.command in {"create-admin", "reset-admin-password"}:
            password = prompt_password()
            with session_factory() as db:
                if args.command == "create-admin":
                    create_admin_record(db, args.username, password)
                else:
                    reset_admin_password(db, args.username, password)
        elif args.command == "process-outbox-once":
            process_outbox_once(session_factory, settings)
        elif args.command == "cleanup":
            cleanup_records(session_factory)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
