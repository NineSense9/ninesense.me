import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9][0-9 -]{6,19}$")
HTML_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


def clean_text(value: str, minimum: int, maximum: int, allow_newlines: bool) -> str:
    value = value.strip()
    allowed_controls = {"\n", "\t"} if allow_newlines else set()
    if any(ord(character) < 32 and character not in allowed_controls for character in value):
        raise ValueError("contains unsupported control characters")
    if HTML_TAG.search(value):
        raise ValueError("HTML is not supported")
    if not minimum <= len(value) <= maximum:
        raise ValueError(f"length must be between {minimum} and {maximum}")
    return value


def classify_contact(value: str | None) -> Literal["email", "phone"] | None:
    if value is None:
        return None
    if EMAIL.fullmatch(value):
        return "email"
    if PHONE.fullmatch(value):
        return "phone"
    raise ValueError("contact must be an email address or phone number")


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["public", "private"]
    nickname: str
    contact: str | None = None
    content: str
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{32,64}$")
    website: str = Field(default="", max_length=200)
    form_started_at: float = Field(ge=0)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        return clean_text(value, 2, 24, False)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return clean_text(value, 2, 500, True)

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = clean_text(value, 7, 100, False)
        classify_contact(value)
        return value


class PublicMessage(BaseModel):
    id: str
    nickname: str
    date: str
    content: str
    reply: str | None
    reply_date: str | None


class PublicFeed(BaseModel):
    items: list[PublicMessage]
    next_cursor: str | None

