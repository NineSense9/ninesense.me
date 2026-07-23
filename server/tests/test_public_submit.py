import time

from sqlalchemy import select

from ninesense_guestbook.models import Message, Outbox


def payload(key: str = "a", **overrides):
    data = {
        "kind": "public",
        "nickname": "访客",
        "contact": "13800138000",
        "content": "你好，网站做得不错。",
        "idempotency_key": key * 32,
        "website": "",
        "form_started_at": time.time() - 4,
    }
    data.update(overrides)
    return data


def test_public_submission_is_pending_and_hides_contact(client, db_session):
    response = client.post("/api/guestbook/messages", json=payload())

    assert response.status_code == 202
    assert response.json() == {"status": "received"}
    assert "13800138000" not in response.text
    stored = db_session.scalars(select(Message)).one()
    assert stored.kind == "public"
    assert stored.status == "pending"
    assert stored.contact_type == "phone"
    assert stored.contact_ciphertext is not None
    assert stored.contact_ciphertext != b"13800138000"
    assert db_session.scalars(select(Outbox)).one().message_id == stored.id


def test_private_submission_is_stored_but_not_distinguished_in_response(client, db_session):
    response = client.post(
        "/api/guestbook/messages",
        json=payload("b", kind="private", contact="hello@example.com"),
    )

    assert response.status_code == 202
    assert response.json() == {"status": "received"}
    stored = db_session.scalars(select(Message)).one()
    assert stored.kind == "private"
    assert stored.contact_type == "email"


def test_duplicate_idempotency_key_returns_same_generic_success(client, db_session):
    request = payload("c", contact="")

    assert client.post("/api/guestbook/messages", json=request).status_code == 202
    assert client.post("/api/guestbook/messages", json=request).status_code == 202
    assert len(db_session.scalars(select(Message)).all()) == 1
    assert len(db_session.scalars(select(Outbox)).all()) == 1


def test_honeypot_and_implausibly_fast_posts_succeed_without_storing(client, db_session):
    honeypot = client.post(
        "/api/guestbook/messages",
        json=payload("d", website="https://spam.example"),
    )
    too_fast = client.post(
        "/api/guestbook/messages",
        json=payload("e", form_started_at=time.time()),
    )
    future = client.post(
        "/api/guestbook/messages",
        json=payload("f", form_started_at=time.time() + 60),
    )

    assert [honeypot.status_code, too_fast.status_code, future.status_code] == [202, 202, 202]
    assert db_session.scalars(select(Message)).all() == []


def test_fourth_new_submission_in_ten_minutes_is_limited(client):
    for key in ("g", "h", "i"):
        assert client.post("/api/guestbook/messages", json=payload(key)).status_code == 202

    response = client.post("/api/guestbook/messages", json=payload("j"))

    assert response.status_code == 429
    assert response.json() == {"detail": "提交得有点频繁，请稍后再试。"}


def test_invalid_content_is_rejected_before_storage(client, db_session):
    response = client.post(
        "/api/guestbook/messages",
        json=payload("k", content="<img src=x onerror=alert(1)>"),
    )

    assert response.status_code == 422
    assert db_session.scalars(select(Message)).all() == []

