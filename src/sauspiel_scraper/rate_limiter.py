import random
import threading
import time


class RateLimiter:
    """
    A thread-safe rate limiter that enforces a global steady interval
    between requests.
    """

    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval

        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

        self.last_request_time = 0.0
        self.block_until = 0.0

        # Simple stats for basic monitoring
        self.total_requests = 0
        self.total_429s = 0

    def acquire(self) -> None:
        """
        Wait until a request can be made according to the steady interval.
        """
        with self._condition:
            while True:
                now = time.time()

                # 1. Check if we are globally blocked (e.g. after a 429)
                if now < self.block_until:
                    self._condition.wait(self.block_until - now)
                    continue

                # 2. Enforce steady interval (pacing)
                time_since_last = now - self.last_request_time
                if time_since_last < self.min_interval:
                    # Add a tiny bit of jitter to avoid deterministic signatures
                    wait_needed = self.min_interval - time_since_last + (random.random() * 0.1)
                    self._condition.wait(wait_needed)
                    continue

                # If we get here, we can proceed
                self.last_request_time = time.time()
                self.total_requests += 1
                break

    def report_429(self, retry_after: int | None = None) -> None:
        """Called when a 429 Too Many Requests is received."""
        with self._condition:
            now = time.time()
            wait_time = retry_after + 1 if retry_after else 60.0
            # Add jitter to avoid thundering herd on recovery
            wait_time += random.random() * 5.0

            self.block_until = now + wait_time
            self.total_429s += 1
            self._condition.notify_all()
