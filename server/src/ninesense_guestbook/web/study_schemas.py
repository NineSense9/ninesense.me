from datetime import date, time
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import clean_text


SubjectValue = Literal["math", "408", "english", "politics"]
TaskStatusValue = Literal[
    "planned",
    "in_progress",
    "completed",
    "incomplete",
    "cancelled",
]


class PublicCompletion(BaseModel):
    completed: int
    closed: int
    rate: float | None


class PublicStudyTask(BaseModel):
    id: int
    kind: Literal["study", "rest"]
    subject: SubjectValue | None
    start_time: str
    end_time: str
    title: str
    description: str
    status: TaskStatusValue


class PublicExamEvent(BaseModel):
    id: int
    kind: str
    title: str
    date_status: Literal["estimated", "confirmed"]
    start_date: str
    end_date: str | None
    description: str
    source_url: str | None
    countdown_target: bool


class PublicToday(BaseModel):
    date: str
    countdown_days: int | None
    countdown_target: str | None
    next_exam_event: PublicExamEvent | None
    active_subject: SubjectValue | None
    updated_at: str
    reflection: str
    completion: PublicCompletion
    total_focus_seconds: int
    subjects: dict[str, int]
    tasks: list[PublicStudyTask]


class PublicRecentDay(BaseModel):
    date: str
    reflection: str
    completion: PublicCompletion
    total_focus_seconds: int
    subjects: dict[str, int]
    tasks: list[PublicStudyTask]


class PublicRecent(BaseModel):
    items: list[PublicRecentDay]


class PublicMonth(BaseModel):
    month: str
    total_seconds: int
    subjects: dict[str, int]
    daily: list[dict[str, int | str]]
    completion: PublicCompletion


class PublicExamList(BaseModel):
    items: list[PublicExamEvent]


def _clean_optional_text(
    value: str | None,
    *,
    maximum: int,
    allow_newlines: bool,
) -> str | None:
    if value is None:
        return None
    if not value.strip():
        return ""
    return clean_text(value, 1, maximum, allow_newlines)


def _validate_kind_subject(kind: str, subject: str | None) -> None:
    if kind == "study" and subject is None:
        raise ValueError("study tasks require a subject")
    if kind == "rest" and subject is not None:
        raise ValueError("rest tasks cannot have a subject")


class ScheduleEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    kind: Literal["study", "rest"]
    subject: SubjectValue | None
    start_time: time
    end_time: time
    title: str
    description: str = ""
    effective_from: date
    effective_until: date | None = None
    position: int = Field(ge=0, le=10000)
    active: bool = True

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_text(value, 1, 120, False)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        ) or ""

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        _validate_kind_subject(self.kind, self.subject)
        if (
            self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until must not precede effective_from")
        return self


class ScheduleEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6)
    kind: Literal["study", "rest"] | None = None
    subject: SubjectValue | None = None
    start_time: time | None = None
    end_time: time | None = None
    title: str | None = None
    description: str | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    position: int | None = Field(default=None, ge=0, le=10000)
    active: bool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return clean_text(value, 1, 120, False) if value is not None else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        )


class DayCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate_from_template: bool = False


class ReflectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reflection: str = Field(max_length=4000)

    @field_validator("reflection")
    @classmethod
    def validate_reflection(cls, value: str) -> str:
        return _clean_optional_text(
            value,
            maximum=4000,
            allow_newlines=True,
        ) or ""


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["study", "rest"]
    subject: SubjectValue | None
    start_time: time
    end_time: time
    title: str
    description: str = ""
    status: TaskStatusValue = "planned"
    position: int = Field(ge=0, le=10000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_text(value, 1, 120, False)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        ) or ""

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        _validate_kind_subject(self.kind, self.subject)
        return self


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["study", "rest"] | None = None
    subject: SubjectValue | None = None
    start_time: time | None = None
    end_time: time | None = None
    title: str | None = None
    description: str | None = None
    status: TaskStatusValue | None = None
    position: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return clean_text(value, 1, 120, False) if value is not None else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        )


def _validate_source_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > 500:
        raise ValueError("source_url is too long")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must be an http or https URL")
    return value


class ExamEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    title: str
    date_status: Literal["estimated", "confirmed"]
    start_date: date
    end_date: date | None = None
    description: str = ""
    source_url: str | None = None
    countdown_target: bool = False
    position: int = Field(ge=0, le=10000)
    active: bool = True

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        return clean_text(value, 1, 32, False)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_text(value, 1, 120, False)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        ) or ""

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        return _validate_source_url(value)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if self.countdown_target and not self.active:
            raise ValueError("countdown target must be active")
        return self


class ExamEventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str | None = None
    title: str | None = None
    date_status: Literal["estimated", "confirmed"] | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    source_url: str | None = None
    countdown_target: bool | None = None
    position: int | None = Field(default=None, ge=0, le=10000)
    active: bool | None = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str | None) -> str | None:
        return clean_text(value, 1, 32, False) if value is not None else None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return clean_text(value, 1, 120, False) if value is not None else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _clean_optional_text(
            value,
            maximum=2000,
            allow_newlines=True,
        )

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        return _validate_source_url(value)
