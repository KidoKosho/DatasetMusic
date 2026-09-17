"""Retry policy with exponential backoff and jitter."""

import random
import time
from typing import Callable, Optional, Set, Type, TypeVar
import requests

RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    ConnectionResetError,
    TimeoutError,
)

T = TypeVar("T")


def exponential_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    jitter_factor: float = 0.5,
) -> float:
    """Calculate exponential backoff delay with random jitter."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    jitter = random.uniform(0, jitter_factor * delay)
    return delay + jitter


def retry_with_backoff(
    fn: Callable[..., T],
    max_retries: int = 5,
    base_delay: float = 1.0,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    """Execute function with retries and exponential backoff."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            should_retry = False
            if isinstance(e, RETRYABLE_EXCEPTIONS):
                should_retry = True
            elif isinstance(e, requests.exceptions.HTTPError):
                if e.response is not None and e.response.status_code in RETRYABLE_STATUS_CODES:
                    should_retry = True

            if should_retry and attempt < max_retries:
                delay = exponential_backoff_with_jitter(attempt, base_delay=base_delay)
                if on_retry:
                    on_retry(attempt + 1, e, delay)
                time.sleep(delay)
                attempt += 1
            else:
                raise e
