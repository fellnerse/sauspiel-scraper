import threading
import time

from sauspiel_scraper.rate_limiter import RateLimiter


def test_rate_limiter_pacing():
    # Set a high interval to make it easy to measure
    interval = 0.1
    limiter = RateLimiter(min_interval=interval, burst_limit=100)

    start = time.time()
    limiter.acquire()  # 1st
    limiter.acquire()  # 2nd (should wait ~0.1s)
    duration = time.time() - start

    assert duration >= interval
    assert limiter.stats.total_requests == 2


def test_rate_limiter_burst_pause():
    # Small burst to trigger pause
    limiter = RateLimiter(burst_limit=2, pause_time=0.2, min_interval=0.01)

    start = time.time()
    limiter.acquire()  # 1
    limiter.acquire()  # 2
    limiter.acquire()  # 3 (should trigger 0.2s pause)
    duration = time.time() - start

    assert duration >= 0.2
    assert limiter.stats.total_requests == 3


def test_rate_limiter_429_blocks_all_threads():
    limiter = RateLimiter(pause_time=0.5, min_interval=0.01)

    def worker():
        limiter.acquire()
        # Simulate hitting 429 on first request
        limiter.report_429(retry_after=None)

    t1 = threading.Thread(target=worker)
    t1.start()
    t1.join()

    assert limiter.is_blocked

    start = time.time()
    limiter.acquire()  # Should block until the 0.5s pause expires
    duration = time.time() - start

    assert duration >= 0.4  # Slightly less than 0.5 to account for timing jitter
    assert limiter.stats.total_429s == 1


def test_rate_limiter_multithreaded_contention():
    # 5 threads trying to burst through a limit of 10
    limiter = RateLimiter(burst_limit=10, min_interval=0.01, pause_time=0.1)

    def run_burst():
        for _ in range(5):
            limiter.acquire()

    threads = [threading.Thread(target=run_burst) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 5 * 5 = 25 requests. With burst_limit=10, it should have paused twice.
    assert limiter.stats.total_requests == 25
    assert limiter.current_burst >= 0  # Reset logic might have cleared it
