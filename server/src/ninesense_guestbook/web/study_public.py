from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Path, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Admin
from ..services.study_days import ensure_today
from ..services.study_stats import (
    SUBJECTS,
    completion_summary,
    month_summary,
    public_recent_days,
)
from ..services.study_timer import as_utc, reconcile_timer
from ..study_models import (
    ExamEvent,
    FocusSession,
    FocusTimer,
    StudyDay,
    StudyTask,
)
from .study_schemas import (
    PublicExamEvent,
    PublicExamList,
    PublicMonth,
    PublicRecent,
    PublicRecentDay,
    PublicStudyTask,
    PublicToday,
)


router = APIRouter(prefix="/api/study", tags=["study-public"])
SHANGHAI = ZoneInfo("Asia/Shanghai")


def active_admin_id(db: Session) -> int | None:
    return db.scalar(
        select(Admin.id)
        .where(Admin.active.is_(True))
        .order_by(Admin.id)
        .limit(1)
    )


def _cache_public(response: Response) -> None:
    response.headers["Cache-Control"] = (
        "public, max-age=30, stale-while-revalidate=30"
    )


def _task_payload(task: StudyTask) -> PublicStudyTask:
    return PublicStudyTask(
        id=task.id,
        kind=task.task_kind,
        subject=task.subject,
        start_time=task.start_time.isoformat(timespec="minutes"),
        end_time=task.end_time.isoformat(timespec="minutes"),
        title=task.title,
        description=task.description,
        status=task.status,
    )


def public_exam_payload(event: ExamEvent) -> PublicExamEvent:
    return PublicExamEvent(
        id=event.id,
        kind=event.kind,
        title=event.title,
        date_status=event.date_status,
        start_date=event.start_date.isoformat(),
        end_date=event.end_date.isoformat() if event.end_date else None,
        description=event.description,
        source_url=event.source_url,
        countdown_target=event.countdown_target,
    )


def _tasks_for_day(db: Session, day_id: int) -> list[StudyTask]:
    return list(
        db.scalars(
            select(StudyTask)
            .where(StudyTask.day_id == day_id)
            .order_by(
                StudyTask.position,
                StudyTask.start_time,
                StudyTask.id,
            )
        )
    )


def _focus_for_day(db: Session, study_date: date) -> dict[str, int]:
    start_local = datetime.combine(
        study_date,
        time.min,
        tzinfo=SHANGHAI,
    )
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = (start_local + timedelta(days=1)).astimezone(timezone.utc)
    sessions = list(
        db.scalars(
            select(FocusSession).where(
                FocusSession.started_at >= start_utc,
                FocusSession.started_at < end_utc,
            )
        )
    )
    values = {subject: 0 for subject in SUBJECTS}
    for session in sessions:
        if session.subject in values:
            values[session.subject] += session.effective_seconds
    return values


def _day_payload(db: Session, day: StudyDay) -> PublicRecentDay:
    tasks = _tasks_for_day(db, day.id)
    subjects = _focus_for_day(db, day.study_date)
    return PublicRecentDay(
        date=day.study_date.isoformat(),
        reflection=day.reflection,
        completion=completion_summary(tasks),
        total_focus_seconds=sum(subjects.values()),
        subjects=subjects,
        tasks=[_task_payload(task) for task in tasks],
    )


def _active_exams(db: Session) -> list[ExamEvent]:
    return list(
        db.scalars(
            select(ExamEvent)
            .where(ExamEvent.active.is_(True))
            .order_by(ExamEvent.start_date, ExamEvent.position, ExamEvent.id)
        )
    )


@router.get("/today", response_model=PublicToday)
def today(request: Request, response: Response) -> PublicToday:
    now_utc = datetime.now(timezone.utc)
    today_local = now_utc.astimezone(SHANGHAI).date()
    with request.app.state.session_factory() as db:
        day = ensure_today(db, today_local)
        admin_id = active_admin_id(db)
        if admin_id is not None:
            reconcile_timer(db, admin_id=admin_id, now=now_utc)
        timer = (
            db.scalar(
                select(FocusTimer).where(FocusTimer.admin_id == admin_id)
            )
            if admin_id is not None
            else None
        )
        exams = _active_exams(db)
        target = next(
            (event for event in exams if event.countdown_target),
            None,
        )
        next_event = next(
            (event for event in exams if event.start_date >= today_local),
            None,
        )
        day_payload = _day_payload(db, day)
        result = PublicToday(
            date=day_payload.date,
            countdown_days=(
                max(0, (target.start_date - today_local).days)
                if target is not None
                else None
            ),
            countdown_target=target.title if target is not None else None,
            next_exam_event=(
                public_exam_payload(next_event)
                if next_event is not None
                else None
            ),
            active_subject=(
                timer.subject
                if timer is not None and timer.phase == "focus"
                else None
            ),
            updated_at=as_utc(day.updated_at).isoformat().replace("+00:00", "Z"),
            reflection=day_payload.reflection,
            completion=day_payload.completion,
            total_focus_seconds=day_payload.total_focus_seconds,
            subjects=day_payload.subjects,
            tasks=day_payload.tasks,
        )
        db.commit()
    _cache_public(response)
    return result


@router.get("/recent", response_model=PublicRecent)
def recent(
    request: Request,
    response: Response,
    days: int = Query(default=30, ge=1, le=30),
) -> PublicRecent:
    today_local = datetime.now(SHANGHAI).date()
    with request.app.state.session_factory() as db:
        rows = public_recent_days(
            db,
            today_local,
            requested_days=days,
        )
        result = PublicRecent(
            items=[_day_payload(db, row) for row in rows]
        )
    _cache_public(response)
    return result


@router.get("/months/{month}", response_model=PublicMonth)
def month(
    request: Request,
    response: Response,
    month: str = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
) -> PublicMonth:
    with request.app.state.session_factory() as db:
        result = PublicMonth.model_validate(month_summary(db, month))
    _cache_public(response)
    return result


@router.get("/exams", response_model=PublicExamList)
def exams(request: Request, response: Response) -> PublicExamList:
    with request.app.state.session_factory() as db:
        result = PublicExamList(
            items=[public_exam_payload(row) for row in _active_exams(db)]
        )
    _cache_public(response)
    return result
