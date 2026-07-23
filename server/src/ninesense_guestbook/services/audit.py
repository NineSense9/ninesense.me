import json
from typing import TypeAlias

from sqlalchemy.orm import Session

from ..admin_models import AuditEvent


AuditScalar: TypeAlias = str | int
AuditValue: TypeAlias = AuditScalar | list[str]

ALLOWED_DETAIL_KEYS = frozenset(
    {
        "client_label",
        "reason_code",
        "changed_fields",
        "release_version",
        "record_count",
    }
)
ALLOWED_OUTCOMES = frozenset({"success", "failure", "denied"})


def _validate_details(details: dict[str, AuditValue]) -> None:
    for key, value in details.items():
        if key not in ALLOWED_DETAIL_KEYS:
            raise ValueError(f"audit detail key is not allowed: {key}")
        if key == "changed_fields":
            if (
                not isinstance(value, list)
                or len(value) > 30
                or any(
                    not isinstance(item, str)
                    or not item
                    or len(item) > 64
                    for item in value
                )
            ):
                raise ValueError("audit detail value is invalid")
            continue
        if type(value) not in {str, int}:
            raise ValueError("audit detail value is invalid")
        if isinstance(value, str) and len(value) > 160:
            raise ValueError("audit detail value is invalid")


def record_audit(
    db: Session,
    *,
    action: str,
    outcome: str,
    admin_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, AuditValue] | None = None,
) -> AuditEvent:
    normalized_action = action.strip()
    if not normalized_action or len(normalized_action) > 64:
        raise ValueError("audit action is invalid")
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError("audit outcome is invalid")
    if target_type is not None and len(target_type) > 32:
        raise ValueError("audit target type is invalid")
    if target_id is not None and len(target_id) > 64:
        raise ValueError("audit target id is invalid")

    safe_details = details or {}
    _validate_details(safe_details)
    event = AuditEvent(
        admin_id=admin_id,
        action=normalized_action,
        outcome=outcome,
        target_type=target_type,
        target_id=target_id,
        details_json=json.dumps(
            safe_details,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    db.add(event)
    return event
