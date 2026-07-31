from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..study_models import FocusSession, FocusTimer


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _active_timer(db: Session, admin_id: int) -> FocusTimer | None:
    return db.scalar(
        select(FocusTimer).where(FocusTimer.admin_id == admin_id)
    )


def _require_available_timer(
    db: Session,
    admin_id: int,
    idempotency_key: str,
) -> FocusTimer | None:
    existing = _active_timer(db, admin_id)
    if existing is None:
        return None
    if existing.idempotency_key == idempotency_key:
        return existing
    raise HTTPException(status_code=409, detail="已有正在运行的计时器")


def start_timer(
    db: Session,
    admin_id: int,
    subject: str,
    preset_kind: str,
    focus_seconds: int,
    break_seconds: int,
    idempotency_key: str,
    now: datetime,
) -> FocusTimer:
    existing = _require_available_timer(db, admin_id, idempotency_key)
    if existing is not None:
        return existing

    now_utc = as_utc(now)
    timer = FocusTimer(
        admin_id=admin_id,
        subject=subject,
        phase="focus",
        preset_kind=preset_kind,
        focus_seconds=focus_seconds,
        break_seconds=break_seconds,
        state="running",
        started_at=now_utc,
        planned_end_at=now_utc + timedelta(seconds=focus_seconds),
        idempotency_key=idempotency_key,
    )
    db.add(timer)
    db.flush()
    return timer


def start_break_timer(
    db: Session,
    admin_id: int,
    break_seconds: int,
    idempotency_key: str,
    now: datetime,
) -> FocusTimer:
    existing = _require_available_timer(db, admin_id, idempotency_key)
    if existing is not None:
        return existing

    now_utc = as_utc(now)
    timer = FocusTimer(
        admin_id=admin_id,
        subject=None,
        phase="break",
        preset_kind="break",
        focus_seconds=0,
        break_seconds=break_seconds,
        state="running",
        started_at=now_utc,
        planned_end_at=now_utc + timedelta(seconds=break_seconds),
        idempotency_key=idempotency_key,
    )
    db.add(timer)
    db.flush()
    return timer


def pause_timer(
    db: Session,
    timer: FocusTimer,
    now: datetime,
) -> FocusTimer:
    if timer.state != "running":
        raise HTTPException(status_code=409, detail="计时器当前不能暂停")
    timer.state = "paused"
    timer.paused_at = as_utc(now)
    db.flush()
    return timer


def resume_timer(
    db: Session,
    timer: FocusTimer,
    now: datetime,
) -> FocusTimer:
    if timer.state != "paused" or timer.paused_at is None:
        raise HTTPException(status_code=409, detail="计时器当前不能恢复")

    now_utc = as_utc(now)
    paused_seconds = max(
        0,
        int((now_utc - as_utc(timer.paused_at)).total_seconds()),
    )
    timer.accumulated_pause_seconds += paused_seconds
    timer.planned_end_at = as_utc(timer.planned_end_at) + timedelta(
        seconds=paused_seconds
    )
    timer.paused_at = None
    timer.state = "running"
    db.flush()
    return timer


def effective_seconds(timer: FocusTimer, now: datetime) -> int:
    end = min(as_utc(now), as_utc(timer.planned_end_at))
    elapsed = int((end - as_utc(timer.started_at)).total_seconds())
    if timer.state == "paused" and timer.paused_at is not None:
        elapsed -= max(
            0,
            int((end - as_utc(timer.paused_at)).total_seconds()),
        )
    elapsed -= timer.accumulated_pause_seconds
    return max(0, min(timer.focus_seconds, elapsed))


def _new_focus_session(
    timer: FocusTimer,
    now: datetime,
    *,
    completion_kind: str,
) -> FocusSession:
    ended_at = min(as_utc(now), as_utc(timer.planned_end_at))
    return FocusSession(
        admin_id=timer.admin_id,
        source_timer_id=timer.id,
        subject=timer.subject,
        planned_seconds=timer.focus_seconds,
        started_at=as_utc(timer.started_at),
        ended_at=ended_at,
        effective_seconds=effective_seconds(timer, now),
        completion_kind=completion_kind,
        source="timer",
    )


def finish_timer(
    db: Session,
    timer: FocusTimer,
    *,
    save: bool,
    now: datetime,
) -> FocusSession | None:
    if not save or timer.phase == "break":
        return discard_timer(db, timer)

    seconds = effective_seconds(timer, now)
    completion_kind = (
        "completed" if seconds >= timer.focus_seconds else "early_saved"
    )
    session = _new_focus_session(
        timer,
        now,
        completion_kind=completion_kind,
    )
    db.add(session)
    db.flush()
    db.delete(timer)
    db.flush()
    return session


def discard_timer(db: Session, timer: FocusTimer) -> None:
    db.delete(timer)
    db.flush()
    return None


def reconcile_timer(
    db: Session,
    admin_id: int,
    now: datetime,
) -> FocusTimer | FocusSession | None:
    timer = db.scalar(
        select(FocusTimer)
        .where(FocusTimer.admin_id == admin_id)
        .with_for_update()
    )
    if timer is None or timer.state == "paused":
        return timer
    if as_utc(now) < as_utc(timer.planned_end_at):
        return timer
    if timer.phase == "break":
        db.delete(timer)
        db.flush()
        return None

    existing = db.scalar(
        select(FocusSession).where(FocusSession.source_timer_id == timer.id)
    )
    if existing is None:
        session = _new_focus_session(
            timer,
            timer.planned_end_at,
            completion_kind="completed",
        )
        try:
            with db.begin_nested():
                db.add(session)
                db.flush()
        except IntegrityError:
            existing = db.scalar(
                select(FocusSession).where(
                    FocusSession.source_timer_id == timer.id
                )
            )
        else:
            existing = session

    db.delete(timer)
    db.flush()
    return existing
