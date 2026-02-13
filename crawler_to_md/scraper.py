import copy
import json
import os
import tempfile
import time
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup, Tag
from markitdown import MarkItDown
from tqdm import tqdm

from . import log_setup, utils
from .database_manager import DatabaseManager

logger = log_setup.get_logger()
logger.name = "Scraper"


class Scraper:
    UNVISITED_LINKS_BATCH_SIZE = 200

    def __init__(
        self,
        base_url,
        exclude_patterns,
        include_url_patterns,
        db_manager: DatabaseManager,
        rate_limit=0,
        delay=0,
        timeout=10,
        proxy=None,
        include_filters=None,
        exclude_filters=None,
    ):
        """
        Initialize the Scraper object and log the initialization process.

        Args:
            base_url (str): The base URL to start scraping from.
            exclude_patterns (list): List of URL patterns to exclude from scraping.
            include_url_patterns (list): List of URL patterns that must be
                present to scrape.
            db_manager (DatabaseManager): The database manager object.
            rate_limit (int): Maximum number of requests per minute.
            delay (float): Delay between requests in seconds.
            timeout (float): Request timeout in seconds.
            proxy (str, optional): Proxy URL for HTTP or SOCKS requests.
            include_filters (list, optional): CSS-like selectors (#id, .class, tag)
                of elements to include before Markdown conversion.
            exclude_filters (list, optional): CSS-like selectors (#id, .class, tag)
                of elements to exclude before Markdown conversion.

        Raises:
            ValueError: If a proxy is provided but unreachable.
        """
        logger.debug(f"Initializing Scraper with base URL: {base_url}")
        self.base_url = utils.normalize_url(base_url) if base_url else base_url
        self.exclude_patterns = exclude_patterns or []
        self.include_url_patterns = include_url_patterns or []
        self.db_manager = db_manager
        self.rate_limit = rate_limit
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})
        self.proxy = proxy
        self.unvisited_links_batch_size = self.UNVISITED_LINKS_BATCH_SIZE
        self._markdown_converter = None

        self.include_filters = include_filters or []
        self.exclude_filters = exclude_filters or []

        if proxy:
            self._test_proxy()

    def _get_markdown_converter(self):
        """
        Return a cached Markdown converter instance for this scraper.

        Returns:
            MarkItDown: Converter instance reused across page conversions.
        """
        if self._markdown_converter is None:
            self._markdown_converter = MarkItDown()
        return self._markdown_converter

    def _test_proxy(self):
        """
        Ensure the configured proxy is reachable.

        Raises:
            ValueError: If the proxy cannot fetch the base URL.
        """
        try:
            self.session.head(self.base_url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ValueError(f"Proxy unreachable: {exc}") from exc

    def _find_elements(self, soup: BeautifulSoup, selector: str):
        """
        Locate elements in the soup using a CSS-like selector.

        Args:
            soup (BeautifulSoup): Parsed HTML document.
            selector (str): Selector in the form of '#id', '.class', or tag name.

        Returns:
            list[Tag]: List of matching elements.
        """
        if selector.startswith("#"):
            element = soup.find(id=selector[1:])
            return [element] if element else []
        if selector.startswith("."):
            return soup.find_all(class_=selector[1:])
        return soup.find_all(selector)

    def _failed_scrape_metadata(self, status, error_type=None, error_message=None):
        """
        Build structured metadata for failed scraping attempts.

        Args:
            status (str): Scrape status value.
            error_type (str, optional): Exception class name or category.
            error_message (str, optional): Error details.

        Returns:
            str: JSON metadata string for persistence.
        """
        metadata = {"scrape_status": status}
        if error_type:
            metadata["error_type"] = error_type
        if error_message:
            metadata["error_message"] = error_message
        return json.dumps(metadata)

    def _extract_links_from_soup(self, soup: BeautifulSoup, url: str):
        """
        Extract and filter valid links from an already parsed HTML soup.

        Args:
            soup (BeautifulSoup): Parsed HTML document.
            url (str): Base URL used to resolve relative links.

        Returns:
            set[str]: Unique set of valid normalized links.
        """
        links = []
        for anchor in soup.find_all("a", href=True):
            if isinstance(anchor, Tag):
                href = anchor.get("href")
                if href:
                    if isinstance(href, list):
                        href = href[0]
                    absolute_link = urljoin(url, str(href))
                    link_without_fragment = urldefrag(absolute_link)[0]
                    try:
                        normalized_link = utils.normalize_url(link_without_fragment)
                    except ValueError:
                        continue
                    if not utils.is_supported_scheme(normalized_link):
                        continue
                    links.append(normalized_link)

        filtered_links = [link for link in links if self.is_valid_link(link)]
        logger.debug(f"Found {len(filtered_links)} valid links on {url}")
        return set(filtered_links)

    def _scrape_page_from_soup(self, soup: BeautifulSoup, url: str):
        """
        Scrape Markdown content and metadata from an already parsed HTML soup.

        Args:
            soup (BeautifulSoup): Parsed HTML document.
            url (str): The URL being scraped.

        Returns:
            tuple[str | None, dict | None]: Scraped markdown and metadata.
        """
        logger.info(f"Scraping page {url}")

        try:
            if self.include_filters:
                new_soup = BeautifulSoup("", "html.parser")
                if soup.find("body"):
                    body = new_soup.new_tag("body")
                    new_soup.append(body)
                else:
                    body = new_soup

                elements = []
                for selector in self.include_filters:
                    elements.extend(self._find_elements(soup, selector))

                for element in elements:
                    body.append(copy.copy(element))
                soup = new_soup

            for selector in self.exclude_filters:
                for element in self._find_elements(soup, selector):
                    element.decompose()

            title = soup.title.string if soup.title else ""
            metadata = {"title": title}

            filtered_html = str(soup)
            with tempfile.NamedTemporaryFile(
                mode="w+", delete=False, suffix=".html"
            ) as tmp:
                tmp.write(filtered_html)
                tmp_path = tmp.name

            markdown = str(self._get_markdown_converter().convert(tmp_path))

            os.remove(tmp_path)

            if not markdown.strip():
                logger.warning("No content scraped from %s", url)
                return None, None

            logger.debug("Successfully scraped content and metadata from %s", url)
            return markdown, metadata

        except Exception as e:
            logger.error("Error scraping %s: %s", url, e)
            return None, None

    def is_valid_link(self, link):
        """
        Check if the given link is valid for scraping.
        Log the result of the validation.

        Args:
            link (str): The link to be checked.

        Returns:
            bool: True if the link is valid, False otherwise.
        """
        try:
            normalized_link = utils.normalize_url(link)
        except ValueError:
            logger.debug(f"Link validation for {link}: False")
            return False

        valid = True
        if not utils.is_supported_scheme(normalized_link):
            valid = False
        if self.base_url and not utils.is_url_in_scope(normalized_link, self.base_url):
            valid = False
        if self.include_url_patterns and not any(
            pattern in normalized_link for pattern in self.include_url_patterns
        ):
            valid = False
        for pattern in self.exclude_patterns:
            if pattern in normalized_link:
                valid = False
        logger.debug(f"Link validation for {normalized_link}: {valid}")
        return valid

    def fetch_links(self, url, html=None):
        """
        Fetch all valid links from the given URL.
        Log the fetching process and outcome.

        Args:
            url (str): The URL to fetch links from.
            html (str, optional): The HTML content of the page.

        Returns:
            set: Set of valid links found on the page.
        """
        logger.debug(f"Fetching links from {url}")
        try:
            if not html:
                # Send a GET request to the URL
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    logger.warning(
                        f"Failed to fetch {url} with status code {response.status_code}"
                    )
                    return []
                else:
                    content = response.text
            else:
                content = html

            soup = BeautifulSoup(content, "html.parser")
            return self._extract_links_from_soup(soup, url)
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return []

    def scrape_page(self, html, url):
        """
        Scrape the content and metadata from the given URL.
        Log the scraping process and outcome.

        Args:
            html (str): The HTML content of the page.
            url (str): The URL to scrape.

        Returns:
            tuple: A tuple containing the extracted content and metadata of the page.
        """
        soup = BeautifulSoup(html, "html.parser")
        return self._scrape_page_from_soup(soup, url)

    def start_scraping(self, url=None, urls_list=None):
        """
        Initiates the scraping process for a single URL or a list of URLs.
        It validates URLs, logs the scraping process, and manages the
        progress of scraping through the database.

        Args:
            url (str, optional): A single URL to start scraping from. Defaults to None.
            urls_list (list, optional): A list of URLs to scrape.
        """
        # Validate and insert the provided URLs into the database
        urls = urls_list or []
        if urls:
            # Build a new list of valid URLs without modifying the original list
            validated_urls = []
            for url_item in urls:
                try:
                    normalized_url = utils.normalize_url(url_item)
                except ValueError:
                    logger.warning(f"Skipping invalid URL: {url_item}")
                    continue

                if not self.is_valid_link(normalized_url):
                    logger.warning(f"Skipping invalid URL: {url_item}")
                    continue
                validated_urls.append(normalized_url)

            # Insert the validated list of URLs into the database
            self.db_manager.insert_link(validated_urls)
        elif url:
            # Insert a single URL if provided and valid
            try:
                normalized_url = utils.normalize_url(url)
            except ValueError:
                logger.warning(f"Skipping invalid URL: {url}")
                normalized_url = None

            if normalized_url:
                self.db_manager.insert_link(normalized_url)

        # Auto-retry previously failed pages (content IS NULL)
        for failed_url in self.db_manager.get_failed_page_urls():
            try:
                normalized_failed_url = utils.normalize_url(failed_url)
            except ValueError:
                continue
            if not self.is_valid_link(normalized_failed_url):
                continue
            self.db_manager.insert_link(normalized_failed_url)
            self.db_manager.mark_link_unvisited(normalized_failed_url)

        # Log the start of the scraping process
        logger.info("Starting scraping process")

        # Initialize a progress bar to track scraping progress
        pbar = tqdm(
            total=self.db_manager.get_links_count(),
            initial=self.db_manager.get_visited_links_count(),
            desc="Scraping",
            unit="link",
        )

        # Initialize rate limit tracking variables
        request_count = 0
        start_time = time.time()

        # Begin the scraping loop
        while True:
            # Fetch a list of unvisited links from the database
            try:
                unvisited_links = self.db_manager.get_unvisited_links(
                    limit=self.unvisited_links_batch_size
                )
            except TypeError:
                unvisited_links = self.db_manager.get_unvisited_links()

            # Exit the loop if there are no more links to visit
            if not unvisited_links:
                logger.info("No more links to visit. Exiting.")
                break

            # Process each unvisited link
            for link in unvisited_links:
                # Check rate limit
                if self.rate_limit > 0:
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    if request_count >= self.rate_limit:
                        sleep_time = 60 - elapsed_time
                        if sleep_time > 0:
                            logger.debug(
                                f"Rate limit reached, sleeping for {sleep_time} seconds"
                            )
                            time.sleep(sleep_time)
                        # Reset the rate limit tracker
                        request_count = 0
                        start_time = time.time()

                # Wait for the specified self.delay before making the next request
                if self.delay > 0:
                    logger.debug(
                        f"Delaying for {self.delay} seconds before next request"
                    )
                    time.sleep(self.delay)

                pbar.update(1)  # Update the progress bar
                raw_url = link[0]
                try:
                    url = utils.normalize_url(raw_url)
                except ValueError:
                    self.db_manager.mark_link_visited(raw_url)
                    continue

                if not self.is_valid_link(url):
                    self.db_manager.mark_link_visited(raw_url)
                    continue

                # Attempt to fetch the page content
                try:
                    response = self.session.get(url, timeout=self.timeout)
                    # Increment request count for rate limiting
                    request_count += 1
                except requests.RequestException as exc:
                    # Increment request count for rate limiting
                    request_count += 1
                    logger.error("Error fetching %s: %s", url, exc)
                    self.db_manager.upsert_page(
                        url,
                        None,
                        self._failed_scrape_metadata(
                            status="failed",
                            error_type=exc.__class__.__name__,
                            error_message=str(exc),
                        ),
                    )
                    self.db_manager.mark_link_visited(raw_url)
                    continue

                # Check for a successful response and correct content type
                if response.status_code != 200 or not response.headers.get(
                    "content-type", ""
                ).startswith("text/html"):
                    # Mark the link as visited and log the reason for skipping
                    self.db_manager.mark_link_visited(raw_url)
                    logger.info(
                        "Skipping link %s due to invalid status code or content type",
                        url,
                    )
                    continue

                # Extract the HTML content from the response
                html = response.text

                # Parse once and reuse for extraction and link discovery
                soup = BeautifulSoup(html, "html.parser")
                discovered_links = set()
                if not urls_list:
                    discovered_links = self._extract_links_from_soup(soup, url)

                # Scrape the page for content and metadata
                content, metadata = self._scrape_page_from_soup(soup, url)

                # Insert or update scraped data in the database
                if content is None:
                    self.db_manager.upsert_page(
                        url,
                        None,
                        self._failed_scrape_metadata(
                            status="failed",
                            error_type="NoContentError",
                            error_message="No content extracted",
                        ),
                    )
                else:
                    self.db_manager.upsert_page(url, content, json.dumps(metadata))

                # Fetch and insert new links found on the page,
                # if not working from a predefined list
                if not urls_list:
                    new_links = discovered_links

                    # Count and insert new links into the database in batch
                    real_new_links_count = 0
                    if new_links:
                        if hasattr(self.db_manager, "insert_links"):
                            real_new_links_count = self.db_manager.insert_links(
                                list(new_links)
                            )
                        else:
                            for new_url in new_links:
                                if self.db_manager.insert_link(new_url):
                                    real_new_links_count += 1
                                    logger.debug(
                                        f"Inserted new link {new_url} into the database"
                                    )

                    # Update the progress bar total with the count of new links
                    if real_new_links_count:
                        pbar.total += real_new_links_count
                        pbar.refresh()

                # Mark the current link as visited in the database
                self.db_manager.mark_link_visited(raw_url)

        # Close the progress bar upon completion of the scraping process
        pbar.close()
