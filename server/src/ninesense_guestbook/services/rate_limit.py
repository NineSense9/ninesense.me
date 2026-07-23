from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from threading import Lock


class SubmissionLimiter:
    def __init__(
        self,
        secret: str,
        short_limit: int = 3,
        short_window: timedelta = timedelta(minutes=10),
        daily_limit: int = 10,
    ):
        self._secret = secret.encode("utf-8")
        self._short_limit = short_limit
        self._short_window = short_window
        self._daily_limit = daily_limit
        self._events: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    def _token(self, ip: str, now: datetime) -> str:
        day = now.astimezone(timezone.utc).date().isoformat()
        value = f"{day}:{ip}".encode("utf-8")
        return hmac.new(self._secret, value, hashlib.sha256).hexdigest()

    def allow(self, ip: str, now: datetime) -> bool:
        now = now.astimezone(timezone.utc)
        token = self._token(ip, now)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        short_start = now - self._short_window

        with self._lock:
            self._prune(now)
            events = self._events.setdefault(token, deque())
            short_count = sum(event >= short_start for event in events)
            daily_count = sum(event >= day_start for event in events)
            if short_count >= self._short_limit or daily_count >= self._daily_limit:
                return False
            events.append(now)
            return True

    def _prune(self, now: datetime) -> None:
        retention_start = now - timedelta(days=1)
        empty_tokens = []
        for token, events in self._events.items():
            while events and events[0] < retention_start:
                events.popleft()
            if not events:
                empty_tokens.append(token)
        for token in empty_tokens:
            del self._events[token]
