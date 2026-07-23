import pytest

from ninesense_guestbook.domain.messages import MessageKind, MessageStatus, require_transition


def test_public_message_can_publish_then_archive():
    require_transition(MessageKind.PUBLIC, MessageStatus.PENDING, MessageStatus.PUBLISHED)
    require_transition(MessageKind.PUBLIC, MessageStatus.PUBLISHED, MessageStatus.ARCHIVED)


def test_private_message_cannot_publish():
    with pytest.raises(ValueError, match="invalid transition"):
        require_transition(MessageKind.PRIVATE, MessageStatus.PENDING, MessageStatus.PUBLISHED)

