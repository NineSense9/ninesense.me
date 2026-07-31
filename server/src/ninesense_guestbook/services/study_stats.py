from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..study_models import FocusSession, StudyDay, StudyTask
from .study_timer import as_utc


SUBJECTS = ("math", "408", "english", "politics")
SHANGHAI = ZoneInfo("Asia/Shanghai")


def completion_summary(tasks) -> dict[str, int | float | None]:
    closed = [
        task
        for task in tasks
        if task.task_kind == "study"
        and task.status in {"completed", "incomplete"}
    ]
    completed = sum(task.status == "completed" for task in closed)
    return {
        "completed": completed,
        "closed": len(closed),
        "rate": completed / len(closed) if closed else None,
    }


def recent_window(today: date, requested_days: int) -> tuple[date, date]:
    days = max(1, min(requested_days, 30))
    return today - timedelta(days=days - 1), today


def public_recent_days(
    db: Session,
    today: date,
    *,
    requested_days: int,
) -> list[StudyDay]:
    start, end = recent_window(today, requested_days)
    return list(
        db.scalars(
            select(StudyDay)
            .where(
                StudyDay.study_date >= start,
                StudyDay.study_date <= end,
            )
            .order_by(StudyDay.study_date.desc())
        )
    )


def admin_history(
    db: Session,
    start: date,
    end: date,
) -> list[StudyDay]:
    if end < start:
        return []
    return list(
        db.scalars(
            select(StudyDay)
            .where(
                StudyDay.study_date >= start,
                StudyDay.study_date <= end,
            )
            .order_by(StudyDay.study_date.desc())
        )
    )


def _month_bounds(month_text: str) -> tuple[datetime, datetime]:
    start_local = datetime.strptime(
        f"{month_text}-01",
        "%Y-%m-%d",
    ).replace(tzinfo=SHANGHAI)
    if start_local.month == 12:
        next_local = start_local.replace(
            year=start_local.year + 1,
            month=1,
        )
    else:
        next_local = start_local.replace(month=start_local.month + 1)
    return (
        start_local.astimezone(timezone.utc),
        next_local.astimezone(timezone.utc),
    )


def month_summary(db: Session, month_text: str) -> dict[str, object]:
    start_utc, next_utc = _month_bounds(month_text)
    aggregate_rows = db.execute(
        select(
            FocusSession.subject,
            func.sum(FocusSession.effective_seconds),
        )
        .where(
            FocusSession.started_at >= start_utc,
            FocusSession.started_at < next_utc,
        )
        .group_by(FocusSession.subject)
    ).all()

    subjects = {subject: 0 for subject in SUBJECTS}
    subjects.update(
        {
            subject: int(total or 0)
            for subject, total in aggregate_rows
            if subject in subjects
        }
    )

    sessions = list(
        db.scalars(
            select(FocusSession).where(
                FocusSession.started_at >= start_utc,
                FocusSession.started_at < next_utc,
            )
        )
    )
    daily: dict[str, int] = {}
    for session in sessions:
        key = as_utc(session.started_at).astimezone(SHANGHAI).date().isoformat()
        daily[key] = daily.get(key, 0) + session.effective_seconds

    start_local_date = start_utc.astimezone(SHANGHAI).date()
    next_local_date = next_utc.astimezone(SHANGHAI).date()
    tasks = list(
        db.scalars(
            select(StudyTask)
            .join(StudyDay, StudyTask.day_id == StudyDay.id)
            .where(
                StudyDay.study_date >= start_local_date,
                StudyDay.study_date < next_local_date,
            )
        )
    )

    return {
        "month": month_text,
        "total_seconds": sum(subjects.values()),
        "subjects": subjects,
        "daily": [
            {"date": key, "seconds": daily[key]}
            for key in sorted(daily)
        ],
        "completion": completion_summary(tasks),
    }
