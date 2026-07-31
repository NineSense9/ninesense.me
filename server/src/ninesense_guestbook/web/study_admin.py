import base64
import binascii
import csv
from datetime import date, datetime, time, timedelta, timezone
import io
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from ..services.audit import record_audit
from ..services.sessions import require_csrf, require_session
from ..services.study_days import get_or_create_day
from ..services.study_stats import admin_history, completion_summary
from ..services.study_timer import (
    as_utc,
    discard_timer,
    finish_timer,
    pause_timer,
    reconcile_timer,
    resume_timer,
    start_break_timer,
    start_timer,
)
from ..study_models import (
    ExamEvent,
    FocusSession,
    FocusTimer,
    StudyDay,
    StudyScheduleEntry,
    StudyTask,
)
from .study_schemas import (
    DayCreate,
    ExamEventInput,
    ExamEventUpdate,
    FocusRecordInput,
    FocusRecordUpdate,
    ReflectionUpdate,
    ScheduleEntryInput,
    ScheduleEntryUpdate,
    TaskCreate,
    TaskUpdate,
    TimerBreak,
    TimerFinish,
    TimerStart,
)


router = APIRouter(prefix="/api/admin/study", tags=["study-admin"])
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _validation_error(error: ValidationError) -> HTTPException:
    messages = [item["msg"] for item in error.errors()]
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="；".join(messages),
    )


def _schedule_payload(row: StudyScheduleEntry) -> dict[str, object]:
    return {
        "id": row.id,
        "weekday": row.weekday,
        "kind": row.task_kind,
        "subject": row.subject,
        "start_time": row.start_time.isoformat(timespec="minutes"),
        "end_time": row.end_time.isoformat(timespec="minutes"),
        "title": row.title,
        "description": row.description,
        "effective_from": row.effective_from.isoformat(),
        "effective_until": (
            row.effective_until.isoformat() if row.effective_until else None
        ),
        "position": row.position,
        "active": row.active,
        "updated_at": as_utc(row.updated_at).isoformat(),
    }


def _schedule_values(row: StudyScheduleEntry) -> dict[str, object]:
    return {
        "weekday": row.weekday,
        "kind": row.task_kind,
        "subject": row.subject,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "title": row.title,
        "description": row.description,
        "effective_from": row.effective_from,
        "effective_until": row.effective_until,
        "position": row.position,
        "active": row.active,
    }


def _apply_schedule(row: StudyScheduleEntry, values: ScheduleEntryInput) -> None:
    row.weekday = values.weekday
    row.task_kind = values.kind
    row.subject = values.subject
    row.start_time = values.start_time
    row.end_time = values.end_time
    row.title = values.title
    row.description = values.description
    row.effective_from = values.effective_from
    row.effective_until = values.effective_until
    row.position = values.position
    row.active = values.active


def _task_payload(row: StudyTask) -> dict[str, object]:
    return {
        "id": row.id,
        "kind": row.task_kind,
        "subject": row.subject,
        "start_time": row.start_time.isoformat(timespec="minutes"),
        "end_time": row.end_time.isoformat(timespec="minutes"),
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "position": row.position,
        "updated_at": as_utc(row.updated_at).isoformat(),
    }


def _task_values(row: StudyTask) -> dict[str, object]:
    return {
        "kind": row.task_kind,
        "subject": row.subject,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "position": row.position,
    }


def _apply_task(row: StudyTask, values: TaskCreate) -> None:
    row.task_kind = values.kind
    row.subject = values.subject
    row.start_time = values.start_time
    row.end_time = values.end_time
    row.title = values.title
    row.description = values.description
    row.status = values.status
    row.position = values.position


def _focus_payload(row: FocusSession) -> dict[str, object]:
    return {
        "id": row.id,
        "subject": row.subject,
        "planned_seconds": row.planned_seconds,
        "started_at": as_utc(row.started_at).isoformat(),
        "ended_at": as_utc(row.ended_at).isoformat(),
        "effective_seconds": row.effective_seconds,
        "completion_kind": row.completion_kind,
        "source": row.source,
        "correction_reason": row.correction_reason,
    }


def _focus_for_day(db: Session, study_date: date) -> list[FocusSession]:
    start_local = datetime.combine(study_date, time.min, tzinfo=SHANGHAI)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = (start_local + timedelta(days=1)).astimezone(timezone.utc)
    return list(
        db.scalars(
            select(FocusSession)
            .where(
                FocusSession.started_at >= start_utc,
                FocusSession.started_at < end_utc,
            )
            .order_by(FocusSession.started_at, FocusSession.id)
        )
    )


def _day_payload(db: Session, day: StudyDay) -> dict[str, object]:
    tasks = list(
        db.scalars(
            select(StudyTask)
            .where(StudyTask.day_id == day.id)
            .order_by(StudyTask.position, StudyTask.start_time, StudyTask.id)
        )
    )
    focus = _focus_for_day(db, day.study_date)
    return {
        "id": day.id,
        "date": day.study_date.isoformat(),
        "reflection": day.reflection,
        "generated_from": day.generated_from,
        "completion": completion_summary(tasks),
        "total_focus_seconds": sum(row.effective_seconds for row in focus),
        "tasks": [_task_payload(row) for row in tasks],
        "focus": [_focus_payload(row) for row in focus],
        "updated_at": as_utc(day.updated_at).isoformat(),
    }


def _exam_payload(row: ExamEvent) -> dict[str, object]:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "date_status": row.date_status,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "description": row.description,
        "source_url": row.source_url,
        "countdown_target": row.countdown_target,
        "position": row.position,
        "active": row.active,
        "updated_at": as_utc(row.updated_at).isoformat(),
    }


def _exam_values(row: ExamEvent) -> dict[str, object]:
    return {
        "kind": row.kind,
        "title": row.title,
        "date_status": row.date_status,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "description": row.description,
        "source_url": row.source_url,
        "countdown_target": row.countdown_target,
        "position": row.position,
        "active": row.active,
    }


def _apply_exam(row: ExamEvent, values: ExamEventInput) -> None:
    row.kind = values.kind
    row.title = values.title
    row.date_status = values.date_status
    row.start_date = values.start_date
    row.end_date = values.end_date
    row.description = values.description
    row.source_url = values.source_url
    row.countdown_target = values.countdown_target
    row.position = values.position
    row.active = values.active


def _clear_other_countdown_targets(
    db: Session,
    *,
    except_id: int | None = None,
) -> None:
    criteria = [ExamEvent.countdown_target.is_(True)]
    if except_id is not None:
        criteria.append(ExamEvent.id != except_id)
    db.execute(update(ExamEvent).where(*criteria).values(countdown_target=False))
    db.flush()


@router.get("/schedule")
def list_schedule(request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = list(
            db.scalars(
                select(StudyScheduleEntry).order_by(
                    StudyScheduleEntry.weekday,
                    StudyScheduleEntry.position,
                    StudyScheduleEntry.start_time,
                    StudyScheduleEntry.id,
                )
            )
        )
        return {"items": [_schedule_payload(row) for row in rows]}


@router.post("/schedule", status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleEntryInput,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = StudyScheduleEntry()
        _apply_schedule(row, payload)
        db.add(row)
        db.flush()
        record_audit(
            db,
            action="study.schedule.created",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_schedule",
            target_id=str(row.id),
            details={"changed_fields": sorted(payload.model_fields_set)},
        )
        db.commit()
        db.refresh(row)
        return _schedule_payload(row)


@router.patch("/schedule/{entry_id}")
def update_schedule(
    entry_id: int,
    payload: ScheduleEntryUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(StudyScheduleEntry, entry_id)
        if row is None:
            raise _not_found("周计划不存在。")
        merged = _schedule_values(row)
        merged.update(payload.model_dump(exclude_unset=True))
        try:
            validated = ScheduleEntryInput.model_validate(merged)
        except ValidationError as error:
            raise _validation_error(error) from error
        changed_fields = sorted(payload.model_fields_set)
        _apply_schedule(row, validated)
        record_audit(
            db,
            action="study.schedule.updated",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_schedule",
            target_id=str(row.id),
            details={"changed_fields": changed_fields},
        )
        db.commit()
        db.refresh(row)
        return _schedule_payload(row)


@router.delete(
    "/schedule/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_schedule(entry_id: int, request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(StudyScheduleEntry, entry_id)
        if row is None:
            raise _not_found("周计划不存在。")
        record_audit(
            db,
            action="study.schedule.deleted",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_schedule",
            target_id=str(row.id),
        )
        db.delete(row)
        db.commit()


@router.get("/days/{study_date}")
def get_day(study_date: date, request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        day = get_or_create_day(
            db,
            study_date,
            generate_from_template=True,
        )
        db.commit()
        return _day_payload(db, day)


@router.post("/days/{study_date}", status_code=status.HTTP_201_CREATED)
def create_day(
    study_date: date,
    request: Request,
    payload: DayCreate | None = None,
) -> dict[str, object]:
    values = payload or DayCreate()
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        day = get_or_create_day(
            db,
            study_date,
            generate_from_template=values.generate_from_template,
        )
        record_audit(
            db,
            action="study.day.created",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_day",
            target_id=str(day.id),
        )
        db.commit()
        return _day_payload(db, day)


@router.patch("/days/{study_date}/reflection")
def update_reflection(
    study_date: date,
    payload: ReflectionUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        day = get_or_create_day(
            db,
            study_date,
            generate_from_template=False,
        )
        day.reflection = payload.reflection
        record_audit(
            db,
            action="study.reflection.updated",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_day",
            target_id=str(day.id),
            details={"changed_fields": ["reflection"]},
        )
        db.commit()
        db.refresh(day)
        return _day_payload(db, day)


@router.post(
    "/days/{study_date}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    study_date: date,
    payload: TaskCreate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        day = get_or_create_day(
            db,
            study_date,
            generate_from_template=False,
        )
        row = StudyTask(day_id=day.id)
        _apply_task(row, payload)
        db.add(row)
        db.flush()
        record_audit(
            db,
            action="study.task.created",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_task",
            target_id=str(row.id),
            details={"changed_fields": sorted(payload.model_fields_set)},
        )
        db.commit()
        db.refresh(row)
        return _task_payload(row)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    payload: TaskUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(StudyTask, task_id)
        if row is None:
            raise _not_found("学习任务不存在。")
        merged = _task_values(row)
        merged.update(payload.model_dump(exclude_unset=True))
        try:
            validated = TaskCreate.model_validate(merged)
        except ValidationError as error:
            raise _validation_error(error) from error
        changed_fields = sorted(payload.model_fields_set)
        _apply_task(row, validated)
        record_audit(
            db,
            action="study.task.updated",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_task",
            target_id=str(row.id),
            details={"changed_fields": changed_fields},
        )
        db.commit()
        db.refresh(row)
        return _task_payload(row)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(StudyTask, task_id)
        if row is None:
            raise _not_found("学习任务不存在。")
        record_audit(
            db,
            action="study.task.deleted",
            outcome="success",
            admin_id=current.admin.id,
            target_type="study_task",
            target_id=str(row.id),
        )
        db.delete(row)
        db.commit()


@router.get("/history")
def history(
    request: Request,
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
) -> dict[str, object]:
    if to_date < from_date or (to_date - from_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="单次历史查询范围必须在 366 天以内。",
        )
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = admin_history(db, from_date, to_date)
        return {"items": [_day_payload(db, row) for row in rows]}


@router.get("/exams")
def list_exams(request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = list(
            db.scalars(
                select(ExamEvent).order_by(
                    ExamEvent.start_date,
                    ExamEvent.position,
                    ExamEvent.id,
                )
            )
        )
        return {"items": [_exam_payload(row) for row in rows]}


@router.post("/exams", status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamEventInput,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        if payload.countdown_target:
            _clear_other_countdown_targets(db)
        row = ExamEvent()
        _apply_exam(row, payload)
        db.add(row)
        db.flush()
        record_audit(
            db,
            action="study.exam.created",
            outcome="success",
            admin_id=current.admin.id,
            target_type="exam_event",
            target_id=str(row.id),
            details={"changed_fields": sorted(payload.model_fields_set)},
        )
        db.commit()
        db.refresh(row)
        return _exam_payload(row)


@router.patch("/exams/{event_id}")
def update_exam(
    event_id: int,
    payload: ExamEventUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(ExamEvent, event_id)
        if row is None:
            raise _not_found("考研时间节点不存在。")
        merged = _exam_values(row)
        merged.update(payload.model_dump(exclude_unset=True))
        try:
            validated = ExamEventInput.model_validate(merged)
        except ValidationError as error:
            raise _validation_error(error) from error
        if validated.countdown_target:
            _clear_other_countdown_targets(db, except_id=row.id)
        changed_fields = sorted(payload.model_fields_set)
        _apply_exam(row, validated)
        record_audit(
            db,
            action="study.exam.updated",
            outcome="success",
            admin_id=current.admin.id,
            target_type="exam_event",
            target_id=str(row.id),
            details={"changed_fields": changed_fields},
        )
        db.commit()
        db.refresh(row)
        return _exam_payload(row)


@router.delete("/exams/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(event_id: int, request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(ExamEvent, event_id)
        if row is None:
            raise _not_found("考研时间节点不存在。")
        record_audit(
            db,
            action="study.exam.deleted",
            outcome="success",
            admin_id=current.admin.id,
            target_type="exam_event",
            target_id=str(row.id),
        )
        db.delete(row)
        db.commit()


def _timer_payload(row: FocusTimer, now: datetime) -> dict[str, object]:
    reference = as_utc(row.paused_at) if row.paused_at else as_utc(now)
    remaining_seconds = max(
        0,
        int((as_utc(row.planned_end_at) - reference).total_seconds()),
    )
    return {
        "id": row.id,
        "subject": row.subject,
        "phase": row.phase,
        "preset": row.preset_kind,
        "focus_seconds": row.focus_seconds,
        "break_seconds": row.break_seconds,
        "state": row.state,
        "started_at": as_utc(row.started_at).isoformat(),
        "planned_end_at": as_utc(row.planned_end_at).isoformat(),
        "paused_at": as_utc(row.paused_at).isoformat() if row.paused_at else None,
        "remaining_seconds": remaining_seconds,
    }


def _timer_response(
    db: Session,
    admin_id: int,
    now: datetime,
    *,
    completed: FocusSession | None = None,
) -> dict[str, object]:
    timer = db.scalar(
        select(FocusTimer).where(FocusTimer.admin_id == admin_id)
    )
    return {
        "timer": _timer_payload(timer, now) if timer is not None else None,
        "completed_session": (
            _focus_payload(completed) if completed is not None else None
        ),
    }


def _current_timer(db: Session, admin_id: int) -> FocusTimer:
    timer = db.scalar(
        select(FocusTimer).where(FocusTimer.admin_id == admin_id)
    )
    if timer is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前没有活动计时器。",
        )
    return timer


@router.get("/timer")
def get_timer(request: Request) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        reconciled = reconcile_timer(db, current.admin.id, now)
        completed = reconciled if isinstance(reconciled, FocusSession) else None
        db.commit()
        return _timer_response(
            db,
            current.admin.id,
            now,
            completed=completed,
        )


@router.post("/timer/start", status_code=status.HTTP_201_CREATED)
def start_focus_timer(
    payload: TimerStart,
    request: Request,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        reconcile_timer(db, current.admin.id, now)
        timer = start_timer(
            db,
            current.admin.id,
            payload.subject,
            payload.preset,
            payload.focus_seconds,
            payload.break_seconds,
            payload.idempotency_key,
            now,
        )
        record_audit(
            db,
            action="study.timer.started",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer.id),
        )
        db.commit()
        return _timer_response(db, current.admin.id, now)


@router.post("/timer/pause")
def pause_focus_timer(request: Request) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        reconcile_timer(db, current.admin.id, now)
        timer = _current_timer(db, current.admin.id)
        pause_timer(db, timer, now)
        record_audit(
            db,
            action="study.timer.paused",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer.id),
        )
        db.commit()
        return _timer_response(db, current.admin.id, now)


@router.post("/timer/resume")
def resume_focus_timer(request: Request) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        _current_timer(db, current.admin.id)
        reconciled = reconcile_timer(db, current.admin.id, now)
        if not isinstance(reconciled, FocusTimer):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="计时器已经结束。",
            )
        timer = reconciled
        resume_timer(db, timer, now)
        record_audit(
            db,
            action="study.timer.resumed",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer.id),
        )
        db.commit()
        return _timer_response(db, current.admin.id, now)


@router.post("/timer/finish")
def finish_focus_timer(
    payload: TimerFinish,
    request: Request,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        timer = _current_timer(db, current.admin.id)
        timer_id = timer.id
        reconciled = reconcile_timer(db, current.admin.id, now)
        if isinstance(reconciled, FocusSession):
            record_audit(
                db,
                action="study.timer.finished",
                outcome="success",
                admin_id=current.admin.id,
                target_type="focus_timer",
                target_id=str(timer_id),
                details={"changed_fields": ["auto_completed"]},
            )
            db.commit()
            return {"timer": None, "session": _focus_payload(reconciled)}
        if reconciled is None:
            db.commit()
            return {"timer": None, "session": None}
        timer = reconciled
        session = finish_timer(db, timer, save=payload.save, now=now)
        record_audit(
            db,
            action="study.timer.finished",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer_id),
            details={"changed_fields": ["saved" if payload.save else "discarded"]},
        )
        db.commit()
        return {
            "timer": None,
            "session": _focus_payload(session) if session is not None else None,
        }


@router.post("/timer/discard")
def discard_focus_timer(request: Request) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        timer = _current_timer(db, current.admin.id)
        timer_id = timer.id
        reconciled = reconcile_timer(db, current.admin.id, now)
        if isinstance(reconciled, FocusSession):
            db.commit()
            return {
                "timer": None,
                "completed_session": _focus_payload(reconciled),
            }
        if isinstance(reconciled, FocusTimer):
            discard_timer(db, reconciled)
        record_audit(
            db,
            action="study.timer.discarded",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer_id),
        )
        db.commit()
        return {"timer": None}


@router.post("/timer/break", status_code=status.HTTP_201_CREATED)
def start_break(
    payload: TimerBreak,
    request: Request,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        reconcile_timer(db, current.admin.id, now)
        timer = start_break_timer(
            db,
            current.admin.id,
            payload.break_seconds,
            payload.idempotency_key,
            now,
        )
        record_audit(
            db,
            action="study.timer.break_started",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_timer",
            target_id=str(timer.id),
        )
        db.commit()
        return _timer_response(db, current.admin.id, now)


def _encode_focus_cursor(row: FocusSession) -> str:
    raw = f"{as_utc(row.started_at).isoformat()}|{row.id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_focus_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(
            (cursor + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
        timestamp_text, row_id_text = raw.rsplit("|", 1)
        timestamp = datetime.fromisoformat(timestamp_text)
        row_id = int(row_id_text)
        if timestamp.tzinfo is None or row_id < 1:
            raise ValueError
        return as_utc(timestamp), row_id
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的分页位置。",
        ) from error


def _focus_range(
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    today = datetime.now(SHANGHAI).date()
    start = from_date or today.replace(day=1)
    end = to_date or today
    if end < start or (end - start).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="单次专注查询范围必须在 366 天以内。",
        )
    return start, end


@router.get("/focus")
def list_focus(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    subject: str | None = Query(default=None, pattern=r"^(math|408|english|politics)$"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    start, end = _focus_range(from_date, to_date)
    start_utc = datetime.combine(start, time.min, tzinfo=SHANGHAI).astimezone(
        timezone.utc
    )
    end_utc = (
        datetime.combine(end, time.min, tzinfo=SHANGHAI) + timedelta(days=1)
    ).astimezone(timezone.utc)
    criteria = [
        FocusSession.started_at >= start_utc,
        FocusSession.started_at < end_utc,
    ]
    if subject is not None:
        criteria.append(FocusSession.subject == subject)
    if cursor is not None:
        cursor_time, cursor_id = _decode_focus_cursor(cursor)
        criteria.append(
            or_(
                FocusSession.started_at < cursor_time,
                and_(
                    FocusSession.started_at == cursor_time,
                    FocusSession.id < cursor_id,
                ),
            )
        )
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = list(
            db.scalars(
                select(FocusSession)
                .where(*criteria)
                .order_by(FocusSession.started_at.desc(), FocusSession.id.desc())
                .limit(limit + 1)
            )
        )
        visible = rows[:limit]
        next_cursor = (
            _encode_focus_cursor(visible[-1])
            if len(rows) > limit and visible
            else None
        )
        return {
            "items": [_focus_payload(row) for row in visible],
            "next_cursor": next_cursor,
        }


@router.post("/focus", status_code=status.HTTP_201_CREATED)
def create_focus(
    payload: FocusRecordInput,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        planned_seconds = int(
            (as_utc(payload.ended_at) - as_utc(payload.started_at)).total_seconds()
        )
        row = FocusSession(
            admin_id=current.admin.id,
            subject=payload.subject,
            planned_seconds=planned_seconds,
            started_at=as_utc(payload.started_at),
            ended_at=as_utc(payload.ended_at),
            effective_seconds=payload.effective_seconds,
            completion_kind="manual",
            source="manual",
            correction_reason=payload.reason,
        )
        db.add(row)
        db.flush()
        record_audit(
            db,
            action="study.focus.created",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_session",
            target_id=str(row.id),
            details={"changed_fields": ["manual_record"]},
        )
        db.commit()
        db.refresh(row)
        return _focus_payload(row)


@router.patch("/focus/{session_id}")
def update_focus(
    session_id: int,
    payload: FocusRecordUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(FocusSession, session_id)
        if row is None:
            raise _not_found("专注记录不存在。")
        merged = {
            "subject": row.subject,
            "started_at": as_utc(row.started_at),
            "ended_at": as_utc(row.ended_at),
            "effective_seconds": row.effective_seconds,
            "reason": payload.reason,
        }
        merged.update(
            {
                key: value
                for key, value in payload.model_dump(exclude_unset=True).items()
                if key != "reason"
            }
        )
        try:
            validated = FocusRecordInput.model_validate(merged)
        except ValidationError as error:
            raise _validation_error(error) from error
        changed_fields = sorted(payload.model_fields_set)
        row.subject = validated.subject
        row.started_at = as_utc(validated.started_at)
        row.ended_at = as_utc(validated.ended_at)
        row.effective_seconds = validated.effective_seconds
        if {"started_at", "ended_at"} & payload.model_fields_set:
            row.planned_seconds = int(
                (row.ended_at - row.started_at).total_seconds()
            )
        row.completion_kind = "corrected"
        row.correction_reason = validated.reason
        record_audit(
            db,
            action="study.focus.updated",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_session",
            target_id=str(row.id),
            details={"changed_fields": changed_fields},
        )
        db.commit()
        db.refresh(row)
        return _focus_payload(row)


@router.delete("/focus/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_focus(session_id: int, request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(FocusSession, session_id)
        if row is None:
            raise _not_found("专注记录不存在。")
        record_audit(
            db,
            action="study.focus.deleted",
            outcome="success",
            admin_id=current.admin.id,
            target_type="focus_session",
            target_id=str(row.id),
        )
        db.delete(row)
        db.commit()


@router.get("/export.json")
def export_study_json(request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        schedule = list(
            db.scalars(
                select(StudyScheduleEntry).order_by(StudyScheduleEntry.id)
            )
        )
        days = list(db.scalars(select(StudyDay).order_by(StudyDay.study_date)))
        tasks = list(db.scalars(select(StudyTask).order_by(StudyTask.id)))
        focus = list(db.scalars(select(FocusSession).order_by(FocusSession.id)))
        exams = list(db.scalars(select(ExamEvent).order_by(ExamEvent.id)))
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schedule": [_schedule_payload(row) for row in schedule],
            "days": [
                {
                    "id": row.id,
                    "date": row.study_date.isoformat(),
                    "reflection": row.reflection,
                    "generated_from": row.generated_from,
                    "created_at": as_utc(row.created_at).isoformat(),
                    "updated_at": as_utc(row.updated_at).isoformat(),
                }
                for row in days
            ],
            "tasks": [
                {**_task_payload(row), "day_id": row.day_id}
                for row in tasks
            ],
            "focus_sessions": [_focus_payload(row) for row in focus],
            "exam_events": [_exam_payload(row) for row in exams],
        }


def _csv_response(
    filename: str,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> StreamingResponse:
    output = io.StringIO(newline="")
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/focus.csv")
def export_focus_csv(request: Request) -> StreamingResponse:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = list(
            db.scalars(
                select(FocusSession).order_by(
                    FocusSession.started_at,
                    FocusSession.id,
                )
            )
        )
        payload = [_focus_payload(row) for row in rows]
    return _csv_response(
        "ninesense-focus.csv",
        [
            "id",
            "subject",
            "planned_seconds",
            "started_at",
            "ended_at",
            "effective_seconds",
            "completion_kind",
            "source",
            "correction_reason",
        ],
        payload,
    )


@router.get("/tasks.csv")
def export_tasks_csv(request: Request) -> StreamingResponse:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        rows = db.execute(
            select(StudyTask, StudyDay.study_date)
            .join(StudyDay, StudyTask.day_id == StudyDay.id)
            .order_by(StudyDay.study_date, StudyTask.position, StudyTask.id)
        ).all()
        payload = [
            {
                **_task_payload(task),
                "date": study_date.isoformat(),
            }
            for task, study_date in rows
        ]
    return _csv_response(
        "ninesense-study-tasks.csv",
        [
            "id",
            "date",
            "kind",
            "subject",
            "start_time",
            "end_time",
            "title",
            "description",
            "status",
            "position",
            "updated_at",
        ],
        payload,
    )
