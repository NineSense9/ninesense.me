from enum import StrEnum


class Subject(StrEnum):
    MATH = "math"
    CS408 = "408"
    ENGLISH = "english"
    POLITICS = "politics"


class TaskKind(StrEnum):
    STUDY = "study"
    REST = "rest"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


FINAL_TASK_STATUSES = frozenset(
    {
        TaskStatus.COMPLETED,
        TaskStatus.INCOMPLETE,
        TaskStatus.CANCELLED,
    }
)


def counts_toward_completion(task_kind: str, status: str) -> bool:
    return task_kind == TaskKind.STUDY and status in {
        TaskStatus.COMPLETED,
        TaskStatus.INCOMPLETE,
    }
