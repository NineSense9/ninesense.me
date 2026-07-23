from datetime import datetime, timedelta, timezone

from ninesense_guestbook.models import Message


def add_message(db_session, identifier: str, *, kind="public", status="published", when=None):
    when = when or datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)
    message = Message(
        id=identifier,
        kind=kind,
        status=status,
        nickname=f"访客{identifier[0]}",
        contact_type="email",
        contact_nonce=b"nonce",
        contact_ciphertext=b"secret-contact",
        contact_key_version=1,
        content=f"留言 {identifier[0]}",
        idempotency_key=identifier,
        published_at=when,
        reply="谢谢你的留言" if identifier.startswith("f") else None,
        reply_at=when + timedelta(hours=1) if identifier.startswith("f") else None,
    )
    db_session.add(message)
    db_session.commit()
    return message


def test_feed_returns_only_published_public_messages_with_allowlisted_fields(
    client, db_session
):
    older = add_message(db_session, "a" * 32)
    newer = add_message(
        db_session,
        "f" * 32,
        when=datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc),
    )
    pending = add_message(db_session, "b" * 32, status="pending")
    private = add_message(db_session, "c" * 32, kind="private")
    archived = add_message(db_session, "d" * 32, status="archived")

    response = client.get("/api/guestbook/messages?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [newer.id, older.id]
    assert set(body["items"][0]) == {
        "id",
        "nickname",
        "date",
        "content",
        "reply",
        "reply_date",
    }
    assert body["items"][0]["date"] == "2026-07-24"
    assert body["items"][0]["reply"] == "谢谢你的留言"
    assert "secret-contact" not in response.text
    assert pending.id not in response.text
    assert private.id not in response.text
    assert archived.id not in response.text


def test_cursor_pagination_is_stable_when_publish_times_match(client, db_session):
    same_time = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)
    identifiers = [character * 32 for character in ("a", "b", "c", "d", "e")]
    for identifier in identifiers:
        add_message(db_session, identifier, when=same_time)

    first = client.get("/api/guestbook/messages?limit=2").json()
    second = client.get(
        "/api/guestbook/messages",
        params={"limit": 2, "cursor": first["next_cursor"]},
    ).json()
    third = client.get(
        "/api/guestbook/messages",
        params={"limit": 2, "cursor": second["next_cursor"]},
    ).json()

    seen = [item["id"] for page in (first, second, third) for item in page["items"]]
    assert seen == sorted(identifiers, reverse=True)
    assert len(seen) == len(set(seen))
    assert third["next_cursor"] is None


def test_invalid_cursor_is_rejected(client):
    response = client.get("/api/guestbook/messages?cursor=not-a-cursor")

    assert response.status_code == 400
    assert response.json() == {"detail": "无效的分页位置。"}

