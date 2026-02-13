import pytest

from crawler_to_md import utils


def test_randomstring_to_filename():
    assert utils.randomstring_to_filename("Hello World!") == "Hello_World"


def test_url_to_filename():
    result = utils.url_to_filename("https://example.com/path/index.html")
    assert result == "example_com_path_index_html"


def test_url_dirname():
    assert (
        utils.url_dirname("https://example.com/path/page")
        == "https://example.com/path/"
    )
    assert (
        utils.url_dirname("https://example.com/path/page/")
        == "https://example.com/path/page/"
    )


def test_deduplicate_list():
    assert utils.deduplicate_list([1, 2, 2, 3, 1]) == [1, 2, 3]


def test_randomstring_special_chars():
    assert utils.randomstring_to_filename("a!@ b$c#") == "a_bc"


def test_url_to_filename_invalid():
    with pytest.raises(ValueError):
        utils.url_to_filename(123)


def test_normalize_url_strips_fragment_and_lowercases_host_scheme():
    result = utils.normalize_url("HTTPS://Example.COM/path#section")
    assert result == "https://example.com/path"


def test_normalize_url_preserves_query():
    result = utils.normalize_url("https://example.com/path?a=1&b=2")
    assert result == "https://example.com/path?a=1&b=2"


def test_normalize_url_invalid():
    with pytest.raises(ValueError):
        utils.normalize_url("/relative/path")


def test_is_supported_scheme():
    assert utils.is_supported_scheme("https://example.com") is True
    assert utils.is_supported_scheme("http://example.com") is True
    assert utils.is_supported_scheme("mailto:me@example.com") is False
    assert utils.is_supported_scheme("javascript:void(0)") is False


def test_is_url_in_scope_strict_host_and_path():
    assert (
        utils.is_url_in_scope(
            "https://example.com/docs/page", "https://example.com/docs"
        )
        is True
    )
    assert (
        utils.is_url_in_scope(
            "https://example.come/docs/page", "https://example.com/docs"
        )
        is False
    )
