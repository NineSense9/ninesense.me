from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.dialects.sqlite import insert

from ..services.audit import record_audit
from ..services.sessions import require_csrf, require_session
from ..services.study_plan import private_plan, progress_summary, task_ids
from ..study_models import StudyPlanCheck
from .study_public import active_admin_id


admin_router = APIRouter(prefix="/api/admin/study/plan", tags=["study-admin"])
public_router = APIRouter(prefix="/api/study/plan", tags=["study-public"])


class CheckUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: StrictBool


@admin_router.get("")
def get_plan(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        return private_plan(db, current.admin.id)


@admin_router.patch("/items/{task_id}")
def update_check(task_id: str, payload: CheckUpdate, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        if task_id not in task_ids():
            raise HTTPException(status_code=404, detail="计划任务不存在。")
        statement = insert(StudyPlanCheck).values(
            admin_id=current.admin.id, task_id=task_id, completed=payload.completed,
            updated_at=datetime.now(timezone.utc),
        )
        db.execute(statement.on_conflict_do_update(
            index_elements=[StudyPlanCheck.admin_id, StudyPlanCheck.task_id],
            set_={"completed": statement.excluded.completed, "updated_at": statement.excluded.updated_at},
        ))
        record_audit(db, action="study.plan.checked", outcome="success", admin_id=current.admin.id,
                     target_type="study_plan_item", target_id=task_id,
                     details={"changed_fields": ["completed"]})
        db.commit()
    return {"id": task_id, "completed": payload.completed}


@public_router.get("")
def get_progress(request: Request, response: Response):
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    with request.app.state.session_factory() as db:
        return progress_summary(db, active_admin_id(db), today)
