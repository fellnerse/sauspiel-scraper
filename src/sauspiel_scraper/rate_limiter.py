import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RateLimitStats:
    total_requests: int = 0
    total_429s: int = 0
    total_waited_seconds: float = 0.0
    start_time: datetime = datetime.now()

    @property
    def requests_per_minute(self) -> float:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed <= 0:
            return 0.0
        return (self.total_requests / elapsed) * 60


class RateLimiter:
    """
    A thread-safe rate limiter that enforces a global steady interval
    between requests and handles 429 blocks.
    """

    def __init__(
        self,
        burst_limit: int = 25,
        pause_time: float = 60.0,
        min_interval: float = 2.0,
    ):
        self.burst_limit = burst_limit
        self.pause_time = pause_time
        self.min_interval = min_interval

        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

        self.current_burst = 0
        self.is_blocked = False
        self.last_request_time = 0.0
        self.block_until = 0.0

        self.stats = RateLimitStats()

    def acquire(self) -> None:
        """
        Wait until a request can be made. Enforces both the min_interval
        and the burst_limit/pause_time logic.
        """
        with self._condition:
            while True:
                now = time.time()

                # 1. Check if we are globally blocked due to a 429
                if self.is_blocked:
                    if now < self.block_until:
                        wait_needed = self.block_until - now
                        self.stats.total_waited_seconds += wait_needed
                        self._condition.wait(wait_needed)
                        continue
                    else:
                        self.is_blocked = False
                        self.current_burst = 0

                # 2. Check burst limit
                if self.current_burst >= self.burst_limit:
                    # Trigger a proactive pause
                    wait_needed = self.pause_time + (random.random() * self.pause_time * 0.1)
                    self.block_until = now + wait_needed
                    self.is_blocked = True
                    continue

                # 3. Enforce steady interval (pacing)
                time_since_last = now - self.last_request_time
                if time_since_last < self.min_interval:
                    wait_needed = self.min_interval - time_since_last + (random.random() * 0.2)
                    self.stats.total_waited_seconds += wait_needed
                    self._condition.wait(wait_needed)
                    continue

                # If we get here, we can proceed
                self.last_request_time = time.time()
                self.current_burst += 1
                self.stats.total_requests += 1
                break

    def report_success(self) -> None:
        """Called after a successful request."""
        # We don't necessarily need to do anything here if we use steady pacing,
        # but we could use it to slowly decrease min_interval if we wanted to calibrate.
        pass

    def report_429(self, retry_after: int | None = None) -> None:
        """Called when a 429 Too Many Requests is received."""
        with self._condition:
            now = time.time()
            wait_time = retry_after + 1 if retry_after else self.pause_time
            # Add jitter to avoid thundering herd on recovery
            wait_time += random.random() * 5.0

            self.block_until = now + wait_time
            self.is_blocked = True
            self.stats.total_429s += 1
            self._condition.notify_all()

    def get_stats(self) -> RateLimitStats:
        with self._lock:
            return self.stats
