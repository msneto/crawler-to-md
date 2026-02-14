import json
import os
import re

from . import log_setup
from .database_manager import DatabaseManager

logger = log_setup.get_logger()
logger.name = "export_manager"


class ExportManager:
    def __init__(self, db_manager: DatabaseManager, title=None, minify=False):
        """
        Initialize the ExportManager with a DatabaseManager instance.

        Args:
            db_manager (DatabaseManager): The DatabaseManager instance for exporting.
        """
        self.db_manager = db_manager
        self.title = title
        self.minify = minify
        logger.info("ExportManager initialized.")  # Add log message

    def _adjust_headers(self, content, level_increment=1):
        """
        Adjust the header levels in the Markdown content.
        The goal is to transform the Markdown content to remain semantically
        valid despite the concatenation.

        Args:
            content (str): The Markdown content to adjust.
            level_increment (int): The increment value for adjusting header levels.

        Returns:
            str: The adjusted Markdown content.
        """
        new_content = ""
        for line in content.split("\n"):
            if line.startswith("#"):
                hashes = len(line.split(" ")[0])
                new_hashes = min(hashes + level_increment, 6)  # Limit to ######
                line = "\n" + "#" * new_hashes + line[hashes:] + "\n"
            new_content += line + "\n"
        return new_content

    def _cleanup_markdown(self, content):
        """
        Remove excessive newline characters from Markdown content.

        This method replaces sequences of three or more consecutive newline characters
        with exactly two newline characters, ensuring that there are no unnecessary
        blank lines in the output.

        Args:
            content (str): The Markdown content to be cleaned up.

        Returns:
            str: The cleaned-up Markdown content with reduced newline characters.
        """
        while "\n\n\n" in content:
            content = content.replace("\n\n\n", "\n\n")
        return content

    def _line_starts_fence(self, line):
        stripped = line.lstrip(" ")
        if stripped.startswith("```"):
            return "`"
        if stripped.startswith("~~~"):
            return "~"
        return None

    def _line_closes_fence(self, line, fence_char):
        stripped = line.lstrip(" ")
        if fence_char == "`":
            return stripped.startswith("```")
        return stripped.startswith("~~~")

    def _strip_html_comments_from_line(self, line, in_comment):
        processed = []
        index = 0

        while index < len(line):
            if in_comment:
                comment_end = line.find("-->", index)
                if comment_end == -1:
                    return "".join(processed), True
                index = comment_end + 3
                in_comment = False
                continue

            comment_start = line.find("<!--", index)
            if comment_start == -1:
                processed.append(line[index:])
                break

            processed.append(line[index:comment_start])
            index = comment_start + 4
            in_comment = True

        return "".join(processed), in_comment

    def _minify_markdown(self, content):
        had_trailing_newline = content.endswith("\n")
        lines = content.split("\n")
        output_lines = []
        in_fenced_code = False
        fence_char = None
        in_html_comment = False

        for line in lines:
            if in_fenced_code:
                output_lines.append(line)
                if self._line_closes_fence(line, fence_char):
                    in_fenced_code = False
                    fence_char = None
                continue

            current_fence_char = self._line_starts_fence(line)
            if current_fence_char:
                in_fenced_code = True
                fence_char = current_fence_char
                output_lines.append(line)
                continue

            stripped_line, in_html_comment = self._strip_html_comments_from_line(
                line, in_html_comment
            )

            if stripped_line.endswith("  ") and not stripped_line.endswith("   "):
                normalized_line = stripped_line
            else:
                normalized_line = stripped_line.rstrip(" \t")

            if normalized_line.strip() == "":
                continue

            if re.fullmatch(r"-{3,}", normalized_line.strip()):
                continue

            output_lines.append(normalized_line)

        minified = "\n".join(output_lines)
        if had_trailing_newline and minified:
            minified += "\n"
        return minified

    def _safe_metadata_dict(self, metadata):
        """
        Parse metadata JSON and return a dictionary.

        Args:
            metadata (str): Serialized metadata.

        Returns:
            dict: Parsed metadata dictionary or an empty dict.
        """
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _concatenate_markdown(self, pages):
        """
        Concatenate a list of Markdown files into one, with header adjustments.

        Args:
            pages (iterator): Iterator of pages to concatenate.

        Returns:
            str: The concatenated Markdown content.
        """
        parts = [f"# {self.title}\n"]
        for url, content, metadata in pages:
            if content is None:
                continue  # Skip empty pages

            # Adjust headers for subsequent files and add metadata
            adjusted_content = self._adjust_headers(content)

            if self.minify:
                parts.append("\n" + adjusted_content)
            else:
                filtered_metadata = {
                    k: v
                    for k, v in self._safe_metadata_dict(metadata).items()
                    if v is not None
                }

                # Prepare metadata as an HTML comment
                metadata_content = "<!--\n"
                metadata_content += f"URL: {url}\n"
                for key, value in filtered_metadata.items():
                    metadata_content += f"{key}: {value}\n"
                metadata_content += "-->"

                parts.append("\n" + metadata_content + "\n\n" + adjusted_content + "\n---")

        final_content = "".join(parts)
        final_content = self._cleanup_markdown(final_content)

        if self.minify:
            final_content = self._minify_markdown(final_content)

        return final_content

    def export_to_markdown(self, output_path):
        """
        Export the pages to a markdown file.

        Args:
            output_path (str): The path to the output markdown file.
        """
        pages = self.db_manager.get_pages_iterator()
        with open(output_path, "w", encoding="utf-8") as md_file:
            md_file.write(self._concatenate_markdown(pages))
        logger.info(f"Exported pages to markdown file: {output_path}")

    def export_to_json(self, output_path):
        """
        Export the pages to a JSON file.

        Args:
            output_path (str): The path to the output JSON file.
        """
        pages = self.db_manager.get_pages_iterator()
        with open(output_path, "w", encoding="utf-8") as json_file:
            # Filter metadata and strip null values
            data_to_export = []
            for url, content, metadata in pages:
                if content is None:
                    continue  # Skip empty pages

                content = self._cleanup_markdown(content)

                filtered_metadata = {
                    k: v
                    for k, v in self._safe_metadata_dict(metadata).items()
                    if v is not None
                }
                data_to_export.append(
                    {"url": url, "content": content, "metadata": filtered_metadata}
                )
            json.dump(data_to_export, json_file, ensure_ascii=False, indent=4)
            # Log the successful export to JSON file
            logger.info(f"Exported pages to JSON file: {output_path}")

    def export_individual_markdown(self, output_folder, base_url=None):
        """
        Export each page individually as Markdown, preserving the URL's structure.

        Args:
            output_folder (str): The base output folder where the files will be saved.
            base_url (str or None): Base URL to remove for creating the path.
        """
        pages = self.db_manager.get_pages_iterator()
        # Add 'files/' to the output folder and create it if it doesn't exist
        output_folder = os.path.join(output_folder, "files")

        os.makedirs(output_folder, exist_ok=True)
        for page in pages:
            url, content, _metadata = page
            logger.debug(f"Exporting individual Markdown for URL: {url}")

            if content is None:
                continue

            # Remove base_url from parsed URL if provided
            if base_url:
                url = url.replace(base_url, "")

            # Parse the URL to determine the folder and filename
            parsed_url = url.replace("https://", "").replace("http://", "")
            if parsed_url.endswith("/") or parsed_url == "":
                file_path = os.path.join(output_folder, parsed_url, "index.md")
            else:
                file_path = os.path.join(output_folder, parsed_url + ".md")

            # Ensure directories exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write the Markdown content
            with open(file_path, "w", encoding="utf-8") as file:
                if self.minify:
                    content = self._minify_markdown(content)
                file.write(content)
                logger.debug(f"Markdown exported to {file_path}")

        return output_folder
