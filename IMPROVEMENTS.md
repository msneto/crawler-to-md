# IMPROVEMENTS

## Scope and Target Runs

This document focuses on the most common usage profiles:

1. Single seed URL crawl.
2. Large crawl expansion (many discovered links).
3. Single compiled exported Markdown output, usually minified (`--minify`), often with JSON disabled (`--no-json`).

For each improvement:
- **Current context**: how behavior works now.
- **Why suboptimal**: cost/risk observed.
- **Possible solutions**: 1-3 options, each ranked:
  - **Rank 1**: quick win, low structural change.
  - **Rank 2**: moderate refactor, touches multiple functions/files.
  - **Rank 3**: architectural change, broader impact.

---

## Crawl Path, CPU, and Time

### 1) Double HTML parse per page (content + links)
**Current context**
Optimized. The scraper now uses a "One-Parse" architecture with `lxml`.

**Why suboptimal (Before Fix)**
BeautifulSoup parsing is expensive. Parsing twice per page doubled CPU costs.

**Solution (Implemented)**
Implemented a **Fast-Path** that reuses the initial `lxml` DOM for both link extraction and Markdown conversion (via internal `CustomMarkdownify`).

### 2) Temporary file + per-page converter instantiation
**Current context**
Optimized. Conversion is now in-memory and reuses a single converter instance.

**Why suboptimal (Before Fix)**
High per-page overhead: disk I/O, filesystem churn, repeated object setup.

**Solution (Implemented)**
Switched to `io.BytesIO` streams and direct DOM-to-Markdown conversion, bypassing the disk entirely. Reused one `MarkItDown` instance (as a fallback) per scraper run.

### 3) Per-link DB insert in discovery loop
**Current context**
Optimized. Uses batch inserts.

**Why suboptimal (Before Fix)**
SQLite transaction overhead dominated large crawls.

**Solution (Implemented)**
Added `insert_links` and `upsert_pages` batch methods to `DatabaseManager`. The scraping loop now groups updates.

### 4) Full unvisited list fetch each loop
**Current context**
Optimized. Uses `LIMIT` batching.

**Why suboptimal (Before Fix)**
Inefficient with large queues; repeated full scans and list materialization.

**Solution (Implemented)**
Implemented `get_unvisited_links(limit=...)` to process the queue in manageable chunks.

### 5) Missing index on `links.visited`
**Current context**
Queries filter by `visited` and count by `visited`, but schema has no dedicated index.

**Why suboptimal**
Table scans become expensive as link table grows.

**Possible solutions**
- **[Rank 1]** Add index `CREATE INDEX IF NOT EXISTS idx_links_visited ON links(visited)`.
- **[Rank 2]** Add covering/compound indexes tuned for fetch/count patterns.
- **[Rank 3]** Redesign link state schema for queue semantics (status + timestamps + retries).

### 6) URL scope check uses string prefix
**Current context**
`is_valid_link()` relies on `startswith(base_url)` and substring include/exclude checks.

**Why suboptimal**
Can misclassify URLs, cause over-crawl/under-crawl, and create duplicates.

**Possible solutions**
- **[Rank 1]** Parse URLs and compare normalized host/path prefixes.
- **[Rank 2]** Add canonicalization before all DB operations (scheme/host case, fragments, slash policy).
- **[Rank 3]** Add configurable URL policy engine (domain/path/query rules, allow/deny precedence).

### 7) Non-HTTP links are not rejected early
**Current context**
Link extraction can include `mailto:`, `javascript:`, `tel:` before validation logic catches/filters indirectly.

**Why suboptimal**
Wasted processing and noisy link set.

**Possible solutions**
- **[Rank 1]** Skip unsupported schemes immediately during extraction.
- **[Rank 2]** Centralize canonicalization + scheme policy in one utility function.
- **[Rank 3]** Add protocol plugin architecture (http/https today, optional others later).

### 8) Retry model can repeatedly revisit failures without policy depth
**Current context**
Failed pages (`content IS NULL`) are auto-requeued every run.

**Why suboptimal**
Potential repeated waste on permanent failures; no retry backoff budget.

**Possible solutions**
- **[Rank 1]** Add max retry count in metadata.
- **[Rank 2]** Add structured retry fields in DB (`retry_count`, `last_error`, `next_retry_at`).
- **[Rank 3]** Full retry scheduler with error-class aware backoff.

### 9) Rate limiting uses coarse per-minute counter
**Current context**
Counter resets each minute window and can sleep a large chunk.

**Why suboptimal**
Burstiness and coarse pacing; can be inefficient and unfriendly to target servers.

**Possible solutions**
- **[Rank 1]** Keep current model, improve monotonic timing and boundary math.
- **[Rank 2]** Token-bucket/leaky-bucket implementation.
- **[Rank 3]** Adaptive politeness model by response latency/status/server hints.

### 10) Requests session not tuned for retry/connection pool policy
**Current context**
Optimized. Configured with `HTTPAdapter`, connection pooling, and `urllib3.Retry`.

**Why suboptimal (Before Fix)**
Lost opportunities for connection reuse and robust transient error handling.

**Solution (Implemented)**
Configured `HTTPAdapter` with `pool_connections=10`, `pool_maxsize=10`, and a `Retry` strategy for transient statuses (429, 500, 502, 503, 504) and idempotent-safe methods.

---

## Export Path, Minify Path, RAM

### 11) `get_all_pages()` loads entire dataset for exports
**Current context**
Optimized. Uses cursor-based iteration.

**Why suboptimal (Before Fix)**
RAM spikes for large crawls and slower startup to first write.

**Solution (Implemented)**
Implemented `get_pages_iterator()` using `fetchmany(100)` to stream records from SQLite.

### 12) Markdown concatenation uses repeated `+=` on large string
**Current context**
Fixed. Uses `"".join(parts)`.

### 13) Cleanup called repeatedly on growing output
**Current context**
Fixed. `_cleanup_markdown` is called once after concatenation.

### 14) Minify mode generates metadata/comments then strips them
**Current context**
Compiled markdown adds metadata comments and separators, then minifier removes many of them.

**Why suboptimal**
Wasted CPU and memory in exactly the common minified flow.

**Possible solutions**
- **[Rank 1]** In minify mode, skip metadata comments generation.
- **[Rank 2]** In minify mode, skip separator emission too.
- **[Rank 3]** Separate "AI-minified export strategy" from "human-readable export strategy."

### 15) JSON pretty-print (`indent=4`) always enabled
**Current context**
Optimized. Automatically compacts when `--minify` is enabled.

**Why suboptimal (Before Fix)**
Larger files and slower writes; unnecessary for machine-ingestion flows.

**Solution (Implemented)**
Linked JSON formatting to the `--minify` flag. When enabled, it uses `indent=None` and compact separators `(",", ":")`.

### 16) Individual markdown path mapping uses basic string replace
**Current context**
Path generation removes protocol and optionally base URL via string replacement.

**Why suboptimal**
Can lead to edge-case path correctness/security issues with complex URLs.

**Possible solutions**
- **[Rank 1]** Parse URL path safely and sanitize path segments.
- **[Rank 2]** Centralize URL->filesystem mapping with test corpus.
- **[Rank 3]** Add pluggable path strategy (`flat`, `hierarchical`, `hashed`).

---

## Resource Lifecycle, Code Health, Extensibility

### 17) Database connection cleanup relies on `__del__`
**Current context**
Optimized. Explicit `close()` is called in the CLI `finally` block.

**Why suboptimal (Before Fix)**
Destructor timing is non-deterministic; can leak handles in longer-lived contexts.

**Solution (Implemented)**
Added an explicit `close()` method to `DatabaseManager` and ensured it is called within a `finally` block in `cli.py`.

### 18) Logging setup may duplicate handlers over time
**Current context**
Fixed. Setup is now idempotent.

### 25) Regex-based URL Filtering
**Current context**
Optimized. Patterns are pre-compiled.

**Why suboptimal (Before Fix)**
Iterating through exclusion lists in a Python loop for every discovered link was slow ($O(N \times M)$).

**Solution (Implemented)**
Pre-compiles all include/exclude patterns into a single optimized regex object for $O(N)$ matching.

### 26) Early Network Termination (`stream=True`)
**Current context**
Optimized. Checks headers before download.

**Why suboptimal (Before Fix)**
The scraper downloaded full bodies of all assets (images, zips) just to check the `Content-Type`.

**Solution (Implemented)**
Uses `stream=True` to inspect headers and immediately close connections for non-HTML resources.

### 19) Scraper loop is monolithic
**Current context**
One large method handles queue logic, timing, fetch, parse, persist, discovery.

**Why suboptimal**
Hard to test, tune, and extend (e.g., concurrency, retries, metrics).

**Possible solutions**
- **[Rank 1]** Extract helper methods without behavior change.
- **[Rank 2]** Split into cohesive components (fetcher, parser, frontier, persister).
- **[Rank 3]** Build explicit crawl engine architecture with plugin hooks.

### 20) Error typing and metadata structure are partially ad hoc
**Current context**
Some failures are typed, but broad `except Exception` remains and metadata schema is soft.

**Why suboptimal**
Reduced observability and weaker future automation around retries/reporting.

**Possible solutions**
- **[Rank 1]** Narrow exception catches and include structured error code fields.
- **[Rank 2]** Define typed error model and centralized metadata serializer.
- **[Rank 3]** Persist normalized failure taxonomy in DB schema.

---

## Workflow / CI / Packaging

### 21) CI does not enforce lint/tests across normal PR flow
**Current context**
Workflows focus on build/publish; quality gates are not strongly enforced for every PR.

**Why suboptimal**
Performance regressions and correctness issues can slip through.

**Possible solutions**
- **[Rank 1]** Add CI job for `ruff check .` and `pytest`.
- **[Rank 2]** Add matrix smoke tests (Python 3.10-3.12) and selective test splitting.
- **[Rank 3]** Add perf regression checks on representative crawl fixtures.

### 22) Docker PR workflow is expensive
**Current context**
PRs trigger multi-arch build pipeline intended for publish-grade artifacts.

**Why suboptimal**
Long feedback loops and higher CI cost.

**Possible solutions**
- **[Rank 1]** PR: single-arch build only; release/main: multi-arch + push/sign.
- **[Rank 2]** Split validation and publish workflows.
- **[Rank 3]** Add staged pipeline (lint/test -> build -> publish) with artifact promotion.

### 23) `.dockerignore` typo and optimization opportunities
**Current context**
Typo exists (`/pytest_cahe`) and context exclusions can be improved.

**Why suboptimal**
Potential larger Docker build context and unnecessary cache invalidation.

**Possible solutions**
- **[Rank 1]** Fix typo and validate ignored files.
- **[Rank 2]** Tighten `.dockerignore` with generated artifacts and local caches.
- **[Rank 3]** Rework Docker context strategy with dedicated build context layout.

### 24) Dependency footprint likely heavier than runtime usage
**Current context**
Several dependencies appear not active in current code path for core crawl/export operations.

**Why suboptimal**
Slower installs, larger images, more supply-chain surface.

**Possible solutions**
- **[Rank 1]** Audit and remove clearly unused runtime deps.
- **[Rank 2]** Move optional features to extras (`[project.optional-dependencies]`).
- **[Rank 3]** Introduce profile-based package variants (`core`, `full`).

---

## Prioritized Execution Roadmap (Recommended)

### Phase 1 - Quick Wins (high ROI, low risk)
1. Index `links(visited)`.
2. Bulk discovered-link inserts.
3. End-of-process markdown cleanup (remove per-iteration cleanup).
4. Skip metadata/separator generation in minify mode.
5. Add iterator-based page export path.

### Phase 2 - Moderate Refactors
6. Single-pass parse/extract/convert per page.
7. Chunked unvisited-link retrieval.
8. URL canonicalization + stricter scope checks.
9. Explicit DB lifecycle management.

### Phase 3 - Architectural Enhancements
10. Scraper componentization.
11. Converter/storage abstractions.
12. CI perf checks and staged workflow architecture.

---

## Notes on Impact for Target Use Case

- For **single URL + many links + minified single `.md`**, the largest practical gains are expected from:
  1. One-pass parsing.
  2. Bulk DB operations + indexed visited-state queries.
  3. Streaming/minify-aware export (avoid build-then-strip behavior).
- These areas are likely to reduce CPU, wall-clock time, and RAM together, while also making future features easier to add safely.
