# Plan: JSON Pretty-Print Configuration (Improvement #15)

## Problem Statement
The `ExportManager` hardcodes `indent=4` for all JSON exports. This is inefficient for large crawls or machine-ingestion tasks where compact file sizes are preferred.

## Selected Solution: Alternative B
Automatically link JSON minification to the existing `--minify` CLI flag. When `--minify` is active, the JSON output will be compacted by removing indentation and extra separators.

## Actionable Steps

### Step 1: Update `ExportManager.export_to_json`
- **Files:** `crawler_to_md/export_manager.py`
- **Description:** Implement conditional parameters for `json.dump`.
- **Logic:**
    - If `self.minify` is `True`: `indent=None`, `separators=(',', ':')`.
    - Else: `indent=4`, `separators=None` (defaults).
- **Points of Attention:** Ensure `ensure_ascii=False` is preserved. 
- **Risks:** Memory usage. Materializing `data_to_export` in RAM is still a potential bottleneck for extremely large crawls.
- **Mitigation:** Document this as a limitation for now; the "quick win" focus is on output size.
- **Tests:** Verify indentation and separator logic.

### Step 2: Verify CLI Integration
- **Files:** `crawler_to_md/cli.py`
- **Description:** Ensure `ExportManager` is correctly receiving the `minify` argument from the CLI.
- **Points of Attention:** Check instantiation at line 258.
- **Risks:** None.

### Step 3: Implement JSON Format Tests
- **Files:** `tests/test_export_manager.py`
- **Description:** Add tests for both formatting modes.
- **Tests:**
    - `test_export_to_json_pretty`: Verify presence of `
` and spaces (e.g., `": "`).
    - `test_export_to_json_compact`: Verify absence of `
` and spaces between keys/values (e.g., `":"`).
    - Verify data integrity by comparing `json.loads(output)` with original data.
- **Risks:** Flaky string matching. **Mitigation:** Use regex or simple substring checks for non-whitespace characters.
