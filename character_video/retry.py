"""Retry helpers.

Two different failure classes, two different policies:

  transport error (timeout, 429, 5xx) -> retry with exponential backoff + jitter
  task failed (model returned failed)  -> do NOT auto-retry: the request was
                                          already billed, so retrying doubles cost
"""

from __future__ import annotations

import random
import time
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def backoff_delays(attempts: int, base: float = 1.5, cap: float = 30.0) -> Iterable[float]:
    for attempt in range(attempts):
        raw = min(cap, base * (2**attempt))
        yield raw * (0.7 + random.random() * 0.6)  # jitter so parallel jobs spread out


def with_backoff(
    fn: Callable[[], T],
    attempts: int = 4,
    base: float = 1.5,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Call fn(), retrying transient errors. Raises the last error if all attempts fail."""
    last_error: Exception | None = None
    for index, delay in enumerate(backoff_delays(attempts, base)):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - caller decides what is retryable
            last_error = exc
            if not _is_retryable(exc) or index == attempts - 1:
                raise
            if on_retry:
                on_retry(index + 1, exc)
            time.sleep(delay)
    raise last_error  # pragma: no cover


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status) in RETRYABLE_STATUS
    name = type(exc).__name__.lower()
    return any(word in name for word in ("timeout", "connection", "ssl"))
