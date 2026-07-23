import json

import pytest
from sqlalchemy import select

from ninesense_guestbook.admin_models import AuditEvent
from ninesense_guestbook.services.audit import record_audit


def test_audit_accepts_allowlisted_details(db_session):
    record_audit(
        db_session,
        action="session.login",
        outcome="success",
        details={"client_label": "Chrome / Windows"},
    )
    db_session.commit()

    event = db_session.scalar(select(AuditEvent))
    assert event.details_json == '{"client_label":"Chrome / Windows"}'


@pytest.mark.parametrize("key", ["password", "contact", "ip", "cookie"])
def test_audit_rejects_sensitive_or_unknown_detail_keys(db_session, key):
    with pytest.raises(ValueError, match="audit detail key"):
        record_audit(
            db_session,
            action="session.login",
            outcome="failure",
            details={key: "secret"},
        )


def test_audit_accepts_a_bounded_flat_changed_field_list(db_session):
    record_audit(
        db_session,
        action="settings.updated",
        outcome="success",
        details={"changed_fields": ["title", "description"]},
    )
    db_session.flush()

    event = db_session.scalar(select(AuditEvent))
    assert json.loads(event.details_json) == {
        "changed_fields": ["title", "description"]
    }


def test_audit_rejects_nested_or_oversized_detail_values(db_session):
    with pytest.raises(ValueError, match="audit detail value"):
        record_audit(
            db_session,
            action="settings.updated",
            outcome="success",
            details={"changed_fields": [{"secret": "value"}]},
        )

    with pytest.raises(ValueError, match="audit detail value"):
        record_audit(
            db_session,
            action="session.login",
            outcome="success",
            details={"client_label": "x" * 161},
        )


def test_audit_does_not_commit_the_callers_transaction(db_session):
    record_audit(db_session, action="session.login", outcome="success")
    db_session.rollback()

    assert db_session.scalars(select(AuditEvent)).all() == []
