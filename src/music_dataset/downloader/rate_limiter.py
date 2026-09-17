"""Thread-safe rate limiter and concurrency controller."""

import threading
import time
from typing import Dict
from urllib.parse import urlparse


class HostRateLimiter:
    """Controls requests per second and concurrency per host."""

    def __init__(self, requests_per_second: float = 2.0, max_concurrency: int = 4):
        self.requests_per_second = max(0.1, requests_per_second)
        self.min_interval = 1.0 / self.requests_per_second
        self.semaphore = threading.Semaphore(max_concurrency)
        self.last_request_time = 0.0
        self.lock = threading.Lock()

    def acquire(self) -> None:
        self.semaphore.acquire()
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()

    def release(self) -> None:
        self.semaphore.release()


class RateLimitManager:
    """Manages per-host rate limiters."""

    def __init__(self, default_rps: float = 2.0, default_concurrency: int = 4):
        self.default_rps = default_rps
        self.default_concurrency = default_concurrency
        self.limiters: Dict[str, HostRateLimiter] = {}
        self.lock = threading.Lock()

    def get_limiter_for_url(self, url: str) -> HostRateLimiter:
        host = urlparse(url).netloc or "default"
        with self.lock:
            if host not in self.limiters:
                self.limiters[host] = HostRateLimiter(
                    requests_per_second=self.default_rps,
                    max_concurrency=self.default_concurrency,
                )
            return self.limiters[host]
