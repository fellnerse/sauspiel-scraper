---
title: Parallel Rate-Limited Scraper with Global Pacing
date: 2026-04-26
category: performance-issues/
module: sauspiel_scraper
problem_type: performance_issue
component: tooling
symptoms:
  - HTTP 429 Too Many Requests errors every 20-30 requests
  - Scraper throughput limited by reactive adaptive delay logic
  - Inefficient sequential data fetching
root_cause: async_timing
resolution_type: code_fix
severity: medium
tags: [scraping, rate-limiting, concurrency, python-threading, performance]
---

# Parallel Rate-Limited Scraper with Global Pacing

## Problem
The sequential scraper was hitting a hard rate limit on the Sauspiel server approximately every 20 requests. The existing reactive adaptive delay logic penalized future requests heavily after a 429 was hit, leading to low throughput and frequent blocks.

## Symptoms
- HTTP 429 Too Many Requests errors.
- Scraper halts or enters long cooling-off periods (60s+).
- Low throughput (~12-15 games per minute) when hitting limits.

## What Didn't Work
- **Reactive Adaptive Delay:** Tripling the inter-request wait time *after* a 429 was hit was too late and too harsh.
- **Burst-and-Pause:** Attempting to burst to the 20-request limit and then pausing for 60s is prone to "sliding window" resets and bot-detection heuristics.
- **Simple threading:** Multiple threads without a centralized governor hit the 20-request burst limit nearly instantly.

## Solution
Implemented a centralized `RateLimiter` using a **Steady Global Pacing** strategy.

### 1. Steady Global Pacing
Instead of bursting, the `RateLimiter` enforces a minimum interval (default 2.0s) between the *start* of any two requests across all threads. This ensures a steady 30 RPM that stays proactively under the server's sliding-window threshold, achieving 100 games in ~3.4 minutes without 429s.

### 2. Thread-Safe Orchestration
- **ThreadPoolExecutor:** Orchestrates parallel game fetching, allowing parsing and DB writes to overlap with network latency.
- **Double-Check Locking:** Uses `threading.RLock` in `SauspielScraper` for reentrant thread safety during session re-authentication.
- **SQLite Synchronization:** Added application-level locking in `Database` to prevent write collisions.

### 3. Calibration Metrics
Added a summary at the end of every run reporting Average RPM, total 429s, and total wait time to allow for empirical optimization.

## Why This Works
Steady pacing is more stable than "Burst and Wait" because it never triggers the server's anti-burst filters. By staying proactively under the limit, we avoid the aggressive WAF cooling-off periods entirely. Concurrency allows us to overlap the network latency of one request with the heavy HTML parsing of another.

## Prevention
- **Proactive Throttling:** Always use a global rate limiter for scrapers targeting sensitive endpoints.
- **Steady Pacing:** Prefer a steady request interval over rapid bursts to mimic human-like browsing patterns.
- **Reentrant Locks:** Use `RLock` when a locked method calls another method that also requires the same lock, but prefer decomposing into public safe wrappers and private unlocked implementations for better clarity.

## Related Issues
- `docs/solutions/architecture-patterns/architectural-decoupling-pydantic-2026-04-25.md`
