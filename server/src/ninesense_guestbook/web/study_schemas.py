from typing import Literal

from pydantic import BaseModel


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
