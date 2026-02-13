import logging

import pytest

from crawler_to_md import log_setup


def _managed_handlers(root_logger):
    return [
        handler
        for handler in root_logger.handlers
        if getattr(handler, log_setup._MANAGED_TQDM_HANDLER_ATTR, False)
    ]


@pytest.fixture
def restore_logging_state():
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    original_logger = log_setup.logger
    original_coloredlogs_installed = log_setup._coloredlogs_installed

    yield

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    for handler in original_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(original_level)
    log_setup.logger = original_logger
    log_setup._coloredlogs_installed = original_coloredlogs_installed


def test_setup_logging_adds_single_managed_handler(restore_logging_state, monkeypatch):
    root_logger = logging.getLogger()
    for handler in _managed_handlers(root_logger):
        root_logger.removeHandler(handler)

    install_calls = {"count": 0}

    def fake_install(*args, **kwargs):
        install_calls["count"] += 1

    monkeypatch.setattr(log_setup.coloredlogs, "install", fake_install)
    log_setup._coloredlogs_installed = False

    log_setup.setup_logging("INFO")
    log_setup.setup_logging("INFO")
    log_setup.setup_logging("INFO")

    assert len(_managed_handlers(root_logger)) == 1
    assert install_calls["count"] == 1


def test_setup_logging_updates_level_without_reinstall(
    restore_logging_state, monkeypatch
):
    install_calls = {"count": 0}

    def fake_install(*args, **kwargs):
        install_calls["count"] += 1

    monkeypatch.setattr(log_setup.coloredlogs, "install", fake_install)
    log_setup._coloredlogs_installed = False

    log_setup.setup_logging("WARNING")
    log_setup.setup_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG
    assert install_calls["count"] == 1


def test_setup_logging_preserves_unrelated_handlers(restore_logging_state, monkeypatch):
    root_logger = logging.getLogger()
    dummy_handler = logging.StreamHandler()
    root_logger.addHandler(dummy_handler)

    monkeypatch.setattr(log_setup.coloredlogs, "install", lambda *a, **k: None)
    log_setup._coloredlogs_installed = False

    log_setup.setup_logging("INFO")
    log_setup.setup_logging("INFO")

    assert dummy_handler in root_logger.handlers
    assert root_logger.handlers.count(dummy_handler) == 1
    assert len(_managed_handlers(root_logger)) == 1


def test_tqdm_handler_emits_with_tqdm_write(restore_logging_state, monkeypatch):
    root_logger = logging.getLogger()
    for handler in _managed_handlers(root_logger):
        root_logger.removeHandler(handler)

    write_calls = []

    def fake_write(message, end="\n"):
        write_calls.append((message, end))

    monkeypatch.setattr(log_setup.coloredlogs, "install", lambda *a, **k: None)
    monkeypatch.setattr(log_setup.tqdm, "write", fake_write)
    log_setup._coloredlogs_installed = False

    log_setup.setup_logging("INFO")
    managed_handler = _managed_handlers(root_logger)[0]

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=123,
        msg="hello logging",
        args=(),
        exc_info=None,
    )
    managed_handler.emit(record)

    assert len(write_calls) == 1
    assert "hello logging" in write_calls[0][0]
    assert write_calls[0][1] == ""
