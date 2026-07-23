import pytest
from sqlalchemy import select

from ninesense_guestbook.cli import create_admin_record, validate_admin_password
from ninesense_guestbook.models import Admin


def test_admin_password_must_be_long_and_varied():
    for password in ("short", "alllowercasepassword", "ALLUPPERCASEPASSWORD", "123456789012"):
        with pytest.raises(ValueError):
            validate_admin_password(password)

    validate_admin_password("Strong-password-2026")


def test_create_admin_refuses_to_add_a_second_account(db_session):
    create_admin_record(db_session, "ninesense", "Strong-password-2026")

    with pytest.raises(ValueError, match="already exists"):
        create_admin_record(db_session, "another", "Another-password-2026")

    assert len(db_session.scalars(select(Admin)).all()) == 1

