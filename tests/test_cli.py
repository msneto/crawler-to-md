import os
import sqlite3
import sys

import pytest

from crawler_to_md import cli, utils
from crawler_to_md.database_manager import DatabaseManager
from crawler_to_md.export_manager import ExportManager
from crawler_to_md.scraper import Scraper


def _run_cli(monkeypatch, tmp_path, extra_args):
    calls = {"md": False, "json": False}

    def fake_export_markdown(self, path):
        calls["md"] = True

    def fake_export_json(self, path):
        calls["json"] = True

    monkeypatch.setattr(ExportManager, "export_to_markdown", fake_export_markdown)
    monkeypatch.setattr(ExportManager, "export_to_json", fake_export_json)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
    ] + extra_args

    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    return calls


def test_cli_default_exports(monkeypatch, tmp_path):
    calls = _run_cli(monkeypatch, tmp_path, [])
    assert calls["md"] is True
    assert calls["json"] is True


def test_cli_disable_exports(monkeypatch, tmp_path):
    calls = _run_cli(monkeypatch, tmp_path, ["--no-markdown", "--no-json"])
    assert calls["md"] is False
    assert calls["json"] is False


def test_cli_proxy_option(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Fake initializer to capture proxy argument.
        """
        captured["proxy"] = kwargs.get("proxy")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--proxy",
        "http://proxy:8080",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("proxy") == "http://proxy:8080"


def test_cli_proxy_short_option(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Fake initializer to capture proxy argument.
        """
        captured["proxy"] = kwargs.get("proxy")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "-p",
        "http://proxy:8080",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("proxy") == "http://proxy:8080"


def test_cli_socks_proxy(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Fake initializer to capture proxy argument.
        """
        captured["proxy"] = kwargs.get("proxy")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--proxy",
        "socks5://localhost:9050",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("proxy") == "socks5://localhost:9050"


def test_cli_proxy_error(monkeypatch, tmp_path):
    def fake_init(*a, **k):
        raise ValueError("Proxy unreachable")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--proxy",
        "http://proxy:8080",
    ]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit):
        cli.main()


def test_cli_include_exclude_options(monkeypatch, tmp_path):
    """
    Ensure CLI passes include and exclude options to the scraper.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        tmp_path (pathlib.Path): Temporary path for tests.
    """
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Fake initializer to capture include/exclude arguments.
        """
        captured["include_filters"] = kwargs.get("include_filters")
        captured["exclude_filters"] = kwargs.get("exclude_filters")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--include",
        "p",
        "--exclude",
        ".remove",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("include_filters") == ["p"]
    assert captured.get("exclude_filters") == [".remove"]


def test_cli_include_exclude_short_options(monkeypatch, tmp_path):
    """
    Ensure short CLI options map to include and exclude selectors.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        tmp_path (pathlib.Path): Temporary path for tests.
    """
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Capture include and exclude selectors from short options.
        """
        captured["include_filters"] = kwargs.get("include_filters")
        captured["exclude_filters"] = kwargs.get("exclude_filters")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "-i",
        "#keep",
        "-x",
        "span",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("include_filters") == ["#keep"]
    assert captured.get("exclude_filters") == ["span"]


def test_cli_include_url_option(monkeypatch, tmp_path):
    """
    Ensure CLI passes include URL filters to the scraper.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        tmp_path (pathlib.Path): Temporary path for tests.
    """
    captured = {}

    def fake_init(self, *args, **kwargs):
        """
        Capture include URL patterns argument.
        """
        captured["include_url_patterns"] = kwargs.get("include_url_patterns")

    monkeypatch.setattr(Scraper, "__init__", fake_init)

    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--include-url",
        "/blog",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("include_url_patterns") == ["/blog"]


def test_cli_overwrite_cache(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, db_path):
        captured["exists"] = os.path.exists(db_path)
        self.conn = sqlite3.connect(":memory:")

    monkeypatch.setattr(DatabaseManager, "__init__", fake_init)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    db_name = utils.url_to_filename("http://example.com") + ".sqlite"
    db_path = cache_folder / db_name
    cache_folder.mkdir()
    db_path.write_text("dummy")

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--overwrite-cache",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("exists") is False


def test_cli_overwrite_cache_short_option(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, db_path):
        captured["exists"] = os.path.exists(db_path)
        self.conn = sqlite3.connect(":memory:")

    monkeypatch.setattr(DatabaseManager, "__init__", fake_init)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    db_name = utils.url_to_filename("http://example.com") + ".sqlite"
    db_path = cache_folder / db_name
    cache_folder.mkdir()
    db_path.write_text("dummy")

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "-w",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("exists") is False


def test_cli_timeout_option_passed_to_scraper(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, *args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--timeout",
        "2.5",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("timeout") == 2.5


def test_cli_timeout_default_passed_to_scraper(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, *args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(Scraper, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()
    assert captured.get("timeout") == 10


def test_cli_help_mentions_timeout(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--help"])

    with pytest.raises(SystemExit):
        cli.main()

    help_output = capsys.readouterr().out
    assert "--timeout" in help_output


def test_cli_help_mentions_simple_selector_forms(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--help"])

    with pytest.raises(SystemExit):
        cli.main()

    help_output = capsys.readouterr().out
    assert "#id, .class, tag only" in help_output


def test_cli_minify_option_passed_to_export_manager(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, db_manager, title=None, minify=False):
        captured["minify"] = minify
        self.db_manager = db_manager
        self.title = title
        self.minify = minify

    monkeypatch.setattr(ExportManager, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "--minify",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()

    assert captured.get("minify") is True


def test_cli_minify_short_option_passed_to_export_manager(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, db_manager, title=None, minify=False):
        captured["minify"] = minify
        self.db_manager = db_manager
        self.title = title
        self.minify = minify

    monkeypatch.setattr(ExportManager, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
        "-m",
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()

    assert captured.get("minify") is True


def test_cli_help_mentions_minify(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--help"])

    with pytest.raises(SystemExit):
        cli.main()

    help_output = capsys.readouterr().out
    assert "--minify" in help_output
    assert "backup" in help_output
    assert "rendering" in help_output


def test_cli_minify_default_false(monkeypatch, tmp_path):
    captured = {}

    def fake_init(self, db_manager, title=None, minify=False):
        captured["minify"] = minify
        self.db_manager = db_manager
        self.title = title
        self.minify = minify

    monkeypatch.setattr(ExportManager, "__init__", fake_init)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    cache_folder = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(cache_folder),
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()

    assert captured.get("minify") is False


def test_cli_minify_with_no_markdown_has_no_markdown_side_effects(
    monkeypatch, tmp_path
):
    calls = _run_cli(monkeypatch, tmp_path, ["--minify", "--no-markdown"])
    assert calls["md"] is False
    assert calls["json"] is True


def test_cli_output_dir_alias(monkeypatch, tmp_path):
    captured = {}

    def fake_export_markdown(self, path):
        captured["markdown_path"] = path

    monkeypatch.setattr(ExportManager, "export_to_markdown", fake_export_markdown)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)

    output_dir = tmp_path / "alias-output"
    cache_dir = tmp_path / "cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-dir",
        str(output_dir),
        "--cache-dir",
        str(cache_dir),
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()

    assert str(output_dir) in captured["markdown_path"]


def test_cli_cache_dir_alias(monkeypatch, tmp_path):
    captured = {}

    def fake_db_init(self, db_path):
        captured["db_path"] = db_path
        self.conn = sqlite3.connect(":memory:")

    monkeypatch.setattr(DatabaseManager, "__init__", fake_db_init)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)

    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "alias-cache"
    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(output_dir),
        "--cache-dir",
        str(cache_dir),
    ]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()

    assert captured["db_path"].startswith(str(cache_dir))


def test_cli_help_mentions_output_and_cache_dir_aliases(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--help"])

    with pytest.raises(SystemExit):
        cli.main()

    help_output = capsys.readouterr().out
    assert "--output-dir" in help_output
    assert "--cache-dir" in help_output


def test_cli_closes_database_on_success(monkeypatch, tmp_path):
    calls = {"close": 0}
    original_close = DatabaseManager.close

    def tracked_close(self):
        if not getattr(self, "_closed", False):
            calls["close"] += 1
        return original_close(self)

    monkeypatch.setattr(DatabaseManager, "close", tracked_close)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(tmp_path / "cache"),
    ]
    monkeypatch.setattr(sys, "argv", args)

    cli.main()

    assert calls["close"] == 1


def test_cli_closes_database_when_scraper_init_fails(monkeypatch, tmp_path):
    calls = {"close": 0}
    original_close = DatabaseManager.close

    def tracked_close(self):
        if not getattr(self, "_closed", False):
            calls["close"] += 1
        return original_close(self)

    def fake_scraper_init(*args, **kwargs):
        raise ValueError("invalid scraper config")

    monkeypatch.setattr(DatabaseManager, "close", tracked_close)
    monkeypatch.setattr(Scraper, "__init__", fake_scraper_init)

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(tmp_path / "cache"),
    ]
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(SystemExit):
        cli.main()

    assert calls["close"] == 1


def test_cli_closes_database_when_scraping_raises(monkeypatch, tmp_path):
    calls = {"close": 0}
    original_close = DatabaseManager.close

    def tracked_close(self):
        if not getattr(self, "_closed", False):
            calls["close"] += 1
        return original_close(self)

    def fake_start_scraping(*args, **kwargs):
        raise RuntimeError("crawl failed")

    monkeypatch.setattr(DatabaseManager, "close", tracked_close)
    monkeypatch.setattr(Scraper, "start_scraping", fake_start_scraping)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", lambda *a, **k: None)

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(tmp_path / "cache"),
    ]
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(RuntimeError):
        cli.main()

    assert calls["close"] == 1


def test_cli_closes_database_when_export_raises(monkeypatch, tmp_path):
    calls = {"close": 0}
    original_close = DatabaseManager.close

    def tracked_close(self):
        if not getattr(self, "_closed", False):
            calls["close"] += 1
        return original_close(self)

    def fake_export_json(*args, **kwargs):
        raise RuntimeError("export failed")

    monkeypatch.setattr(DatabaseManager, "close", tracked_close)
    monkeypatch.setattr(Scraper, "start_scraping", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_markdown", lambda *a, **k: None)
    monkeypatch.setattr(ExportManager, "export_to_json", fake_export_json)

    args = [
        "prog",
        "--url",
        "http://example.com",
        "--output-folder",
        str(tmp_path),
        "--cache-folder",
        str(tmp_path / "cache"),
    ]
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(RuntimeError):
        cli.main()

    assert calls["close"] == 1
