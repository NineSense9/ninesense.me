from enum import Enum


class MessageKind(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class MessageStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    HANDLED = "handled"
    ARCHIVED = "archived"
    REJECTED = "rejected"


ALLOWED_TRANSITIONS = {
    MessageKind.PUBLIC: {
        (MessageStatus.PENDING, MessageStatus.PUBLISHED),
        (MessageStatus.PENDING, MessageStatus.REJECTED),
        (MessageStatus.PUBLISHED, MessageStatus.PENDING),
        (MessageStatus.PUBLISHED, MessageStatus.ARCHIVED),
    },
    MessageKind.PRIVATE: {
        (MessageStatus.PENDING, MessageStatus.HANDLED),
        (MessageStatus.PENDING, MessageStatus.REJECTED),
        (MessageStatus.HANDLED, MessageStatus.ARCHIVED),
    },
}


def require_transition(
    kind: MessageKind,
    current: MessageStatus,
    target: MessageStatus,
) -> None:
    if (current, target) not in ALLOWED_TRANSITIONS[kind]:
        raise ValueError(
            f"invalid transition: {kind.value} {current.value} -> {target.value}"
        )

