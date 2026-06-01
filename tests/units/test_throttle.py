from datetime import UTC, datetime, timedelta

from oopsys_server.application.dedup import ThrottleInput, should_notify
from oopsys_server.domain.enums import ErrorGroupStatus, Severity

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
QUIET = 120
WINDOW = 600


def _decide(state: ThrottleInput) -> bool:
    return should_notify(state, now=NOW, quiet_gap_seconds=QUIET, renotify_window_seconds=WINDOW)


def test_new_group_always_notifies():
    assert _decide(ThrottleInput(True, ErrorGroupStatus.OPEN, Severity.ERROR, None, None)) is True


def test_muted_never_notifies():
    assert _decide(ThrottleInput(False, ErrorGroupStatus.MUTED, Severity.CRITICAL, None, None)) is False


def test_continuous_spam_suppressed():
    # Recurred only 10s after last occurrence (< quiet gap) -> no notify.
    state = ThrottleInput(
        is_new=False,
        status=ErrorGroupStatus.OPEN,
        severity=Severity.ERROR,
        previous_last_seen=NOW - timedelta(seconds=10),
        last_notified_at=NOW - timedelta(seconds=10),
    )
    assert _decide(state) is False


def test_recurrence_after_quiet_gap_notifies():
    state = ThrottleInput(
        is_new=False,
        status=ErrorGroupStatus.OPEN,
        severity=Severity.ERROR,
        previous_last_seen=NOW - timedelta(seconds=200),
        last_notified_at=NOW - timedelta(seconds=900),
    )
    assert _decide(state) is True


def test_rate_cap_blocks_even_after_quiet_gap():
    state = ThrottleInput(
        is_new=False,
        status=ErrorGroupStatus.OPEN,
        severity=Severity.ERROR,
        previous_last_seen=NOW - timedelta(seconds=200),
        last_notified_at=NOW - timedelta(seconds=120),
    )
    assert _decide(state) is False
