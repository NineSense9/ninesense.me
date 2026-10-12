from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json

from sqlalchemy import select

from ..study_models import StudyPlanCheck

DEFAULT_PLAN = "revised-20261012"
PLAN_FILES = {
    DEFAULT_PLAN: "study_plan_revised_20261012.json",
    "strengthening-202610": "study_plan_202610.json",
}


@lru_cache(maxsize=2)
def plan_content(plan_id=None):
    filename = PLAN_FILES[plan_id or DEFAULT_PLAN]
    return json.loads(
        files("ninesense_guestbook").joinpath("data", filename).read_text(encoding="utf-8")
    )


def task_ids(plan_id=None):
    plans = [plan_content(plan_id)] if plan_id is not None else [plan_content(key) for key in PLAN_FILES]
    return {
        item["id"]
        for plan in plans
        for day in plan["days"]
        for group in day["groups"]
        for item in group["items"]
    }


def checked_ids(db, admin_id, plan_id=DEFAULT_PLAN):
    if admin_id is None:
        return set()
    return set(db.scalars(select(StudyPlanCheck.task_id).where(
        StudyPlanCheck.admin_id == admin_id, StudyPlanCheck.completed.is_(True)
    ))) & task_ids(plan_id)


def private_plan(db, admin_id, plan_id=DEFAULT_PLAN):
    plan = deepcopy(plan_content(plan_id))
    checked = checked_ids(db, admin_id, plan_id)
    plan["available_plans"] = [
        {key: plan_content(value)[key] for key in ("id", "title", "start_date", "end_date")}
        for value in PLAN_FILES
    ]
    for day in plan["days"]:
        for group in day["groups"]:
            for item in group["items"]:
                item["completed"] = item["id"] in checked
    return plan


def progress_summary(db, admin_id, today):
    plan = plan_content()
    checked = checked_ids(db, admin_id)
    groups = {}
    today_items = []
    for day in plan["days"]:
        for group in day["groups"]:
            ids = [item["id"] for item in group["items"] if not item.get("optional", False)]
            if not ids:
                continue
            metric = groups.setdefault(group["key"], {"label": group["label"], "total": 0, "completed": 0})
            metric["total"] += len(ids)
            metric["completed"] += sum(key in checked for key in ids)
            if day["date"] == today:
                today_items.extend(ids)
    return {
        "title": plan["title"], "start_date": plan["start_date"], "end_date": plan["end_date"],
        "total": sum(value["total"] for value in groups.values()),
        "completed": sum(value["completed"] for value in groups.values()), "groups": groups,
        "today": {"date": today, "total": len(today_items), "completed": sum(key in checked for key in today_items)},
    }
