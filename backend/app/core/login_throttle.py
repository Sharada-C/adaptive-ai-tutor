"""Sliding-window brute-force protection for login.

Failures are tracked per normalised username and per client IP. Once a key
has MAX failures inside WINDOW seconds, further logins for it are refused
with the number of seconds until the oldest failure ages out.

State is in process memory: it is lost on restart and not shared between
worker processes. That is enough to stop online guessing against a single
server; a multi-worker deployment would move it to the database or Redis.
"""

import threading
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 300
MAX_FAILURES_PER_USERNAME = 10
# Higher, because many students can share one campus/NAT address.
MAX_FAILURES_PER_IP = 30

_lock = threading.Lock()
_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _keys(username: str, ip: str):
    return (
        (("user", username.strip().lower()), MAX_FAILURES_PER_USERNAME),
        (("ip", ip), MAX_FAILURES_PER_IP),
    )


def _prune(entries: deque, now: float) -> None:
    while entries and now - entries[0] >= WINDOW_SECONDS:
        entries.popleft()


def retry_after(username: str, ip: str) -> int:
    """Seconds the caller must wait, or 0 if the login may be attempted."""

    now = time.monotonic()
    wait = 0

    with _lock:
        for key, limit in _keys(username, ip):
            entries = _failures.get(key)

            if not entries:
                continue

            _prune(entries, now)

            if not entries:
                del _failures[key]
            elif len(entries) >= limit:
                wait = max(wait, int(WINDOW_SECONDS - (now - entries[0])) + 1)

    return wait


def record_failure(username: str, ip: str) -> None:
    now = time.monotonic()

    with _lock:
        for key, _limit in _keys(username, ip):
            _failures[key].append(now)


def record_success(username: str) -> None:
    """A valid login clears that username's history (the IP's is kept)."""

    with _lock:
        _failures.pop(("user", username.strip().lower()), None)


def reset() -> None:
    with _lock:
        _failures.clear()
