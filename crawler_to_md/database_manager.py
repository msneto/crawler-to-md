import logging
import sqlite3

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path):
        """
        Initialize the DatabaseManager object with the database path and create tables.

        Args:
        db_path (str): The path to the SQLite database file.
        """
        logger.debug(f"Connecting to the database at {db_path}")
        self.conn = sqlite3.connect(db_path)
        self._closed = False
        self.create_tables()

    def close(self):
        """
        Close the database connection.

        This method is safe to call multiple times.
        """
        if getattr(self, "_closed", False):
            return

        conn = getattr(self, "conn", None)
        if conn is None:
            self._closed = True
            return

        logger.debug("Closing the database connection")
        conn.close()
        self._closed = True

    def create_tables(self):
        """
        Create tables 'pages' and 'links' if they do not exist in the database.
        """
        with self.conn:
            logger.debug("Creating tables 'pages' and 'links' if they do not exist")
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS pages (
                          url TEXT PRIMARY KEY,
                          content TEXT,
                          metadata TEXT)"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS links (
                          url TEXT PRIMARY KEY,
                          visited BOOLEAN)"""
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_visited ON links (visited)"
            )

    def insert_page(self, url, content, metadata):
        """
        Insert a new page into the 'pages' table.

        Args:
        url (str): The URL of the page.
        content (str): The content of the page.
        metadata (str): The metadata of the page.
        """
        with self.conn:
            logger.debug(f"Inserting a new page with URL: {url}")
            self.conn.execute(
                "INSERT OR IGNORE INTO pages (url, content, metadata) VALUES (?, ?, ?)",
                (url, content, metadata),
            )

    def upsert_page(self, url, content, metadata):
        """
        Insert or update a page in the 'pages' table.

        Args:
        url (str): The URL of the page.
        content (str | None): The scraped page content.
        metadata (str): The metadata of the page serialized as JSON.
        """
        with self.conn:
            logger.debug(f"Upserting page with URL: {url}")
            self.conn.execute(
                """
                INSERT INTO pages (url, content, metadata)
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    content = excluded.content,
                    metadata = excluded.metadata
                """,
                (url, content, metadata),
            )

    def insert_link(self, url, visited=False):
        """
        Insert a new link into the 'links' table if it does not exist.

        Args:
        url (str | List[str]): The URL or list of URLs of the link(s).
        visited (bool): The status of the link (default is False).

        Returns:
        bool: True if the link is inserted, False if it already exists.
        """
        if isinstance(url, str):
            urls = [url]
        elif isinstance(url, list):
            urls = url
        else:
            raise ValueError("URL must be a string or a list of strings")

        inserted_count = self.insert_links(urls, visited=visited)
        return inserted_count > 0

    def insert_links(self, urls, visited=False):
        """
        Insert multiple links into the 'links' table if they do not exist.

        Args:
        urls (List[str]): URLs to insert.
        visited (bool): Initial visited status (default False).

        Returns:
        int: Number of newly inserted links.
        """
        if not isinstance(urls, list):
            raise ValueError("URLs must be provided as a list of strings")

        if not urls:
            return 0

        with self.conn:
            for link in urls:
                logger.debug(f"Inserting a new link with URL: {link}")

            before_changes = self.conn.total_changes
            self.conn.executemany(
                "INSERT OR IGNORE INTO links (url, visited) VALUES (?, ?)",
                ((link, visited) for link in urls),
            )
            return self.conn.total_changes - before_changes

    def mark_link_visited(self, url):
        """
        Mark a link as visited in the 'links' table.

        Args:
        url (str): The URL of the link to mark as visited.
        """
        with self.conn:
            logger.debug(f"Marking link as visited with URL: {url}")
            self.conn.execute("UPDATE links SET visited = TRUE WHERE url = ?", (url,))

    def get_unvisited_links(self, limit=None):
        """
        Retrieve all unvisited links from the 'links' table.

        Args:
        limit (int | None): Maximum number of rows to return.

        Returns:
        list: List of unvisited links.
        """
        if limit is not None:
            if not isinstance(limit, int):
                raise ValueError("limit must be an integer or None")
            if limit < 0:
                raise ValueError("limit must be greater than or equal to 0")

        with self.conn:
            logger.debug("Retrieving all unvisited links")
            if limit is None:
                cursor = self.conn.execute(
                    "SELECT url FROM links WHERE visited = FALSE"
                )
            else:
                cursor = self.conn.execute(
                    "SELECT url FROM links WHERE visited = FALSE LIMIT ?", (limit,)
                )
            return cursor.fetchall()

    def get_links_count(self):
        """
        Retrieve the total number of links in the 'links' table.

        Returns:
        int: The total number of links.
        """
        with self.conn:
            logger.debug("Retrieving the total number of links")
            cursor = self.conn.execute("SELECT COUNT(*) FROM links")
            return cursor.fetchone()[0]

    def get_visited_links_count(self):
        """
        Retrieve the total number of visited links in the 'links' table.

        Returns:
        int: The total number of visited links.
        """
        with self.conn:
            logger.debug("Retrieving the total number of visited links")
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM links WHERE visited = TRUE"
            )
            return cursor.fetchone()[0]

    def get_all_pages(self):
        """
        Retrieve all pages from the 'pages' table.

        Returns:
        list: List of tuples containing page URL, content, and metadata.
        """
        with self.conn:
            logger.debug("Retrieving all pages")
            cursor = self.conn.execute("SELECT url, content, metadata FROM pages")
            return cursor.fetchall()

    def get_failed_page_urls(self):
        """
        Retrieve URLs of pages with failed scraping attempts.

        Returns:
        list[str]: URLs whose page content is NULL.
        """
        with self.conn:
            logger.debug("Retrieving URLs for failed pages")
            cursor = self.conn.execute("SELECT url FROM pages WHERE content IS NULL")
            return [row[0] for row in cursor.fetchall()]

    def mark_link_unvisited(self, url):
        """
        Mark a link as unvisited in the 'links' table.

        Args:
        url (str): The URL of the link to mark as unvisited.
        """
        with self.conn:
            logger.debug(f"Marking link as unvisited with URL: {url}")
            self.conn.execute("UPDATE links SET visited = FALSE WHERE url = ?", (url,))

    def __del__(self):
        """
        Close the database connection when the object is deleted.
        """
        try:
            self.close()
        except Exception:
            pass
