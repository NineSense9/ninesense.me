from datetime import date, time

from sqlalchemy import select

from ninesense_guestbook.services.study_days import ensure_today, get_or_create_day
from ninesense_guestbook.study_models import StudyScheduleEntry, StudyTask


def schedule_entry(**overrides):
    values = {
        "weekday": 5,
        "task_kind": "study",
        "subject": "408",
        "start_time": time(8, 30),
        "end_time": time(12),
        "title": "408",
        "description": "数据结构",
        "effective_from": date(2026, 8, 1),
        "position": 10,
        "active": True,
    }
    values.update(overrides)
    return StudyScheduleEntry(**values)


def test_ensure_today_snapshots_only_the_effective_template(db_session):
    db_session.add_all(
        [
            schedule_entry(
                title="旧计划",
                effective_from=date(2026, 7, 1),
                effective_until=date(2026, 7, 31),
            ),
            schedule_entry(title="新计划"),
        ]
    )
    db_session.commit()

    day = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    tasks = list(
        db_session.scalars(
            select(StudyTask).where(StudyTask.day_id == day.id)
        )
    )

    assert [task.title for task in tasks] == ["新计划"]


def test_generated_day_is_immutable_when_template_changes(db_session):
    entry = schedule_entry(title="原计划")
    db_session.add(entry)
    db_session.commit()

    first = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    entry.title = "修改后的模板"
    db_session.commit()
    second = ensure_today(db_session, date(2026, 8, 1))

    assert first.id == second.id
    assert db_session.scalar(
        select(StudyTask.title).where(StudyTask.day_id == first.id)
    ) == "原计划"


def test_missing_template_creates_an_empty_day_without_rollover(db_session):
    day = get_or_create_day(
        db_session,
        date(2026, 8, 2),
        generate_from_template=True,
    )
    db_session.commit()

    assert day.study_date == date(2026, 8, 2)
    assert list(db_session.scalars(select(StudyTask))) == []


def test_template_tasks_use_stable_position_and_time_order(db_session):
    db_session.add_all(
        [
            schedule_entry(
                title="第三项",
                start_time=time(10),
                end_time=time(11),
                position=20,
            ),
            schedule_entry(
                title="第二项",
                start_time=time(9),
                end_time=time(10),
                position=10,
            ),
            schedule_entry(
                title="第一项",
                start_time=time(8),
                end_time=time(9),
                position=10,
            ),
        ]
    )
    db_session.commit()

    day = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    tasks = list(
        db_session.scalars(
            select(StudyTask)
            .where(StudyTask.day_id == day.id)
            .order_by(StudyTask.position, StudyTask.start_time, StudyTask.id)
        )
    )

    assert [task.title for task in tasks] == ["第一项", "第二项", "第三项"]


def test_rest_template_generates_a_subjectless_rest_task(db_session):
    db_session.add(
        schedule_entry(
            task_kind="rest",
            subject=None,
            start_time=time(14),
            end_time=time(17, 30),
            title="下午休息",
            description="",
            position=20,
        )
    )
    db_session.commit()

    day = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    task = db_session.scalar(
        select(StudyTask).where(StudyTask.day_id == day.id)
    )

    assert task.task_kind == "rest"
    assert task.subject is None


def test_incomplete_task_does_not_roll_into_tomorrow(db_session):
    first = get_or_create_day(
        db_session,
        date(2026, 8, 1),
        generate_from_template=False,
    )
    db_session.add(
        StudyTask(
            day_id=first.id,
            task_kind="study",
            subject="408",
            start_time=time(8, 30),
            end_time=time(12),
            title="未完成任务",
            description="",
            status="incomplete",
            position=10,
        )
    )
    db_session.commit()

    second = get_or_create_day(
        db_session,
        date(2026, 8, 2),
        generate_from_template=False,
    )
    db_session.commit()

    assert list(
        db_session.scalars(
            select(StudyTask).where(StudyTask.day_id == second.id)
        )
    ) == []


def test_admin_can_create_a_past_blank_day_without_current_template(db_session):
    day = get_or_create_day(
        db_session,
        date(2025, 1, 5),
        generate_from_template=False,
    )
    db_session.commit()

    assert day.study_date == date(2025, 1, 5)
    assert list(
        db_session.scalars(
            select(StudyTask).where(StudyTask.day_id == day.id)
        )
    ) == []
