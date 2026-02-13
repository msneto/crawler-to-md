import json
import os
import tempfile

from crawler_to_md.database_manager import DatabaseManager
from crawler_to_md.export_manager import ExportManager


def create_populated_db(tmpdir):
    db_path = os.path.join(tmpdir, "db.sqlite")
    db = DatabaseManager(db_path)
    db.insert_link("http://example.com")
    db.mark_link_visited("http://example.com")
    db.insert_page(
        "http://example.com", "# Title\nParagraph", json.dumps({"author": "John"})
    )
    return db


def test_export_markdown_and_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = create_populated_db(tmpdir)
        exporter = ExportManager(db, title="My Title")
        md_path = os.path.join(tmpdir, "out.md")
        json_path = os.path.join(tmpdir, "out.json")

        exporter.export_to_markdown(md_path)
        exporter.export_to_json(json_path)

        assert os.path.exists(md_path)
        assert os.path.exists(json_path)

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert content.startswith("# My Title")
            assert "## Title" in content
            assert "URL: http://example.com" in content

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data[0]["url"] == "http://example.com"
            assert "Title" in data[0]["content"]
            assert data[0]["metadata"]["author"] == "John"


def test_adjust_headers_and_cleanup():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, title="T")
    content = "# H1\n## H2"
    adjusted = exporter._adjust_headers(content, level_increment=1)
    assert "## H1" in adjusted
    assert "### H2" in adjusted
    cleaned = exporter._cleanup_markdown("A\n\n\nB")
    assert cleaned == "A\n\nB"


def test_concatenate_markdown_filters_metadata():
    db = DatabaseManager(":memory:")
    db.insert_page("http://a", "# T1", json.dumps({"keep": "x"}))
    db.insert_page("http://b", "# T2", json.dumps({"drop": None}))
    exporter = ExportManager(db, title="Head")
    result = exporter._concatenate_markdown(db.get_all_pages())
    assert result.startswith("# Head")
    assert "URL: http://a" in result and "T1" in result
    assert "keep: x" in result
    assert "drop:" not in result


def test_export_individual_markdown(tmp_path):
    db_path = tmp_path / "db.sqlite"
    db = DatabaseManager(str(db_path))
    db.insert_page("http://example.com/path/page", "# P", "{}")
    exporter = ExportManager(db)
    output_folder = exporter.export_individual_markdown(str(tmp_path))
    expected = tmp_path / "files" / "example.com" / "path" / "page.md"
    assert expected.exists()
    assert output_folder == str(tmp_path / "files")


def test_adjust_headers_upper_limit():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db)
    content = "###### H6\n####### H7"
    adjusted = exporter._adjust_headers(content, level_increment=1)
    lines = [line for line in adjusted.split("\n") if line.startswith("#")]
    # both lines should not exceed 6 hashes
    assert all(len(line.split()[0]) <= 6 for line in lines)


def test_concatenate_skips_none_content():
    db = DatabaseManager(":memory:")
    db.insert_page("http://a", None, "{}")
    db.insert_page("http://b", "# T", "{}")
    exporter = ExportManager(db, title="Top")
    content = exporter._concatenate_markdown(db.get_all_pages())
    assert "URL: http://a" not in content
    assert "URL: http://b" in content


def test_export_to_json_skips_none(tmp_path):
    db = DatabaseManager(":memory:")
    db.insert_page("http://a", None, "{}")
    db.insert_page("http://b", "# T", "{}")
    exporter = ExportManager(db)
    json_path = tmp_path / "out.json"
    exporter.export_to_json(str(json_path))
    data = json.load(open(json_path, "r", encoding="utf-8"))
    assert len(data) == 1 and data[0]["url"] == "http://b"


def test_export_handles_legacy_null_metadata(tmp_path):
    db = DatabaseManager(":memory:")
    db.insert_page("http://a", "# A", "null")
    exporter = ExportManager(db, title="Head")

    md_path = tmp_path / "out.md"
    json_path = tmp_path / "out.json"

    exporter.export_to_markdown(str(md_path))
    exporter.export_to_json(str(json_path))

    data = json.load(open(json_path, "r", encoding="utf-8"))
    assert data[0]["url"] == "http://a"
    assert data[0]["metadata"] == {}


def test_export_individual_skips_none_content(tmp_path):
    db = DatabaseManager(":memory:")
    db.insert_page("http://example.com/a", None, '{"scrape_status":"failed"}')
    db.insert_page("http://example.com/b", "# B", "{}")
    exporter = ExportManager(db)

    output_folder = exporter.export_individual_markdown(str(tmp_path))

    assert not (tmp_path / "files" / "example.com" / "a.md").exists()
    assert (tmp_path / "files" / "example.com" / "b.md").exists()
    assert output_folder == str(tmp_path / "files")


def test_minify_markdown_removes_blank_lines_and_trims_trailing_whitespace():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A   \n\n\nB\t\n"
    minified = exporter._minify_markdown(content)

    assert minified == "A\nB\n"


def test_minify_markdown_preserves_hard_break_spaces():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "Line with break  \n"
    minified = exporter._minify_markdown(content)

    assert minified == "Line with break  \n"


def test_minify_markdown_strips_html_comments_outside_code_blocks():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A<!-- one -->B\n<!--\nmultiline\n-->\nC\n"
    minified = exporter._minify_markdown(content)

    assert "<!--" not in minified
    assert minified == "AB\nC\n"


def test_minify_markdown_preserves_fenced_code_exactly():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = (
        "Before\n"
        "```python\n"
        "x = 1    \n"
        "\n"
        "<!-- keep in code -->\n"
        "```\n"
        "\n"
        "    indented code    \n"
        "After\n"
    )

    minified = exporter._minify_markdown(content)

    assert "x = 1    " in minified
    assert "<!-- keep in code -->" in minified


def test_minify_markdown_keeps_leading_indentation_unchanged_outside_fences():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "  indented line\n\talso indented\n"
    minified = exporter._minify_markdown(content)

    assert minified == content


def test_minify_markdown_is_idempotent():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A\n\n\n<!-- c -->\nB   \n"
    once = exporter._minify_markdown(content)
    twice = exporter._minify_markdown(once)

    assert once == twice


def test_export_to_markdown_minify_removes_metadata_comments(tmp_path):
    db_path = tmp_path / "db.sqlite"
    db = DatabaseManager(str(db_path))
    db.insert_page("http://example.com/page", "# P\n\n\nText", json.dumps({"k": "v"}))
    exporter = ExportManager(db, title="Head", minify=True)

    md_path = tmp_path / "out.md"
    exporter.export_to_markdown(str(md_path))

    content = md_path.read_text(encoding="utf-8")
    assert "<!--" not in content
    assert "URL: http://example.com/page" not in content


def test_export_individual_markdown_minifies_when_enabled(tmp_path):
    db = DatabaseManager(":memory:")
    db.insert_page(
        "http://example.com/a",
        "A   \n\n\n<!-- remove -->\nB\n",
        "{}",
    )
    exporter = ExportManager(db, minify=True)

    output_folder = exporter.export_individual_markdown(str(tmp_path))
    output_file = tmp_path / "files" / "example.com" / "a.md"

    content = output_file.read_text(encoding="utf-8")
    assert content == "A\nB\n"
    assert output_folder == str(tmp_path / "files")


def test_minify_markdown_supports_tilde_fences():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "Before\n~~~md\nline    \n<!-- keep -->\n~~~\nAfter\n"
    minified = exporter._minify_markdown(content)

    assert "line    " in minified
    assert "<!-- keep -->" in minified
    assert minified == content


def test_minify_markdown_supports_indented_fence_markers():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "Text\n   ```python\n<!-- keep -->\nx = 1    \n   ```\nDone\n"
    minified = exporter._minify_markdown(content)

    assert minified == content


def test_minify_markdown_unterminated_html_comment_drops_to_eof():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A\n<!-- starts\nstill comment\n"
    minified = exporter._minify_markdown(content)

    assert minified == "A\n"


def test_minify_markdown_inline_comment_stripping_between_text():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A <!--x--> B\n"
    minified = exporter._minify_markdown(content)

    assert minified == "A  B\n"
    assert exporter._minify_markdown(minified) == minified


def test_minify_markdown_hard_break_precision():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "one \ntwo  \nthree   \nfour\t\n"
    minified = exporter._minify_markdown(content)

    assert minified == "one\ntwo  \nthree\nfour\n"


def test_minify_markdown_preserves_indented_code_after_list_context():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "1. Item\n\n    code line    \n    <!-- removed -->\n\nAfter\n"
    minified = exporter._minify_markdown(content)

    assert minified == "1. Item\n    code line\nAfter\n"


def test_minify_off_keeps_metadata_comments_in_compiled_markdown(tmp_path):
    db_path = tmp_path / "db.sqlite"
    db = DatabaseManager(str(db_path))
    db.insert_page("http://example.com/page", "# P", json.dumps({"k": "v"}))
    exporter = ExportManager(db, title="Head", minify=False)

    md_path = tmp_path / "out.md"
    exporter.export_to_markdown(str(md_path))

    content = md_path.read_text(encoding="utf-8")
    assert "<!--" in content
    assert "URL: http://example.com/page" in content


def test_minify_on_keeps_separator_structure(tmp_path):
    db_path = tmp_path / "db.sqlite"
    db = DatabaseManager(str(db_path))
    db.insert_page("http://example.com/a", "# A", "{}")
    db.insert_page("http://example.com/b", "# B", "{}")
    exporter = ExportManager(db, title="Head", minify=True)

    md_path = tmp_path / "out.md"
    exporter.export_to_markdown(str(md_path))

    content = md_path.read_text(encoding="utf-8")
    assert "\n---" not in content


def test_minify_markdown_with_crlf_input_is_stable():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A\r\n\r\n<!-- x -->\r\nB\r\n"
    once = exporter._minify_markdown(content)
    twice = exporter._minify_markdown(once)

    assert once == twice


def test_minify_markdown_corpus_idempotence():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    fixtures = [
        "A\n\n\nB\n",
        "A <!--x--> B\n",
        "```\ncode\n\n```\n",
        "1. Item\n\n    code    \n",
    ]

    for fixture in fixtures:
        once = exporter._minify_markdown(fixture)
        twice = exporter._minify_markdown(once)
        assert once == twice


def test_minify_markdown_removes_hyphen_only_separator_lines():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "A\n---\n ---- \n-----\n--- note\nB\n"
    minified = exporter._minify_markdown(content)

    assert minified == "A\n--- note\nB\n"


def test_minify_markdown_keeps_hyphen_only_lines_inside_fences():
    db = DatabaseManager(":memory:")
    exporter = ExportManager(db, minify=True)

    content = "```\n---\n----\n```\n"
    minified = exporter._minify_markdown(content)

    assert minified == content
