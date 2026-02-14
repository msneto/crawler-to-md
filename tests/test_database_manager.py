import os
import sqlite3
import tempfile

from crawler_to_md.database_manager import DatabaseManager


def test_database_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = DatabaseManager(db_path)

        # Insert link and verify count
        assert db.insert_link("http://example.com") is True
        assert db.get_links_count() == 1
        assert db.get_unvisited_links() == [("http://example.com",)]

        # Mark link visited
        db.mark_link_visited("http://example.com")
        assert db.get_visited_links_count() == 1
        assert db.get_unvisited_links() == []

        # Insert page and read back
        db.insert_page("http://example.com", "content", "{}")
        pages = db.get_all_pages()
        assert pages == [("http://example.com", "content", "{}")]


def test_insert_link_duplicates_and_list():
    db = DatabaseManager(":memory:")
    assert db.insert_link("http://a") is True
    # duplicate single link should return False
    assert db.insert_link("http://a") is False
    # insert list with one new and one duplicate
    assert db.insert_link(["http://b", "http://a"]) is True
    # total links should be 2
    assert db.get_links_count() == 2
    assert set(db.get_unvisited_links()) == {("http://a",), ("http://b",)}


def test_insert_links_returns_inserted_count():
    db = DatabaseManager(":memory:")

    inserted = db.insert_links(["http://a", "http://b", "http://a"])

    assert inserted == 2
    assert db.get_links_count() == 2


def test_insert_links_rejects_non_list_input():
    db = DatabaseManager(":memory:")

    try:
        db.insert_links("http://a")
        assert False, "Expected ValueError for non-list input"
    except ValueError:
        assert True


def test_upsert_page_replaces_existing_content():
    db = DatabaseManager(":memory:")
    db.insert_page("http://a", None, '{"scrape_status":"failed"}')

    db.upsert_page("http://a", "# Title", '{"title":"A"}')

    assert db.get_all_pages() == [("http://a", "# Title", '{"title":"A"}')]


def test_get_failed_page_urls_and_mark_unvisited():
    db = DatabaseManager(":memory:")
    db.insert_link("http://a", visited=True)
    db.insert_link("http://b", visited=True)
    db.insert_page("http://a", None, '{"scrape_status":"failed"}')
    db.insert_page("http://b", "# ok", '{"title":"ok"}')

    assert db.get_failed_page_urls() == ["http://a"]

    db.mark_link_unvisited("http://a")

    assert db.get_unvisited_links() == [("http://a",)]


def test_get_unvisited_links_limit_support():
    db = DatabaseManager(":memory:")
    db.insert_link(["http://a", "http://b", "http://c"])
    db.mark_link_visited("http://b")

    limited = db.get_unvisited_links(limit=1)
    assert len(limited) == 1
    assert limited[0][0] in {"http://a", "http://c"}

    limited_large = db.get_unvisited_links(limit=10)
    assert set(limited_large) == {("http://a",), ("http://c",)}

    assert db.get_unvisited_links(limit=0) == []


def test_get_unvisited_links_limit_validation():
    db = DatabaseManager(":memory:")
    db.insert_link("http://a")

    try:
        db.get_unvisited_links(limit=-1)
        assert False, "Expected ValueError for negative limit"
    except ValueError:
        assert True

    try:
        db.get_unvisited_links(limit="2")
        assert False, "Expected ValueError for non-integer limit"
    except ValueError:
        assert True


def test_close_is_idempotent():
    db = DatabaseManager(":memory:")

    db.close()
    db.close()


def test_operations_fail_after_close():
    db = DatabaseManager(":memory:")
    db.close()

    try:
        db.get_links_count()
        assert False, "Expected sqlite3.ProgrammingError after close"
    except sqlite3.ProgrammingError:
        assert True


def test_database_wal_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = DatabaseManager(db_path)
        cursor = db.conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"


def test_get_pages_iterator_paging():
    db = DatabaseManager(":memory:")
    # Insert 150 pages to test the 100-page paging logic
    pages = [(f"http://{i}", f"content {i}", "{}") for i in range(150)]
    db.upsert_pages(pages)

    iterator = db.get_pages_iterator()
    results = list(iterator)

    assert len(results) == 150
    assert results[0][0] == "http://0"
    assert results[149][0] == "http://149"


def test_upsert_pages_batch():
    db = DatabaseManager(":memory:")
    initial_pages = [("http://a", "c1", "{}"), ("http://b", "c2", "{}")]
    db.upsert_pages(initial_pages)

    # Update one and insert one new
    update_pages = [("http://a", "updated", '{"k":"v"}'), ("http://c", "c3", "{}")]
    db.upsert_pages(update_pages)

    all_pages = dict((url, content) for url, content, _ in db.get_all_pages())
    assert all_pages["http://a"] == "updated"
    assert all_pages["http://b"] == "c2"
    assert all_pages["http://c"] == "c3"
    assert len(all_pages) == 3
