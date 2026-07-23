from argon2 import PasswordHasher
from sqlalchemy import select

from ninesense_guestbook.models import Admin, Message, Outbox


PASSWORD = "A-secure-test-password-2026"


def authenticate(client, db_session):
    db_session.add(
        Admin(
            username="ninesense",
            password_hash=PasswordHasher().hash(PASSWORD),
            active=True,
        )
    )
    db_session.commit()
    response = client.post(
        "/api/admin/session",
        json={"username": "ninesense", "password": PASSWORD},
    )
    return response.json()["csrf_token"]


def add_message(db_session, app, key: str, *, kind="public", contact="hello@example.com"):
    encrypted = app.state.contact_cipher.encrypt(contact)
    message = Message(
        kind=kind,
        status="pending",
        nickname=f"访客{key}",
        contact_type="email",
        contact_nonce=encrypted.nonce,
        contact_ciphertext=encrypted.ciphertext,
        contact_key_version=encrypted.key_version,
        content=f"这是第 {key} 条留言",
        idempotency_key=key * 32,
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(Outbox(message_id=message.id))
    db_session.commit()
    return message


def csrf_header(token):
    return {"X-CSRF-Token": token}


def test_pending_list_hides_contact_and_detail_reveals_it(client, db_session, app):
    authenticate(client, db_session)
    public = add_message(db_session, app, "a")
    private = add_message(db_session, app, "b", kind="private", contact="13800138000")

    response = client.get("/api/admin/messages?status=pending")

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {public.id, private.id}
    assert all(item["has_contact"] for item in response.json()["items"])
    assert "hello@example.com" not in response.text
    assert "13800138000" not in response.text
    detail = client.get(f"/api/admin/messages/{private.id}")
    assert detail.status_code == 200
    assert detail.json()["contact"] == "13800138000"


def test_publish_with_reply_is_atomic_and_appears_in_public_feed(client, db_session, app):
    csrf = authenticate(client, db_session)
    message = add_message(db_session, app, "c")

    response = client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "published", "reply": "谢谢你来这里看看。"},
        headers=csrf_header(csrf),
    )

    assert response.status_code == 200
    db_session.expire_all()
    stored = db_session.get(Message, message.id)
    assert stored.status == "published"
    assert stored.published_at is not None
    assert stored.reviewed_at is not None
    assert stored.reply == "谢谢你来这里看看。"
    assert stored.reply_at is not None
    feed = client.get("/api/guestbook/messages").json()["items"]
    assert feed[0]["id"] == message.id
    assert feed[0]["reply"] == "谢谢你来这里看看。"


def test_withdraw_removes_published_message_from_feed(client, db_session, app):
    csrf = authenticate(client, db_session)
    message = add_message(db_session, app, "d")
    client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "published"},
        headers=csrf_header(csrf),
    )

    response = client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "pending"},
        headers=csrf_header(csrf),
    )

    assert response.status_code == 200
    assert client.get("/api/guestbook/messages").json()["items"] == []


def test_private_message_can_be_handled_then_archived_but_never_published(
    client, db_session, app
):
    csrf = authenticate(client, db_session)
    message = add_message(db_session, app, "e", kind="private")

    publish = client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "published"},
        headers=csrf_header(csrf),
    )
    reply = client.put(
        f"/api/admin/messages/{message.id}/reply",
        json={"reply": "不应公开"},
        headers=csrf_header(csrf),
    )
    handled = client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "handled"},
        headers=csrf_header(csrf),
    )
    archived = client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "archived"},
        headers=csrf_header(csrf),
    )

    assert publish.status_code == 409
    assert reply.status_code == 409
    assert handled.status_code == archived.status_code == 200
    db_session.expire_all()
    assert db_session.get(Message, message.id).status == "archived"


def test_reply_can_be_updated_and_removed(client, db_session, app):
    csrf = authenticate(client, db_session)
    message = add_message(db_session, app, "f")
    client.patch(
        f"/api/admin/messages/{message.id}/status",
        json={"status": "published"},
        headers=csrf_header(csrf),
    )

    updated = client.put(
        f"/api/admin/messages/{message.id}/reply",
        json={"reply": "后来补上的回复。"},
        headers=csrf_header(csrf),
    )
    removed = client.delete(
        f"/api/admin/messages/{message.id}/reply",
        headers=csrf_header(csrf),
    )

    assert updated.status_code == removed.status_code == 200
    db_session.expire_all()
    stored = db_session.get(Message, message.id)
    assert stored.reply is None
    assert stored.reply_at is None


def test_delete_cascades_outbox_and_all_writes_require_csrf(client, db_session, app):
    csrf = authenticate(client, db_session)
    message = add_message(db_session, app, "1")
    message_id = message.id

    without_csrf = client.delete(f"/api/admin/messages/{message_id}")
    assert without_csrf.status_code == 403

    deleted = client.delete(
        f"/api/admin/messages/{message_id}",
        headers=csrf_header(csrf),
    )
    assert deleted.status_code == 204
    db_session.expire_all()
    assert db_session.get(Message, message_id) is None
    assert db_session.scalars(select(Outbox)).all() == []
