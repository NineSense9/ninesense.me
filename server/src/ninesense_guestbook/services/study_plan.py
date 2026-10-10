from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json

from sqlalchemy import select

from ..study_models import StudyPlanCheck


@lru_cache(maxsize=1)
def plan_content():
    return json.loads(
        files("ninesense_guestbook").joinpath("data/study_plan_202610.json").read_text(encoding="utf-8")
    )


def task_ids():
    return {
        item["id"]
        for day in plan_content()["days"]
        for group in day["groups"]
        for item in group["items"]
    }


def checked_ids(db, admin_id):
    if admin_id is None:
        return set()
    return set(db.scalars(select(StudyPlanCheck.task_id).where(
        StudyPlanCheck.admin_id == admin_id, StudyPlanCheck.completed.is_(True)
    ))) & task_ids()


def private_plan(db, admin_id):
    plan = deepcopy(plan_content())
    checked = checked_ids(db, admin_id)
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
            ids = [item["id"] for item in group["items"]]
            metric = groups.setdefault(group["key"], {"label": group["label"], "total": 0, "completed": 0})
            metric["total"] += len(ids)
            metric["completed"] += sum(key in checked for key in ids)
            if day["date"] == today:
                today_items.extend(ids)
    return {
        "title": plan["title"], "start_date": plan["start_date"], "end_date": plan["end_date"],
        "total": len(task_ids()), "completed": len(checked), "groups": groups,
        "today": {"date": today, "total": len(today_items), "completed": sum(key in checked for key in today_items)},
    }
