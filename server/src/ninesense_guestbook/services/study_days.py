from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..study_models import StudyDay, StudyScheduleEntry, StudyTask


def get_or_create_day(
    db: Session,
    study_date: date,
    *,
    generate_from_template: bool,
) -> StudyDay:
    existing = db.scalar(
        select(StudyDay).where(StudyDay.study_date == study_date)
    )
    if existing is not None:
        return existing

    day = StudyDay(study_date=study_date, reflection="")
    db.add(day)
    db.flush()

    if not generate_from_template:
        return day

    entries = list(
        db.scalars(
            select(StudyScheduleEntry)
            .where(
                StudyScheduleEntry.active.is_(True),
                StudyScheduleEntry.weekday == study_date.weekday(),
                StudyScheduleEntry.effective_from <= study_date,
                or_(
                    StudyScheduleEntry.effective_until.is_(None),
                    StudyScheduleEntry.effective_until >= study_date,
                ),
            )
            .order_by(
                StudyScheduleEntry.position,
                StudyScheduleEntry.start_time,
                StudyScheduleEntry.id,
            )
        )
    )
    if entries:
        day.generated_from = f"weekly:{study_date.isoformat()}"

    for entry in entries:
        db.add(
            StudyTask(
                day_id=day.id,
                task_kind=entry.task_kind,
                subject=entry.subject,
                start_time=entry.start_time,
                end_time=entry.end_time,
                title=entry.title,
                description=entry.description,
                status="planned",
                position=entry.position,
            )
        )

    return day


def ensure_today(db: Session, today: date) -> StudyDay:
    return get_or_create_day(
        db,
        today,
        generate_from_template=True,
    )
