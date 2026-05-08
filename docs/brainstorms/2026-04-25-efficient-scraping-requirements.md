# Requirements: Efficient Parallel Scraper for Sauspiel

## Overview
The current sequential scraper hits a rate limit (HTTP 429) approximately every 20 requests. When limited, it applies a harsh exponential penalty to the inter-request delay, leading to significantly degraded performance. This document outlines a move toward a **Parallel & Proactive** scraping architecture that maximizes throughput while staying safely under the detected limits.

## Goals
- **Increase Speed:** Leverage parallelism to overcome network latency bottlenecks.
- **Proactive Throttling:** Avoid hitting 429 errors by tracking request counts and pausing *before* the server's limit is reached.
- **Efficient Recovery:** If a 429 is hit, wait only as long as necessary (honor `Retry-After`) and resume at an optimal rate rather than staying in a penalized state.
- **Maintain Reliability:** Ensure data integrity and session stability are not compromised by concurrency.

## Success Criteria
- **Throughput:** Fetching 100 game records should be at least 3-4x faster than the current sequential approach.
- **Stability:** Zero 429 errors in a standard 50-game run.
- **Calibration:** The system can automatically or semi-automatically detect the window reset time.

## Proposed Behavior

### 1. Parallel Fetching
- Move from sequential `requests` to concurrent fetching (using `httpx.AsyncClient` or `ThreadPoolExecutor` with `requests`).
- Implement a **Concurrency Cap** (e.g., max 5–8 simultaneous requests) to avoid triggering WAF/DDoS protections while still gaining speed.

### 2. Batch-Aware Rate Limiting
Instead of a simple delay between requests, implement a **Token Bucket** or **Fixed Window** rate limiter:
- **Configurable Quotas:** Allow up to N requests (starting at 18) before pausing.
- **Dynamic Pause:** Enforce a pause of M seconds (starting at 60s).
- **Empirical Calibration:** These numbers (N=20, M=60) are currently heuristics. The implementation must include logging or a "probe" mode to verify the *actual* server boundaries and optimize for the shortest safe reset window.
- **Jitter:** Add random variance (±10%) to the pause duration to avoid "heartbeat" detection.

### 3. Smart 429 Handling
- **Header Parsing:** Priority is given to the `Retry-After` header if provided by the server.
- **State Reset:** Unlike the current "adaptive delay" which persists for many requests, a 429 should trigger a "Wait & Reset" cycle where the system clears its request history and resumes at a safe rate.

### 4. Calibration Mode (Optional)
- A specialized CLI command or internal flag to "test" the boundaries of the rate limit to find the shortest possible reset window (e.g., is it 60s, 30s, or shorter?).

## Scope Boundaries

### Included
- Refactoring `SauspielScraper.scrape_game` to support batch/parallel processing.
- Implementing the `RateLimiter` logic.
- Updating `main.py` to orchestration parallel tasks.

### Deferred / Out of Scope
- **Proxy Rotation:** Not needed yet as per-account/per-IP limits seem manageable with simple pauses.
- **Headless Browsers:** Continue using HTML parsing for performance; avoid Playwright/Selenium unless strictly necessary for bypass.
- **Database Concurrency:** Keep SQLite writes sequential or use a proper connection pool/queue to avoid "database is locked" errors during parallel scraping.

## Key Assumptions & Risks
- **Assumption:** The limit is based on request count per window (fixed or sliding).
- **Risk:** The server might interpret parallel requests from the same IP as more aggressive than sequential ones, even if the total count is the same.
- **Mitigation:** Start with low concurrency (e.g., 3) and increase after verification.
