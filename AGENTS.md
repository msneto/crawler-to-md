# AGENTS.md

## 0) Scope

For coding agents in `crawler-to-md`.
Primary goals -> run correct commands, preserve repo behavior, touch matching tests.

Includes:

- build/lint/test commands (incl. single test)
- repo conventions + invariants
- CI/release context
- Cursor/Copilot rule-file status

## 1) Repo Map

Code (`crawler_to_md/`):

- `cli.py` -> CLI args + orchestration
- `scraper.py` -> crawl loop, HTTP, filters, markdown conversion
- `database_manager.py` -> SQLite schema + persistence API
- `export_manager.py` -> combined markdown/json + per-page markdown export
- `utils.py` -> URL/path/filename helpers
- `log_setup.py` -> logging setup (tqdm-friendly)

Tests: `tests/**`

Key config/automation:

- `pyproject.toml`
- `Dockerfile`
- `.github/workflows/build-and-publish.yaml`
- `.github/workflows/publish-to-pypi.yaml`

## 2) Environment

- Python -> `>=3.10`
- Packaging -> `setuptools` + `setuptools_scm`
- Lint/import sorting -> `ruff` (`E,F,W,I`)
- Tests -> `pytest`

Local setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e .
pip install pytest ruff build twine
```

Note -> `pytest`/`ruff` configured but not exposed as dev extras.

## 3) Canonical Commands

Run CLI:

```bash
crawler-to-md --url https://example.com
python -m crawler_to_md.cli --url https://example.com
```

Lint:

```bash
ruff check .
ruff check . --fix
```

Tests:

```bash
pytest
pytest tests/test_utils.py
pytest tests/test_utils.py::test_url_to_filename
pytest -k proxy
pytest -x
pytest -v
```

Build/package:

```bash
python -m build
twine check dist/*
```

Docker (local):

```bash
docker build -t crawler-to-md .
docker run --rm -v "$(pwd)/output:/app/output" crawler-to-md --url https://example.com
```

## 4) Conventions + Invariants (Do Not Drift)

Formatting/imports:

- line length -> `88`
- imports -> Ruff `I` compliant
- after import/format changes -> run `ruff check . --fix`

Naming/ownership:

- naming -> `snake_case` (modules/functions/vars), `PascalCase` (classes)
- keep logic boundaries:
  - DB logic -> `DatabaseManager`
  - export logic -> `ExportManager`
  - crawl/scrape logic -> `Scraper`

Error handling:

- invalid caller input -> `ValueError`
- CLI user-facing arg/config errors -> `parser.error(...)`
- network/proxy boundary failures -> handle `requests` exceptions + log context
- never silently swallow failures

File/data:

- create output/cache dirs before writes
- text output encoding -> UTF-8
- preserve DB semantics in `database_manager.py`:
  - `pages(url, content, metadata)`
  - `links(url, visited)`
- keep idempotent insert behavior unless intentionally changing semantics

Scraping behavior:

- preserve URL include/exclude semantics
- preserve CSS include/exclude semantics before markdown conversion
- skip non-200 or non-HTML responses
- preserve rate-limit + delay behavior

## 5) Test Mapping + Done Criteria

Change -> tests to update/run:

- CLI flags/options -> `tests/test_cli.py`
- scraping/link/proxy/filter behavior -> `tests/test_scraper.py`
- DB behavior -> `tests/test_database_manager.py`
- markdown/json export behavior -> `tests/test_export_manager.py`
- helpers/utilities -> `tests/test_utils.py`

Before finishing non-trivial work:

1. `ruff check .`
2. targeted pytest (single test or file)
3. full `pytest` for cross-cutting changes
4. `python -m build` if packaging/release behavior changed

## 6) CI/Release Reality

Workflows present:

- Docker build/publish/sign
- PyPI publish on release

No dedicated workflow here runs lint/tests on every PR by default -> run checks locally.
