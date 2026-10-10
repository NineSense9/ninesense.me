import pytest

from admin_test_helpers import create_totp_admin, login_with_totp


@pytest.fixture
def owner(client, app, db_session):
    _, secret = create_totp_admin(db_session, app)
    login = login_with_totp(client, secret)
    client.headers.update({"X-CSRF-Token": login.json()["csrf_token"]})
    return client


def test_plan_requires_login_and_csrf(client, app, db_session):
    assert client.get("/api/admin/study/plan").status_code == 401
    _, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)
    assert client.patch(
        "/api/admin/study/plan/items/2026-10-09-408-1", json={"completed": True}
    ).status_code == 403


def test_plan_retains_23_days_and_expanded_groups(owner):
    plan = owner.get("/api/admin/study/plan").json()
    assert len(plan["days"]) == 23
    assert plan["days"][0]["date"] == "2026-10-09"
    assert plan["days"][-1]["date"] == "2026-10-31"
    ids = []
    for day in plan["days"]:
        assert [group["key"] for group in day["groups"]] == ["408", "math", "goals"]
        for group in day["groups"]:
            assert group["source"]
            assert len(group["items"]) >= 2
            ids.extend(item["id"] for item in group["items"])
    assert len(ids) == len(set(ids))


def test_check_persists_is_idempotent_and_can_be_undone(owner):
    task = "2026-10-10-math-1"
    url = f"/api/admin/study/plan/items/{task}"
    for _ in range(2):
        assert owner.patch(url, json={"completed": True}).status_code == 200
    plan = owner.get("/api/admin/study/plan").json()
    items = [item for day in plan["days"] for group in day["groups"] for item in group["items"]]
    assert sum(item["completed"] for item in items) == 1
    assert owner.get("/api/study/plan").json()["completed"] == 1
    assert owner.patch(url, json={"completed": False}).status_code == 200
    assert owner.get("/api/study/plan").json()["completed"] == 0


def test_public_summary_has_no_task_contents_and_unknown_ids_rejected(owner):
    response = owner.get("/api/study/plan")
    assert response.status_code == 200
    assert "source" not in response.text
    assert "description" not in response.text
    assert "麦克劳林" not in response.text
    assert owner.patch(
        "/api/admin/study/plan/items/not-in-plan", json={"completed": True}
    ).status_code == 404
    assert owner.patch(
        "/api/admin/study/plan/items/2026-10-10-math-1", json={"completed": "false"}
    ).status_code == 422
