import time
from unittest.mock import MagicMock, patch

import pytest
import requests
import tqdm
from bs4 import BeautifulSoup as RealBeautifulSoup

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

    def get_retriable_failed_urls(self, max_retries):
        return []

    def upsert_page(self, url, content, metadata):
        pass

    def commit_crawl_batch(
        self, pages_upsert, visited_updates, retry_increments, retry_resets
    ):
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
        self.retry_counts = {}
        self.pages = []
        self.unvisited_query_limits = []

    def insert_link(self, url, visited=False) -> bool:
        urls = url if isinstance(url, list) else [url]
        inserted = False
        for u in urls:
            if u not in self.links:
                self.links.append(u)
                self.retry_counts[u] = 0
                inserted = True
        return inserted

    def insert_links(self, urls, visited=False):
        count = 0
        for u in urls:
            if u not in self.links:
                self.links.append(u)
                self.retry_counts[u] = 0
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

    def get_retriable_failed_urls(self, max_retries):
        return [
            url
            for url, content, _ in self.pages
            if content is None and self.retry_counts.get(url, 0) < max_retries
        ]

    def get_all_pages(self):
        return self.pages

    def mark_links_visited(self, urls):
        for url in urls:
            self.visited.add(url)

    def commit_crawl_batch(
        self, pages_upsert, visited_updates, retry_increments, retry_resets
    ):
        self.upsert_pages(pages_upsert)
        self.mark_links_visited(visited_updates)
        for url in retry_increments:
            self.retry_counts[url] = self.retry_counts.get(url, 0) + 1
        for url in retry_resets:
            self.retry_counts[url] = 0


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
        patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md,
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
    db.get_retriable_failed_urls.return_value = []
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
    assert db.commit_crawl_batch.called
    call_args = db.commit_crawl_batch.call_args[1]
    assert len(call_args["pages_upsert"]) == 2
    assert len(call_args["visited_updates"]) == 2
    # Single upsert/mark should NOT be called inside the loop
    # (Note: Scraper might call them during init or for other reasons,
    # but the loop should prefer batch)
    assert not db.upsert_pages.called


def test_retry_increments_on_failure(monkeypatch):
    db = MagicMock(spec=DatabaseManager)
    db.get_links_count.return_value = 0
    db.get_visited_links_count.return_value = 0
    db.get_retriable_failed_urls.return_value = []
    # Two links: one fails with 500, one fails with exception
    db.get_unvisited_links.side_effect = [
        [("http://example.com/500",), ("http://example.com/error",)],
        [],
    ]

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )
    scraper.unvisited_links_batch_size = 2

    # Mock responses
    class DummyResp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {"content-type": "text/html"}
            self.text = ""

        def close(self):
            pass

    def fake_get(url, **kwargs):
        if "500" in url:
            return DummyResp(500)
        if "error" in url:
            raise requests.RequestException("boom")
        return DummyResp(200)

    monkeypatch.setattr(scraper.session, "get", fake_get)
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    scraper.start_scraping()

    assert db.commit_crawl_batch.called
    call_args = db.commit_crawl_batch.call_args[1]
    retry_increments = call_args["retry_increments"]
    assert "http://example.com/500" in retry_increments
    assert "http://example.com/error" in retry_increments
    # Ensure they are also upserted as failed pages
    failed_urls = [p[0] for p in call_args["pages_upsert"]]
    assert "http://example.com/500" in failed_urls
    assert "http://example.com/error" in failed_urls


def test_retry_reset_on_success(monkeypatch):
    db = MagicMock(spec=DatabaseManager)
    db.get_links_count.return_value = 0
    db.get_visited_links_count.return_value = 0
    db.get_retriable_failed_urls.return_value = []
    db.get_unvisited_links.side_effect = [[("http://example.com/ok",)], []]

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: DummyResp())
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    with patch("crawler_to_md.scraper._CustomMarkdownify") as mock_custom_md:
        mock_custom_md.return_value.convert_soup.return_value = "content"
        scraper.start_scraping()

    assert db.commit_crawl_batch.called
    call_args = db.commit_crawl_batch.call_args[1]
    retry_resets = call_args["retry_resets"]
    assert "http://example.com/ok" in retry_resets


def test_start_scraping_uses_retriable_failed_urls(monkeypatch):
    db = MagicMock(spec=DatabaseManager)
    db.get_retriable_failed_urls.return_value = ["http://example.com/retry_me"]
    db.get_links_count.return_value = 0
    db.get_visited_links_count.return_value = 0
    db.get_unvisited_links.return_value = []

    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        max_retries=5,
    )

    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    scraper.start_scraping()

    # Should call get_retriable_failed_urls with configured max_retries
    db.get_retriable_failed_urls.assert_called_with(5)
    # Should requeue the returned url
    db.insert_link.assert_any_call("http://example.com/retry_me")
    db.mark_link_unvisited.assert_any_call("http://example.com/retry_me")


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
        m.get(
            "http://example.com",
            [
                {"text": "Service Unavailable", "status_code": 503},
                {"text": "Service Unavailable", "status_code": 503},
                {
                    "text": "<html><body><a href='/ok'>ok</a></body></html>",
                    "status_code": 200,
                    "headers": {"Content-Type": "text/html"},
                },
            ],
        )

        # We simulate the retries manually to verify the sequence logic
        resp1 = scraper.session.get("http://example.com")
        assert resp1.status_code == 503

        resp2 = scraper.session.get("http://example.com")
        assert resp2.status_code == 503

        resp3 = scraper.session.get("http://example.com")
        assert resp3.status_code == 200
        assert "ok" in resp3.text

        assert m.call_count == 3


def test_start_scraping_rate_limit(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        rate_limit=2,
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: DummyResp())
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    # We need at least rate_limit + 1 requests to trigger sleep
    urls = ["http://example.com/1", "http://example.com/2", "http://example.com/3"]
    scraper.start_scraping(urls_list=urls)

    # Should have slept once after 2 requests
    assert len(sleep_calls) >= 1


def test_start_scraping_delay(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        delay=0.5,
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: DummyResp())
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    urls = ["http://example.com/1", "http://example.com/2"]
    scraper.start_scraping(urls_list=urls)

    # Should have slept for each request
    assert len(sleep_calls) == 2
    assert all(s == 0.5 for s in sleep_calls)


def test_start_scraping_skips_non_html(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
    )

    class NonHtmlResp:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        text = "%PDF-1.4"

        def close(self):
            pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: NonHtmlResp())
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())

    scraper.start_scraping(url="http://example.com/file.pdf")

    assert db.get_visited_links_count() == 1
    assert len(db.pages) == 0  # No page should be saved


def test_failed_scrape_metadata():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    metadata = scraper._failed_scrape_metadata("failed", "ErrorType", "Some message")
    import json
    parsed = json.loads(metadata)
    assert parsed["scrape_status"] == "failed"
    assert parsed["error_type"] == "ErrorType"
    assert parsed["error_message"] == "Some message"


def test_fetch_links_with_list_href():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup('<html><body><a id="link">L</a></body></html>', "html.parser")
    link = soup.find("a")
    # Manually set href to a list, which sometimes happens with some BS4 parsers
    link["href"] = ["http://a.com/page1", "http://a.com/page2"]
    
    links = scraper._extract_links_from_soup(soup, "http://a.com")
    assert "http://a.com/page1" in links


def test_scrape_page_include_filters_no_body():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db, include_filters=["p"])
    # No <html> or <body> tags
    html = "<p>Keep</p><span>Ignore</span>"
    content, _ = scraper.scrape_page(html, "http://a.com")
    assert "Keep" in content
    assert "Ignore" not in content


def test_scrape_page_no_body_tag():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db, include_filters=["p"])
    # HTML without <html> or <body>
    html = "<p>No body</p>"
    content, _ = scraper.scrape_page(html, "http://a.com")
    assert "No body" in content


def test_start_scraping_invalid_seed_url(monkeypatch):
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())
    
    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html></html>"
        def close(self): pass

    # Test invalid URL in list
    db = ListDB()
    scraper = Scraper("http://a.com", [], [], db)
    monkeypatch.setattr(scraper.session, "get", lambda url, **k: DummyResp())
    scraper.start_scraping(urls_list=["not a url", "http://a.com/ok"])
    assert "http://a.com/ok" in db.links
    assert "not a url" not in db.links

    # Test invalid single URL
    db2 = ListDB()
    scraper2 = Scraper("http://a.com", [], [], db2)
    monkeypatch.setattr(scraper2.session, "get", lambda url, **k: DummyResp())
    scraper2.start_scraping(url="not a url")
    assert len(db2.links) == 0


def test_scrape_page_slow_path(monkeypatch):
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    
    # Mock _CustomMarkdownify to None to trigger slow path
    monkeypatch.setattr("crawler_to_md.scraper._CustomMarkdownify", None)
    
    # We need to mock MarkItDown and its convert_stream
    with patch("crawler_to_md.scraper.MarkItDown") as mock_mid:
        mock_mid.return_value.convert_stream.return_value = "Slow Path Content"
        html = "<html><body><p>Test</p></body></html>"
        content, _ = scraper.scrape_page(html, "http://a.com")
        assert content == "Slow Path Content"


def test_scrape_page_exception_handling():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db, include_filters=["p"])
    
    # Mock _find_elements which is called inside the try-except block of _scrape_page_from_soup
    with patch.object(Scraper, "_find_elements") as mock_find:
        mock_find.side_effect = Exception("Inner error")
        content, metadata = scraper.scrape_page("<html><body><p>Test</p></body></html>", "http://a.com")
        assert content is None
        assert metadata is None


def test_is_valid_link_value_error(monkeypatch):
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    
    def mock_normalize(url):
        raise ValueError("Invalid")
    
    monkeypatch.setattr("crawler_to_md.utils.normalize_url", mock_normalize)
    assert scraper.is_valid_link("anything") is False


def test_fetch_links_error_statuses(monkeypatch):
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    
    class ErrorResp:
        status_code = 404
        def close(self): pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: ErrorResp())
    assert scraper.fetch_links("http://a.com") == []

    def raise_exc(url, **k):
        raise requests.RequestException("conn error")
    
    monkeypatch.setattr(scraper.session, "get", raise_exc)
    assert scraper.fetch_links("http://a.com") == []


def test_start_scraping_response_variants(monkeypatch):
    db = ListDB()
    scraper = Scraper("http://a.com", [], [], db)
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())
    
    class Resp500:
        status_code = 500
        headers = {"content-type": "text/html"}
        def close(self): pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: Resp500())
    scraper.start_scraping(url="http://a.com/500")
    # Should be in pages as failed and have retry incremented
    assert len(db.pages) == 1
    assert db.retry_counts["http://a.com/500"] == 1

    class Resp404:
        status_code = 404
        headers = {"content-type": "text/html"}
        def close(self): pass

    db2 = ListDB()
    scraper2 = Scraper("http://a.com", [], [], db2)
    monkeypatch.setattr(scraper2.session, "get", lambda url, **k: Resp404())
    scraper2.start_scraping(url="http://a.com/404")
    # Should be marked visited but NOT in pages (permanent failure, no retry)
    assert db2.get_visited_links_count() == 1
    assert len(db2.pages) == 0


def test_start_scraping_normalize_error_in_loop(monkeypatch):
    db = ListDB()
    db.insert_link("http://a.com/bad")
    scraper = Scraper("http://a.com", [], [], db)
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())
    
    def mock_normalize(url):
        if "bad" in url:
            raise ValueError("bad")
        return url

    # We need to mock it where it's called in the loop
    monkeypatch.setattr("crawler_to_md.utils.normalize_url", mock_normalize)
    
    scraper.start_scraping()
    assert db.get_visited_links_count() == 1


def test_find_elements_missing_id():
    db = DummyDB()
    scraper = Scraper("http://a.com", [], [], db)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper._find_elements(soup, "#nonexistent") == []


def test_start_scraping_rate_limit_precise(monkeypatch):
    db = ListDB()
    scraper = Scraper(
        base_url="http://example.com",
        exclude_patterns=[],
        include_url_patterns=[],
        db_manager=db,
        rate_limit=1,
    )

    class DummyResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><body>Some content</body></html>"
        def close(self): pass

    monkeypatch.setattr(scraper.session, "get", lambda url, **k: DummyResp())
    monkeypatch.setattr(tqdm, "tqdm", MagicMock())
    # Ensure _scrape_page_from_soup returns content so pbar and other things proceed normally
    monkeypatch.setattr(Scraper, "_scrape_page_from_soup", lambda *a: ("MD", {"t": "T"}))

    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))
    
    # Mock time.time
    t_vals = [100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7]
    def mock_time():
        return t_vals.pop(0) if t_vals else 200.0
    monkeypatch.setattr(time, "time", mock_time)

    # Insert two links to ensure the second one triggers the rate limit check
    db.insert_link(["http://example.com/1", "http://example.com/2"])
    scraper.start_scraping()

    assert len(sleep_calls) >= 1
    assert sleep_calls[0] > 0
