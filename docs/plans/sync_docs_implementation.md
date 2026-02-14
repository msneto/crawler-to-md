# Detailed Plan: Documentation Synchronization

## Goal
Synchronize `IMPROVEMENTS.md` and `IMPROVEMENTS_IMPLEMENTATION_PLAN.md` with the current codebase state, marking already implemented features as completed.

## Steps

### 1. Update Improvement #10 in `IMPROVEMENTS.md`
- **Affected Files**: `IMPROVEMENTS.md`
- **Description**: Mark "Requests session tuning" as implemented.
- **Details**: Mention `HTTPAdapter`, connection pooling (size 10), and `urllib3.Retry` for specific status codes.
- **Risks**: Misrepresenting technical constants.
- **Mitigation**: Re-read `crawler_to_md/scraper.py` constants before writing.
- **Tests**: None (Documentation only).

### 2. Update Improvement #15 in `IMPROVEMENTS.md`
- **Affected Files**: `IMPROVEMENTS.md`
- **Description**: Mark "JSON pretty-print" as implemented.
- **Details**: Note that it auto-compacts when `--minify` is enabled.
- **Risks**: Inaccurate trigger logic description.
- **Mitigation**: Verify `ExportManager.export_to_json` logic.
- **Tests**: None (Documentation only).

### 3. Update Improvement #17 in `IMPROVEMENTS.md`
- **Affected Files**: `IMPROVEMENTS.md`
- **Description**: Mark "Database connection cleanup" as implemented.
- **Details**: Note the explicit `close()` calls in `cli.py` and `DatabaseManager`.
- **Risks**: Omitting the deterministic nature of the fix.
- **Mitigation**: Check `cli.py` finally block.
- **Tests**: None (Documentation only).

### 4. Sync `IMPROVEMENTS_IMPLEMENTATION_PLAN.md`
- **Affected Files**: `IMPROVEMENTS_IMPLEMENTATION_PLAN.md`
- **Description**: Update roadmap and snapshot.
- **Details**: Move Task 4.1 to "Completed Tasks" and update "Progress Snapshot" to show Phase 4 has started.
- **Risks**: Accidental roadmap deletion.
- **Mitigation**: Use precise regex or multi-line context in replacements.
- **Tests**: `pytest` to ensure no side effects on code.
