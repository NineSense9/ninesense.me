from datetime import datetime, timezone
import logging
import time

from ninesense_guestbook.models import Message

from admin_test_helpers import create_totp_admin, login_with_totp


PASSWORD = "A-secure-test-password-2026"


def create_admin_and_login(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    return login_with_totp(client, secret)


def test_public_feed_has_a_strict_field_allowlist(client, db_session, app):
    encrypted = app.state.contact_cipher.encrypt("secret@example.com")
    message = Message(
        kind="public",
        status="published",
        nickname="访客",
        contact_type="email",
        contact_nonce=encrypted.nonce,
        contact_ciphertext=encrypted.ciphertext,
        contact_key_version=encrypted.key_version,
        content="已经通过审核的内容",
        idempotency_key="s" * 32,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(message)
    db_session.commit()

    response = client.get("/api/guestbook/messages")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {"id", "nickname", "date", "content", "reply", "reply_date"}
    assert "secret@example.com" not in response.text
    assert "contact" not in response.text
    assert "published" not in response.text


def test_admin_data_is_unavailable_without_session(client):
    response = client.get("/api/admin/messages")

    assert response.status_code == 401


def test_e2e_totp_helper_is_absent_from_normal_application(client):
    assert client.get("/__e2e/current-totp").status_code == 404


def test_forged_csrf_is_rejected(client, db_session, app):
    create_admin_and_login(client, db_session, app)

    response = client.delete(
        "/api/admin/session",
        headers={"X-CSRF-Token": "forged-token"},
    )

    assert response.status_code == 403


def test_logs_do_not_capture_credentials_or_contact(client, db_session, app, caplog):
    create_admin_and_login(client, db_session, app)
    caplog.set_level(logging.DEBUG)

    client.post(
        "/api/guestbook/messages",
        json={
            "kind": "private",
            "nickname": "访客",
            "contact": "secret@example.com",
            "content": "这是一段不应进入日志的私信正文",
            "idempotency_key": "t" * 32,
            "website": "",
            "form_started_at": datetime.now(timezone.utc).timestamp() - 5,
        },
    )

    log_text = caplog.text
    assert PASSWORD not in log_text
    assert "secret@example.com" not in log_text
    assert "不应进入日志" not in log_text


def submission_payload(content, key="u"):
    return {
        "kind": "public",
        "nickname": "访客",
        "contact": "",
        "content": content,
        "idempotency_key": key * 32,
        "website": "",
        "form_started_at": time.time() - 5,
    }


def test_adversarial_plain_text_is_never_interpreted_as_markup_or_sql(client, db_session):
    xss = client.post(
        "/api/guestbook/messages",
        json=submission_payload("<script>alert(1)</script>", "v"),
    )
    nul = client.post(
        "/api/guestbook/messages",
        json=submission_payload("hello\x00world", "w"),
    )
    sql_shaped = client.post(
        "/api/guestbook/messages",
        json=submission_payload("' OR 1=1 --", "x"),
    )

    assert xss.status_code == 422
    assert nul.status_code == 422
    assert sql_shaped.status_code == 202
    assert db_session.query(Message).filter_by(content="' OR 1=1 --").count() == 1


def test_api_rejects_payloads_over_32_kib(client):
    response = client.post(
        "/api/guestbook/messages",
        content=b"x" * (33 * 1024),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "请求内容过大。"}


def test_api_responses_include_security_headers_and_no_cors(client):
    response = client.get(
        "/api/health",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers
