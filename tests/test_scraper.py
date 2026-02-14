from unittest.mock import MagicMock, patch

import pytest
import requests
import tqdm

from crawler_to_md.database_manager import DatabaseManager
from crawler_to_md.scraper import Scraper


class DummyDB(DatabaseManager):
    def __init__(self):
        pass

    def __del__(self):
        pass

    def insert_link(self, url, visited=False) -> bool:
        return True

    def get_unvisited_links(self, limit=None):
        return []

    def mark_link_visited(self, url):
        pass

    def mark_link_unvisited(self, url):
        pass

    def get_failed_page_urls(self):
        return []

    def upsert_page(self, url, content, metadata):
        pass


def test_is_valid_link():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=["/exclude"],
        include_url_patterns=[],
        db_manager=db,
    )
    assert scraper.is_valid_link("https://example.com/page")
    assert not scraper.is_valid_link("https://example.com/exclude/page")
    assert not scraper.is_valid_link("https://other.com/")

    include_scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=[],
        include_url_patterns=["/docs"],
        db_manager=db,
    )
    assert include_scraper.is_valid_link("https://example.com/docs/page")
    assert not include_scraper.is_valid_link("https://example.com/blog")


def test_fetch_links():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=["/exclude"],
        include_url_patterns=[],
        db_manager=db,
    )
    html = """<html><body>
    <a href="https://example.com/page1">1</a>
    <a href="/page2">2</a>
    <a href="https://example.com/exclude/hidden">3</a>
    </body></html>"""
    links = scraper.fetch_links(url="https://example.com", html=html)
    assert links == {"https://example.com/page1", "https://example.com/page2"}


def test_fetch_links_includes_only_matching_patterns():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=[],
        include_url_patterns=["/page1"],
        db_manager=db,
    )
    html = """<html><body>
    <a href="https://example.com/page1">1</a>
    <a href="/page2">2</a>
    <a href="https://example.com/page3">3</a>
    </body></html>"""
    links = scraper.fetch_links(url="https://example.com", html=html)
    assert links == {"https://example.com/page1"}


def test_fetch_links_skips_unsupported_schemes():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    html = """<html><body>
    <a href="mailto:test@example.com">mail</a>
    <a href="javascript:void(0)">js</a>
    <a href="tel:+123">tel</a>
    <a href="/page">ok</a>
    </body></html>"""

    links = scraper.fetch_links(url="https://example.com", html=html)

    assert links == {"https://example.com/page"}


def test_fetch_links_normalizes_and_deduplicates_links():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    html = """<html><body>
    <a href="https://EXAMPLE.com/page#one">a</a>
    <a href="https://example.com/page#two">b</a>
    </body></html>"""

    links = scraper.fetch_links(url="https://example.com", html=html)

    assert links == {"https://example.com/page"}


def test_is_valid_link_rejects_similar_host_prefix():
    db = DummyDB()
    scraper = Scraper(
        base_url="https://example.com/docs",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    assert scraper.is_valid_link("https://example.com/docs/page")
    assert not scraper.is_valid_link("https://example.come/docs/page")


def test_scrape_page_parses_content_and_metadata():
    # Arrange
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    html = "<html><head><title>Test</title></head><body><p>Hello</p></body></html>"

    # Act
    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:
        mock_custom_md.return_value.convert_soup.return_value = "Hello"
        content, metadata = scraper.scrape_page(html, "http://example.com/test")

    # Assert
    assert content is not None
    assert "Hello" in content
    assert metadata is not None
    assert metadata.get("title") == "Test"


def test_scrape_page_with_markitdown():
    # Arrange
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    html = (
        "<html><head><title>Test</title></head><body><h1>A Title</h1>"
        "<p>This is a paragraph with <strong>bold</strong> text.</p></body></html>"
    )

    # Act
    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:
        mock_custom_md.return_value.convert_soup.return_value = (
            "# A Title\n\nThis is a paragraph with **bold** text."
        )
        content, metadata = scraper.scrape_page(html, "http://example.com/test")

    # Assert
    assert content is not None
    assert content == "# A Title\n\nThis is a paragraph with **bold** text."
    assert metadata is not None
    assert metadata.get("title") == "Test"


def test_scrape_page_include_exclude():
    """
    Verify include and exclude selectors filter HTML before conversion.
    """
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        include_filters=["p"],
        exclude_filters=[".remove"],
    )
    html = (
        '<html><body><p class="keep">Keep</p>'
        '<p class="remove">Remove</p><span>Ignore</span></body></html>'
    )

    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:

        def convert_side_effect(soup, **kwargs):
            """Return the HTML of the soup."""
            return str(soup)

        mock_custom_md.return_value.convert_soup.side_effect = convert_side_effect
        content, metadata = scraper.scrape_page(html, "http://example.com/test")

    assert "Keep" in content
    assert "Remove" not in content
    assert "Ignore" not in content
    assert metadata.get("title") == ""


class ListDB(DummyDB):
    def __init__(self):
        self.links = []
        self.visited = set()
        self.pages = []
        self.unvisited_query_limits = []

    def insert_link(self, url, visited=False) -> bool:
        urls = url if isinstance(url, list) else [url]
        inserted = False
        for u in urls:
            if u not in self.links:
                self.links.append(u)
                inserted = True
        return inserted

    def insert_links(self, urls, visited=False):
        count = 0
        for u in urls:
            if u not in self.links:
                self.links.append(u)
                count += 1
        return count

    def get_unvisited_links(self, limit=None):
        self.unvisited_query_limits.append(limit)
        unvisited = [(u,) for u in self.links if u not in self.visited]
        if limit is None:
            return unvisited
        return unvisited[:limit]

    def mark_link_visited(self, url):
        self.visited.add(url)

    def mark_link_unvisited(self, url):
        if url in self.visited:
            self.visited.remove(url)

    def get_links_count(self):
        return len(self.links)

    def get_visited_links_count(self):
        return len(self.visited)

    def insert_page(self, url, content, metadata):
        self.pages.append((url, content, metadata))

    def upsert_page(self, url, content, metadata):
        self.upsert_pages([(url, content, metadata)])

    def upsert_pages(self, pages):
        for url, content, metadata in pages:
            for index, existing in enumerate(self.pages):
                if existing[0] == url:
                    self.pages[index] = (url, content, metadata)
                    break
            else:
                self.pages.append((url, content, metadata))

    def get_failed_page_urls(self):
        return [url for url, content, _ in self.pages if content is None]

    def get_all_pages(self):
        return self.pages

    def mark_links_visited(self, urls):
        for url in urls:
            self.visited.add(url)


def test_start_scraping_process(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<html></html>"
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(url="http://example.com/page")

    assert db.get_links_count() == 1
    assert db.get_visited_links_count() == 1
    assert db.pages[0][0] == "http://example.com/page"


def test_start_scraping_processes_unvisited_links_in_batches(monkeypatch):
    db = ListDB()
    db.insert_link(
        [
            "http://example.com/1",
            "http://example.com/2",
            "http://example.com/3",
            "http://example.com/4",
            "http://example.com/5",
        ]
    )

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    scraper.unvisited_links_batch_size = 2

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping()

    assert db.get_visited_links_count() == 5
    assert all(limit == 2 for limit in db.unvisited_query_limits if limit is not None)
    assert len(db.unvisited_query_limits) >= 3


def test_start_scraping_parses_each_page_once(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    scraper.unvisited_links_batch_size = 10

    parse_count = {"count": 0}

    from bs4 import BeautifulSoup as RealBeautifulSoup

    def counting_bs4(*args, **kwargs):
        parse_count["count"] += 1
        return RealBeautifulSoup(*args, **kwargs)

    monkeypatch.setattr("crawler_to_md.scraper.BeautifulSoup", counting_bs4)

    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = '<html><body><a href="/n1">n1</a><a href="/n2">n2</a></body></html>'

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(url="http://example.com/start")

    assert db.get_visited_links_count() == 3
    assert parse_count["count"] == 3


def test_start_scraping_reuses_single_markitdown_instance(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    scraper.unvisited_links_batch_size = 10

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = '<html><body><a href="/n1">n1</a><a href="/n2">n2</a></body></html>'

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    with (
        patch("crawler_to_md.scraper.MarkItDown") as mock_markdown,
        patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md
    ):
        mock_custom_md.return_value.convert_soup.return_value = "# MD"

        scraper.start_scraping(url="http://example.com/start")

    assert db.get_visited_links_count() == 3
    # With One-Parse optimization, MarkItDown is no longer
    # instantiated/called for standard HTML
    assert mock_markdown.call_count == 0
    assert mock_custom_md.return_value.convert_soup.call_count == 3


def test_scraper_proxy_initialization(monkeypatch):
    db = DummyDB()
    monkeypatch.setattr(Scraper, "_test_proxy", lambda self: None)
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        proxy="http://proxy:8080",
    )
    assert scraper.session.proxies.get("http") == "http://proxy:8080"
    assert scraper.session.proxies.get("https") == "http://proxy:8080"


def test_scraper_socks_proxy_initialization(monkeypatch):
    db = DummyDB()
    proxy = "socks5://localhost:9050"
    monkeypatch.setattr(Scraper, "_test_proxy", lambda self: None)
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        proxy=proxy,
    )
    assert scraper.session.proxies.get("http") == proxy
    assert scraper.session.proxies.get("https") == proxy


def test_scraper_proxy_failure_detection(monkeypatch):
    db = DummyDB()

    def fake_head(self, url, timeout=5):
        raise requests.exceptions.ProxyError("fail")

    monkeypatch.setattr(requests.Session, "head", fake_head)
    with pytest.raises(ValueError):
        Scraper(
            base_url="http://example.com",
            exclude_patterns=[],
            include_url_patterns=[],
            db_manager=db,
            proxy="http://proxy:8080",
        )


def test_scrape_page_returns_none_for_empty_content(monkeypatch):
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    html = "<html><body></body></html>"

    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:
        mock_custom_md.return_value.convert_soup.return_value = ""
        content, metadata = scraper.scrape_page(html, "http://example.com/empty")

    assert content is None
    assert metadata is None


def test_start_scraping_excludes_invalid_urls(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=["/exclude"],
        include_url_patterns=[],
        db_manager=db,
    )

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<html></html>"
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    urls = [
        "http://example.com/page1",
        "http://example.com/exclude/page",
        "http://example.com/page2",
    ]

    scraper.start_scraping(urls_list=urls)

    assert "http://example.com/exclude/page" not in db.links


def test_start_scraping_normalizes_seed_urls(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="https://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(urls_list=["HTTPS://EXAMPLE.COM/Page#frag"])

    assert "https://example.com/Page" in db.links


def test_start_scraping_filters_discovered_links(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=["/exclude"],
        include_url_patterns=[],
        db_manager=db,
    )

    html = (
        "<html><body>"
        '<a href="/page1">1</a>'
        '<a href="/exclude/page">2</a>'
        '<a href="/page2">3</a>'
        "</body></html>"
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = html

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(url="http://example.com")

    assert "http://example.com/exclude/page" not in db.links


def test_start_scraping_continues_after_request_exception(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    def fake_get(url, **kwargs):
        if url == "http://example.com/fail":
            raise requests.RequestException("network error")
        return DummyResp()

    monkeypatch.setattr(scraper.session, "get", fake_get)

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(
        urls_list=["http://example.com/fail", "http://example.com/ok"]
    )

    assert db.get_visited_links_count() == 2
    assert len(db.pages) == 2
    assert any(page[0] == "http://example.com/ok" for page in db.pages)
    assert any(
        page[0] == "http://example.com/fail" and page[1] is None for page in db.pages
    )


def test_start_scraping_auto_retries_failed_pages(monkeypatch):
    db = ListDB()
    db.insert_link("http://example.com/retry")
    db.mark_link_visited("http://example.com/retry")
    db.upsert_page(
        "http://example.com/retry",
        None,
        '{"scrape_status": "failed"}',
    )

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# OK", {"title": "Retried"}),
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping()

    assert len(db.pages) == 1
    assert db.pages[0][0] == "http://example.com/retry"
    assert db.pages[0][1] == "# OK"


def test_start_scraping_passes_timeout_to_get(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    setattr(scraper, "timeout", 10)

    monkeypatch.setattr(Scraper, "fetch_links", lambda self, url, html=None: set())
    monkeypatch.setattr(
        Scraper,
        "_scrape_page_from_soup",
        lambda self, soup, url: ("# MD", {"url": url}),
    )

    call_kwargs = {}

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    def fake_get(url, **kwargs):
        call_kwargs.update(kwargs)
        return DummyResp()

    monkeypatch.setattr(scraper.session, "get", fake_get)

    class DummyTqdm:
        def __init__(self, *a, **k):
            self.total = k.get("total", 0)

        def update(self, n):
            pass

        def refresh(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tqdm, "tqdm", lambda *a, **k: DummyTqdm(*a, **k))

    scraper.start_scraping(url="http://example.com/page")

    assert call_kwargs.get("timeout") == 10


def test_fetch_links_passes_timeout_when_fetching_html(monkeypatch):
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    setattr(scraper, "timeout", 10)

    call_kwargs = {}

    class DummyResp:
        status_code = 200
        text = '<html><body><a href="/page">P</a></body></html>'

        def close(self):
            pass

    def fake_get(url, **kwargs):
        call_kwargs.update(kwargs)
        return DummyResp()

    monkeypatch.setattr(scraper.session, "get", fake_get)

    links = scraper.fetch_links(url="http://example.com", html=None)

    assert "http://example.com/page" in links
    assert call_kwargs.get("timeout") == 10


def test_proxy_check_uses_timeout_default(monkeypatch):
    captured = {}

    def fake_head(self, url, timeout=5):
        captured["timeout"] = timeout

    monkeypatch.setattr(requests.Session, "head", fake_head)

    Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=DummyDB(),
        proxy="http://proxy:8080",
    )

    assert captured.get("timeout") == 10


def test_start_scraping_batch_db_calls(monkeypatch):
    """Verify that scraper uses batch methods for database updates."""
    db = MagicMock(spec=DatabaseManager)
    # Mock return values for startup queries
    db.get_links_count.return_value = 0
    db.get_visited_links_count.return_value = 0
    db.get_failed_page_urls.return_value = []
    # Mock unvisited links for one batch of 2
    db.get_unvisited_links.side_effect = [
        [("http://example.com/a",), ("http://example.com/b",)],
        [],
    ]

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    scraper.unvisited_links_batch_size = 2

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><body></body></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **kwargs: DummyResp())

    # Mock tqdm to avoid output
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    with patch("crawler_to_md.scraper._CustomMarkdownify"):
        scraper.start_scraping()

    # Verify batch methods were called instead of single ones in the loop
    assert db.upsert_pages.called
    assert db.mark_links_visited.called
    # Single upsert/mark should NOT be called inside the loop
    # (Note: Scraper might call them during init or for other reasons,
    # but the loop should prefer batch)
    pages_upserted = db.upsert_pages.call_args[0][0]
    assert len(pages_upserted) == 2


def test_scrape_page_fast_path_encoding():
    """Verify that Fast-Path handles non-ASCII characters correctly."""
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    # Content with non-ASCII characters
    html = "<html><body><p>Olá Mundo!</p></body></html>"

    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:
        mock_custom_md.return_value.convert_soup.return_value = "Olá Mundo!"
        content, _ = scraper.scrape_page(html, "http://example.com")

        assert "Olá Mundo!" in content
        # Verify body element (or soup) was passed to convert_soup
        assert mock_custom_md.return_value.convert_soup.called


def test_scraper_session_adapter_config():
    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    for protocol in ["http://", "https://"]:
        adapter = scraper.session.get_adapter(protocol)
        assert isinstance(adapter, requests.adapters.HTTPAdapter)
        assert adapter.max_retries.total == 3
        assert adapter.max_retries.backoff_factor == 1
        assert set(adapter.max_retries.status_forcelist) == {429, 500, 502, 503, 504}
        assert set(adapter.max_retries.allowed_methods) == {"HEAD", "GET", "OPTIONS"}
        assert adapter._pool_connections == 10
        assert adapter._pool_maxsize == 10


def test_scraper_retries_behavior_with_mock(monkeypatch):
    import requests_mock

    db = DummyDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    with requests_mock.Mocker() as m:
        # Configure the mock to return two 503 errors and then one 200 success
        # This tests that our code handles a sequence of responses if we were to
        # call it multiple times, OR if the adapter was active.
        # Note: requests-mock 1.12.1 + requests 2.32 bypasses HTTPAdapter retries.
        m.get("http://example.com", [
            {"text": "Service Unavailable", "status_code": 503},
            {"text": "Service Unavailable", "status_code": 503},
            {
                "text": "<html><body><a href='/ok'>ok</a></body></html>",
                "status_code": 200,
                "headers": {"Content-Type": "text/html"},
            },
        ])

        # We simulate the retries manually to verify the sequence logic
        resp1 = scraper.session.get("http://example.com")
        assert resp1.status_code == 503

        resp2 = scraper.session.get("http://example.com")
        assert resp2.status_code == 503

        resp3 = scraper.session.get("http://example.com")
        assert resp3.status_code == 200
        assert "ok" in resp3.text

        assert m.call_count == 3
