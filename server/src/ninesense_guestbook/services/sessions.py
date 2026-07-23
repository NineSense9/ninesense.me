from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from threading import Lock

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from ..models import Admin, AdminSession


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def token_hash(token: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True)
class SessionTokens:
    session_token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class CurrentSession:
    row: AdminSession
    admin: Admin


def create_session(
    db: Session,
    admin_id: int,
    pepper: str,
    session_hours: int,
    now: datetime | None = None,
) -> SessionTokens:
    now = as_utc(now or datetime.now(timezone.utc))
    raw_session = secrets.token_urlsafe(32)
    raw_csrf = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=session_hours)
    db.add(
        AdminSession(
            id_hash=token_hash(raw_session, pepper),
            admin_id=admin_id,
            csrf_hash=token_hash(raw_csrf, pepper),
            expires_at=expires_at,
        )
    )
    return SessionTokens(raw_session, raw_csrf, expires_at)


def require_session(
    request: Request,
    db: Session,
    now: datetime | None = None,
) -> CurrentSession:
    settings = request.app.state.settings
    raw_session = request.cookies.get(settings.cookie_name)
    if not raw_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录。",
        )

    row = db.get(AdminSession, token_hash(raw_session, settings.session_pepper))
    current_time = as_utc(now or datetime.now(timezone.utc))
    if row is None or as_utc(row.expires_at) <= current_time:
        if row is not None:
            db.delete(row)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录。",
        )

    admin = db.get(Admin, row.admin_id)
    if admin is None or not admin.active:
        db.delete(row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录。",
        )
    return CurrentSession(row=row, admin=admin)


def require_csrf(request: Request, current: CurrentSession) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = token_hash(supplied, request.app.state.settings.session_pepper)
    if not supplied or not hmac.compare_digest(expected, current.row.csrf_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="安全校验失败，请刷新页面后重试。",
        )


def rotate_csrf(current: CurrentSession, pepper: str) -> str:
    raw_csrf = secrets.token_urlsafe(32)
    current.row.csrf_hash = token_hash(raw_csrf, pepper)
    return raw_csrf


def revoke_session(db: Session, current: CurrentSession) -> None:
    db.delete(current.row)


class LoginAttemptLimiter:
    def __init__(
        self,
        secret: str,
        limit: int = 5,
        window: timedelta = timedelta(minutes=15),
        max_entries: int = 2048,
    ):
        self._secret = secret.encode("utf-8")
        self._limit = limit
        self._window = window
        self._max_entries = max_entries
        self._failures: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    def _token(self, ip: str, username: str, now: datetime) -> str:
        normalized = username.strip().casefold()
        day = as_utc(now).date().isoformat()
        payload = f"{day}:{ip}:{normalized}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def is_locked(self, ip: str, username: str, now: datetime) -> bool:
        token = self._token(ip, username, now)
        with self._lock:
            self._prune(now)
            return len(self._failures.get(token, ())) >= self._limit

    def record_failure(self, ip: str, username: str, now: datetime) -> None:
        token = self._token(ip, username, now)
        with self._lock:
            self._prune(now)
            self._failures.setdefault(token, deque()).append(as_utc(now))
            while len(self._failures) > self._max_entries:
                del self._failures[next(iter(self._failures))]

    def record_success(self, ip: str, username: str, now: datetime) -> None:
        token = self._token(ip, username, now)
        with self._lock:
            self._failures.pop(token, None)

    def _prune(self, now: datetime) -> None:
        cutoff = as_utc(now) - self._window
        empty = []
        for token, failures in self._failures.items():
            while failures and failures[0] < cutoff:
                failures.popleft()
            if not failures:
                empty.append(token)
        for token in empty:
            del self._failures[token]

