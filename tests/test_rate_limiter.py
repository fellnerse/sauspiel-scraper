import threading
import time

from sauspiel_scraper.rate_limiter import RateLimiter


def test_rate_limiter_pacing():
    # Set a high interval to make it easy to measure
    interval = 0.1
    limiter = RateLimiter(min_interval=interval)

    start = time.time()
    limiter.acquire()  # 1st
    limiter.acquire()  # 2nd (should wait ~0.1s)
    duration = time.time() - start

    assert duration >= interval
    assert limiter.total_requests == 2


def test_rate_limiter_429_blocks_all_threads():
    limiter = RateLimiter(min_interval=0.01)

    # Manual block to simulate reactive 429
    limiter.report_429(retry_after=1)  # Block for 1s

    start = time.time()
    limiter.acquire()  # Should block until the 1s pause expires
    duration = time.time() - start

    assert duration >= 0.9  # Account for timing jitter
    assert limiter.total_429s == 1


def test_rate_limiter_multithreaded_pacing():
    # 5 threads trying to do 2 requests each with 0.1s interval
    interval = 0.1
    limiter = RateLimiter(min_interval=interval)

    def run_paced():
        for _ in range(2):
            limiter.acquire()

    start = time.time()
    threads = [threading.Thread(target=run_paced) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start

    # 10 requests total. 9 intervals of 0.1s = 0.9s minimum.
    assert duration >= 0.9
    assert limiter.total_requests == 10
