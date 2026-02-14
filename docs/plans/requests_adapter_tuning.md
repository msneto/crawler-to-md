# Plan: Requests Adapter Tuning & Retries (Improvement #10)

## Problem Statement
The `Scraper` class uses a default `requests.Session()` without specialized configuration, leading to:
1. Lack of connection pooling.
2. No automatic retries for transient network failures or temporary server-side errors (429, 503, etc.).

## Selected Solution: Alternative A
Standard `urllib3.util.Retry` with `HTTPAdapter`. This idiomatic approach handles exponential backoff and connection pooling transparently at the transport layer.

## Actionable Steps

### Step 1: Update Imports
- **Files:** `crawler_to_md/scraper.py`
- **Description:** Add `from requests.adapters import HTTPAdapter` and `from urllib3.util import Retry`.
- **Points of Attention:** Standard import placement.
- **Risks:** None.
- **Tests:** Smoke tests.

### Step 2: Initialize Retry and Adapter in `Scraper.__init__`
- **Files:** `crawler_to_md/scraper.py`
- **Description:** Configure `Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])`. Instantiate `HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry)`.
- **Points of Attention:** `backoff_factor=1` results in 1s, 2s, 4s sleeps.
- **Risks:** Fixed pool size. **Mitigation:** Reasonable defaults for now.
- **Tests:** Verify adapter configuration in `Scraper` instance.

### Step 3: Mount the Adapter
- **Files:** `crawler_to_md/scraper.py`
- **Description:** Call `self.session.mount("https://", adapter)`. and `self.session.mount("http://", adapter)`.
- **Points of Attention:** Must cover both protocols.
- **Risks:** Missing a protocol. **Mitigation:** Explicitly mount both.
- **Tests:** Session adapter mount check.

### Step 4: Implement Retry Verification Test
- **Files:** `tests/test_scraper.py`
- **Description:** Use mocking to simulate transient failures (503) and verify successful recovery.
- **Points of Attention:** Mock `time.sleep` to keep tests fast.
- **Risks:** Test flakiness. **Mitigation:** Deterministic mocking.
- **Tests:**
    - 200 OK (Success).
    - 503 -> 200 (Successful retry).
    - 429 (Rate limit handling).
    - Persistent 500 (Exhaustion failure).
