import pytest
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError

from ninesense_guestbook.services.crypto import ContactCipher, EncryptedContact
from ninesense_guestbook.web.schemas import MessageCreate, classify_contact


TEST_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def valid_message(**overrides):
    payload = {
        "kind": "public",
        "nickname": " 访客 ",
        "contact": "13800138000",
        "content": " 你好，网站做得不错。 ",
        "idempotency_key": "a" * 32,
        "website": "",
        "form_started_at": 1,
    }
    payload.update(overrides)
    return MessageCreate(**payload)


def test_contact_round_trip_uses_random_nonce():
    cipher = ContactCipher.from_urlsafe_key(TEST_KEY)

    first = cipher.encrypt("13800138000")
    second = cipher.encrypt("13800138000")

    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext
    assert cipher.decrypt(first) == "13800138000"


def test_wrong_key_or_version_cannot_decrypt_contact():
    cipher = ContactCipher.from_urlsafe_key(TEST_KEY)
    encrypted = cipher.encrypt("hello@example.com")
    wrong_key = ContactCipher.from_urlsafe_key(
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
    )

    with pytest.raises(InvalidTag):
        wrong_key.decrypt(encrypted)
    with pytest.raises(ValueError, match="unsupported contact key version"):
        cipher.decrypt(EncryptedContact(encrypted.nonce, encrypted.ciphertext, 2))


def test_message_schema_trims_text_and_classifies_contact():
    message = valid_message()

    assert message.nickname == "访客"
    assert message.content == "你好，网站做得不错。"
    assert classify_contact(message.contact) == "phone"
    assert classify_contact("hello@example.com") == "email"


@pytest.mark.parametrize(
    "contact",
    ["not-contact", "13800abc000", "name@localhost", "1" * 101],
)
def test_contact_must_be_email_or_mobile(contact):
    with pytest.raises(ValidationError):
        valid_message(contact=contact)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nickname", "a"),
        ("nickname", "访\n客"),
        ("content", "a"),
        ("content", "hello\x00world"),
        ("content", "<script>alert(1)</script>"),
    ],
)
def test_message_rejects_invalid_plain_text(field, value):
    with pytest.raises(ValidationError):
        valid_message(**{field: value})


def test_optional_contact_is_normalized_to_none():
    assert valid_message(contact="   ").contact is None

