from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..services.audit import record_audit
from ..services.sessions import require_csrf, require_session
from ..services.study_days import get_or_create_day
from ..services.study_stats import admin_history, completion_summary
from ..services.study_timer import as_utc
from ..study_models import (
    ExamEvent,
    FocusSession,
    StudyDay,
    StudyScheduleEntry,
    StudyTask,
)
from .study_schemas import (
    DayCreate,
    ExamEventInput,
    ExamEventUpdate,
    ReflectionUpdate,
    ScheduleEntryInput,
    ScheduleEntryUpdate,
    TaskCreate,
    TaskUpdate,
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
