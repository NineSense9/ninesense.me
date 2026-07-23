from datetime import datetime, timedelta, timezone

from ninesense_guestbook.services.rate_limit import SubmissionLimiter


def test_daily_limit_applies_even_when_short_windows_have_elapsed():
    limiter = SubmissionLimiter("secret")
    start = datetime(2026, 7, 23, 0, 0, tzinfo=timezone.utc)

    for index in range(10):
        assert limiter.allow("203.0.113.10", start + timedelta(minutes=11 * index))

    assert not limiter.allow("203.0.113.10", start + timedelta(minutes=110))

