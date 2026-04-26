---
title: Parallel Rate-Limited Scraper with Global Pacing
date: 2026-04-26
category: performance-issues/
module: sauspiel_scraper
problem_type: performance_issue
component: tooling
symptoms:
  - HTTP 429 Too Many Requests errors every 20-30 requests
  - Inefficient sequential data fetching
root_cause: async_timing
resolution_type: code_fix
severity: medium
tags: [scraping, rate-limiting, concurrency, python-threading, performance]
---

# Parallel Rate-Limited Scraper with Global Pacing

## Problem
The sequential scraper was hitting a hard rate limit on the Sauspiel server approximately every 20 requests. The existing reactive logic tripling inter-request wait times was inefficient, causing long stalls and low throughput.

## Symptoms
- HTTP 429 Too Many Requests errors.
- Scraper halts or enters long cooling-off periods (60s+).
- Inconsistent performance due to reactive rather than proactive throttling.

## What Didn't Work
- **Reactive Backoff:** Waiting for a 429 to slow down is "too little, too late."
- **Burst-and-Pause:** Attempting to burst to the limit and then pausing is prone to sliding-window triggers and bot-detection heuristics.

## Solution
Implemented a centralized `RateLimiter` using a **Steady Global Pacing** strategy.

### 1. Steady Global Pacing
The `RateLimiter` enforces a minimum interval (default 2.0s) between the *start* of any two requests across all threads. This proactively stays under the server's sliding-window threshold, achieving a steady 30 RPM without triggering 429s.

### 2. Thread-Safe Orchestration
- **ThreadPoolExecutor:** Orchestrates parallel workers to overlap network I/O with HTML parsing and DB writes.
- **RLock for Sessions:** Uses `threading.RLock` in `SauspielScraper` for reentrant thread safety during session re-authentication.
- **SQLite Locking:** Synchronizes database writes to prevent "database is locked" errors.

## Why This Works
Steady pacing is the most stable strategy for servers with sliding-window rate limits. By ensuring a consistent gap between requests, we avoid the "traffic spikes" that trigger WAF burst filters. Concurrency ensures the scraper is always ready to fire the next request the moment the pacing interval expires.

## Prevention
- **Pacing over Bursting:** When scraping, always prefer a steady, low-velocity stream of requests over high-velocity bursts.
- **Global Rate Limiting:** In multi-threaded environments, throttling must be managed by a centralized governor to be effective.
- **Thread Safety:** Ensure shared resources like session cookie jars and database connections are properly locked.

## Related Issues
- `docs/solutions/architecture-patterns/architectural-decoupling-pydantic-2026-04-25.md`
