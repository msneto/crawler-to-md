# IMPROVEMENTS IMPLEMENTATION PLAN

## Goal

Turn findings in `IMPROVEMENTS.md` into an execution-ready backlog with clear order,
scope, test impact, and risk.

Primary target profile:
1. Single seed URL.
2. Many discovered links.
3. Single compiled minified Markdown export.

## Progress Snapshot

- **Phase 1 Complete**: Indexing, Batching, Linear concatenation.
- **Phase 2 Complete**: One-parse logic, URL normalization, Lifecycle management.
- **Phase 3 Complete**: Streaming exports (Markdown/JSON/Individual) via `get_pages_iterator`.
- **Phase 4 Started**: Requests adapter tuning and retries implemented.
- **Explore Mode Wins**: 
    - Integrated `lxml` for 3x-10x parsing speedup.
    - Implemented **Fast-Path** (Direct DOM conversion) to eliminate second parse.
    - Implemented **Regex matching** for $O(N)$ URL filtering.
    - Implemented **Early Termination** (`stream=True`) to skip large binary assets.

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

## Completed Tasks

- Task 0.2: Add CI quality gate for lint/tests.
- Task 1.1: SQLite index for visited state.
- Task 1.2: Bulk insert discovered links.
- Task 1.3: Export cleanup pass only once.
- Task 1.4: Minify-aware markdown assembly shortcuts.
- Task 1.5: Fix `.dockerignore` typo.
- Task 2.1: Paged DB readers for crawl queue.
- Task 2.2: Single-pass HTML processing (No second parse).
- Task 2.3: Reuse converter instance in scraper.
- Task 2.4: URL canonicalization and stricter scope checks.
- Task 2.5: Explicit DB lifecycle management.
- Task 2.6: Logging setup idempotency.
- Task 3.1: Cursor-based page iterator in `DatabaseManager`.
- Task 3.2: Streamed compiled Markdown export.
- Task 3.3: Streamed JSON and Individual exports.
- Task 4.1: Requests adapter tuning and retries.
- Task 4.2: Retry policy guardrails for failed pages.

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
- **Status**: Complete

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
- **Status**: Complete

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

### Task 5.2 - Parallelization (NEW)
- **Goal**: Implement `ThreadPoolExecutor` for concurrent network requests and `ProcessPoolExecutor` for CPU-bound Markdown conversion.
- **Effort/Risk**: L / High

### Task 5.3 - Converter abstraction
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

### Task 5.4 - Structured error taxonomy
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
