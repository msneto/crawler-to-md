# IMPROVEMENTS IMPLEMENTATION PLAN

## Goal

Turn findings in `IMPROVEMENTS.md` into an execution-ready backlog with clear order,
scope, test impact, and risk.

Primary target profile:
1. Single seed URL.
2. Many discovered links.
3. Single compiled minified Markdown export.

## Progress Snapshot

- Completed: Task 1.1 (index on `links.visited`)
- Completed: Task 1.2 (bulk discovered-link insert path)
- Completed: Task 1.3 and Task 1.4 (minify-aware compiled markdown optimizations)
- Completed: Task 2.1 (paged unvisited-link reads in crawl loop)
- Completed: Task 2.2 (single-pass parse/extract in crawl path)
- Completed: Task 2.3 (single MarkItDown instance reused per scrape run)

---

## Planning Assumptions

- Preserve current behavior by default unless explicitly called out.
- Favor incremental, reviewable PRs.
- Every step includes matching test updates and local validation.
- Performance work should include before/after measurement on a fixed crawl fixture.

Effort scale:
- **S**: up to half day
- **M**: 1-2 days
- **L**: 3-5 days
- **XL**: 1+ week

Risk scale:
- **Low**: unlikely behavior drift
- **Med**: moderate regression surface
- **High**: broad behavior/API surface

---

## Phase 0 - Baseline and Safety Nets

### Task 0.1 - Add repeatable performance benchmark harness
- **Why**: avoid subjective "faster/slower" claims.
- **Changes**:
  - Add a small benchmark script under `scripts/` (e.g. crawl fixture HTML set).
  - Capture wall time, peak RSS (if available), links processed/sec.
- **Files**:
  - `scripts/benchmark_crawl.py` (new)
  - `README.md` (benchmark usage section)
- **Tests**: none required; script smoke execution.
- **Effort/Risk**: S / Low

### Task 0.2 - Add CI quality gate for lint/tests
- **Why**: guard against regressions while refactoring.
- **Changes**:
  - Add a workflow for `ruff check .` and `pytest` on PR.
- **Files**:
  - `.github/workflows/ci.yaml` (new)
- **Tests**: workflow validation.
- **Effort/Risk**: S / Low

---

## Phase 1 - High ROI, Low Structural Change

### Task 1.1 - Add SQLite index for visited state
- **Items covered**: Improvement #5.
- **Changes**:
  - Add `idx_links_visited` creation in `create_tables()`.
- **Files**:
  - `crawler_to_md/database_manager.py`
  - `tests/test_database_manager.py`
- **Validation**:
  - `pytest tests/test_database_manager.py`
- **Effort/Risk**: S / Low

### Task 1.2 - Bulk insert discovered links
- **Items covered**: Improvement #3.
- **Changes**:
  - Add bulk insert method (or optimize existing list path with `executemany`).
  - Update discovery loop to insert in batches rather than one URL at a time.
- **Files**:
  - `crawler_to_md/database_manager.py`
  - `crawler_to_md/scraper.py`
  - `tests/test_database_manager.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_database_manager.py tests/test_scraper.py -k link`
- **Effort/Risk**: M / Low

### Task 1.3 - Export cleanup pass only once
- **Items covered**: Improvement #13.
- **Changes**:
  - Move `_cleanup_markdown` call out of per-page loop in compiled markdown export.
- **Files**:
  - `crawler_to_md/export_manager.py`
  - `tests/test_export_manager.py`
- **Validation**:
  - `pytest tests/test_export_manager.py`
- **Effort/Risk**: S / Low

### Task 1.4 - Minify-aware markdown assembly shortcuts
- **Items covered**: Improvement #14.
- **Changes**:
  - Skip metadata comments generation in minify mode.
  - Skip separator generation in minify mode when redundant.
- **Files**:
  - `crawler_to_md/export_manager.py`
  - `tests/test_export_manager.py`
- **Validation**:
  - `pytest tests/test_export_manager.py -k minify`
- **Effort/Risk**: M / Med

### Task 1.5 - Fix `.dockerignore` typo
- **Items covered**: Improvement #23.
- **Changes**:
  - Correct `/pytest_cahe` -> `/.pytest_cache`.
- **Files**:
  - `.dockerignore`
- **Validation**:
  - `docker build -t crawler-to-md .` (optional quick check)
- **Effort/Risk**: S / Low

---

## Phase 2 - Moderate Refactors

### Task 2.1 - Introduce paged DB readers for crawl queue
- **Items covered**: Improvement #4.
- **Changes**:
  - Add `get_unvisited_links(limit=...)`.
  - Update loop to fetch next chunks and avoid full materialization.
- **Files**:
  - `crawler_to_md/database_manager.py`
  - `crawler_to_md/scraper.py`
  - `tests/test_database_manager.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_scraper.py tests/test_database_manager.py`
- **Effort/Risk**: M / Med

### Task 2.2 - Single-pass HTML processing (no second parse)
- **Items covered**: Improvement #1.
- **Changes**:
  - Consolidate parse/filter/link extraction in one path.
  - Ensure include/exclude selector behavior is unchanged.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_scraper.py`
- **Effort/Risk**: L / Med

### Task 2.3 - Reuse converter instance in scraper
- **Items covered**: Improvement #2 (partial).
- **Changes**:
  - Instantiate converter once in `Scraper.__init__`.
  - Use same instance in page conversions.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_scraper.py -k scrape_page`
- **Effort/Risk**: S / Med

### Task 2.4 - URL canonicalization and stricter scope checks
- **Items covered**: Improvements #6 and #7.
- **Changes**:
  - Add URL normalize utility.
  - Apply canonicalization before insert/validate.
  - Explicitly skip non-http(s) schemes during discovery.
- **Files**:
  - `crawler_to_md/utils.py`
  - `crawler_to_md/scraper.py`
  - `tests/test_utils.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_utils.py tests/test_scraper.py`
- **Effort/Risk**: L / Med

### Task 2.5 - Explicit DB lifecycle (`close` and context safety)
- **Items covered**: Improvement #17.
- **Changes**:
  - Add `close()` on manager.
  - Ensure CLI closes in `finally`.
  - Keep `__del__` as fallback only (or remove if safe).
- **Files**:
  - `crawler_to_md/database_manager.py`
  - `crawler_to_md/cli.py`
  - `tests/test_cli.py`
  - `tests/test_database_manager.py`
- **Validation**:
  - `pytest tests/test_cli.py tests/test_database_manager.py`
- **Effort/Risk**: M / Med

### Task 2.6 - Logging setup idempotency
- **Items covered**: Improvement #18.
- **Changes**:
  - Guard against duplicate handlers.
  - Keep tqdm-compatible behavior.
- **Files**:
  - `crawler_to_md/log_setup.py`
  - `tests/` (add focused test if logger init is unit-testable)
- **Validation**:
  - `pytest`
- **Effort/Risk**: S / Low

---

## Phase 3 - Memory and Streaming Exports

### Task 3.1 - Add page iterator API in database manager
- **Items covered**: Improvement #11 (foundation).
- **Changes**:
  - Add `iter_pages(fetch_size=...)` cursor-based generator.
- **Files**:
  - `crawler_to_md/database_manager.py`
  - `tests/test_database_manager.py`
- **Validation**:
  - `pytest tests/test_database_manager.py`
- **Effort/Risk**: M / Low

### Task 3.2 - Stream compiled markdown export
- **Items covered**: Improvements #11 and #12.
- **Changes**:
  - Avoid building one giant string in memory.
  - Write chunks/page sections directly to output file.
- **Files**:
  - `crawler_to_md/export_manager.py`
  - `tests/test_export_manager.py`
- **Validation**:
  - `pytest tests/test_export_manager.py`
- **Effort/Risk**: L / Med

### Task 3.3 - Stream JSON export (optional after markdown)
- **Items covered**: Improvement #11 and #15.
- **Changes**:
  - Option A: keep full list for compatibility.
  - Option B: stream JSON array with controlled separators.
  - Add optional compact mode behavior tied to minify/profile.
- **Files**:
  - `crawler_to_md/export_manager.py`
  - `crawler_to_md/cli.py`
  - `tests/test_export_manager.py`
  - `tests/test_cli.py`
- **Validation**:
  - `pytest tests/test_export_manager.py tests/test_cli.py`
- **Effort/Risk**: M / Med

---

## Phase 4 - Network Behavior and Reliability

### Task 4.1 - Requests adapter tuning and retries
- **Items covered**: Improvement #10.
- **Changes**:
  - Configure session adapters (pool sizes).
  - Add conservative retry policy for transient errors.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_scraper.py -k timeout or proxy or request`
- **Effort/Risk**: M / Med

### Task 4.2 - Retry policy guardrails for failed pages
- **Items covered**: Improvement #8.
- **Changes**:
  - Introduce retry cap and/or metadata retry counter.
  - Prevent endless requeue loops.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `crawler_to_md/database_manager.py` (if schema fields added)
  - `tests/test_scraper.py`
  - `tests/test_database_manager.py`
- **Validation**:
  - `pytest tests/test_scraper.py -k retry`
- **Effort/Risk**: L / Med

### Task 4.3 - Improve rate limiting algorithm
- **Items covered**: Improvement #9.
- **Changes**:
  - Replace coarse minute-window counter with token bucket.
  - Preserve `--rate-limit` and `--delay` semantics.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest tests/test_scraper.py -k rate or delay`
- **Effort/Risk**: M / Med

---

## Phase 5 - Architecture and Extensibility

### Task 5.1 - Refactor scraper loop into cohesive units
- **Items covered**: Improvement #19.
- **Changes**:
  - Extract methods/classes for frontier, fetch, parse, persist.
  - Keep external CLI behavior stable.
- **Files**:
  - `crawler_to_md/scraper.py`
  - possible new modules under `crawler_to_md/`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest`
- **Effort/Risk**: XL / High

### Task 5.2 - Converter abstraction
- **Items covered**: Improvement #2 (full), #24.
- **Changes**:
  - Introduce converter interface and adapter for MarkItDown.
  - Prepare for alternative converter backends.
- **Files**:
  - new module(s) in `crawler_to_md/`
  - `crawler_to_md/scraper.py`
  - `tests/test_scraper.py`
- **Validation**:
  - `pytest`
- **Effort/Risk**: L / High

### Task 5.3 - Structured error taxonomy
- **Items covered**: Improvement #20.
- **Changes**:
  - Define error categories/codes for persistent metadata.
  - Tighten exception boundaries.
- **Files**:
  - `crawler_to_md/scraper.py`
  - `crawler_to_md/export_manager.py` (if metadata expectations change)
  - `tests/test_scraper.py`
  - `tests/test_export_manager.py`
- **Validation**:
  - `pytest`
- **Effort/Risk**: M / Med

---

## CI / Release Follow-Ups

### Task C1 - Split docker validation vs publish flow
- **Items covered**: Improvement #22.
- **Changes**:
  - PR: validate build only (single arch).
  - Release/main: multi-arch + push + sign.
- **Files**:
  - `.github/workflows/build-and-publish.yaml`
- **Validation**:
  - Workflow dry-run logic review.
- **Effort/Risk**: M / Med

### Task C2 - Package release hardening
- **Items covered**: Improvement #21.
- **Changes**:
  - Add `twine check dist/*` before upload.
  - Optional: migrate to trusted publishing.
- **Files**:
  - `.github/workflows/publish-to-pypi.yaml`
- **Validation**:
  - Release workflow test on tag sandbox.
- **Effort/Risk**: S-M / Med

### Task C3 - Dependency audit and optional extras
- **Items covered**: Improvement #24.
- **Changes**:
  - Audit actual imports vs dependencies.
  - Move optional deps to extras.
- **Files**:
  - `pyproject.toml`
  - `README.md`
- **Validation**:
  - `pip install -e .`
  - `pytest`
  - `python -m build`
- **Effort/Risk**: M / Med

---

## Suggested PR Batching Strategy

1. **PR-1 (Fast safety + easy perf):** Tasks 0.2, 1.1, 1.3, 1.5
2. **PR-2 (DB and crawl throughput):** Tasks 1.2, 2.1
3. **PR-3 (Minify/export optimization):** Tasks 1.4, 3.1, 3.2
4. **PR-4 (URL correctness + lifecycle):** Tasks 2.4, 2.5, 2.6
5. **PR-5 (Network reliability):** Tasks 4.1, 4.2, 4.3
6. **PR-6 (Architecture):** Tasks 5.1, 5.2, 5.3
7. **PR-7 (Workflow/package hardening):** Tasks C1, C2, C3

---

## Definition of Done (per PR)

- Lint passes: `ruff check .`
- Targeted tests for touched modules pass.
- Full test suite passes for cross-cutting changes: `pytest`
- If packaging/workflows changed: `python -m build` and `twine check dist/*`
- Benchmark delta captured when performance-related behavior changed.

---

## Earliest Measurable Wins

If only three tasks are done first, prioritize:
1. **Task 1.2** (bulk inserts),
2. **Task 2.1** (paged unvisited reads),
3. **Task 1.4** (minify-aware export shortcuts).

This combination is expected to reduce runtime and memory pressure for the common
"single URL -> many links -> one minified markdown" path with minimal behavior drift.
