from dataclasses import dataclass
from datetime import datetime, timedelta

from oopsys_server.domain.enums import ErrorGroupStatus, Severity


@dataclass(slots=True)
class ThrottleInput:
    is_new: bool
    status: ErrorGroupStatus
    severity: Severity
    previous_last_seen: datetime | None
    last_notified_at: datetime | None


def should_notify(state: ThrottleInput, *, now: datetime, quiet_gap_seconds: int, renotify_window_seconds: int) -> bool:
    if state.status is not ErrorGroupStatus.OPEN:
        return False
    if state.is_new:
        return True
    quiet_gap = timedelta(seconds=quiet_gap_seconds)
    renotify_window = timedelta(seconds=renotify_window_seconds)
    recurred_after_quiet = state.previous_last_seen is None or now - state.previous_last_seen >= quiet_gap
    rate_ok = state.last_notified_at is None or now - state.last_notified_at >= renotify_window
    return recurred_after_quiet and rate_ok
