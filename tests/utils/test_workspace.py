"""Unit tests for workspace path utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_bridge.utils.workspace import relative_link


class TestRelativeLink:
    def test_simple_ascii_no_spaces(self, tmp_path: Path) -> None:
        src = tmp_path / "synthesis/ps/实体总表.md"
        dst = tmp_path / "atoms/ps/doc1/entities/x.md"
        assert relative_link(src, dst) == "../../atoms/ps/doc1/entities/x.md"

    def test_encodes_spaces_as_percent_20(self, tmp_path: Path) -> None:
        src = tmp_path / "synthesis/xianche/数据流总表.md"
        dst = tmp_path / "raw/xianche/课程1-5 CS V3.0操作手册.pdf"
        result = relative_link(src, dst)
        assert " " not in result
        assert "%20" in result
        assert result.endswith(".pdf")

    def test_encodes_chinese_characters(self, tmp_path: Path) -> None:
        src = tmp_path / "synthesis/xianche/表.md"
        dst = tmp_path / "raw/xianche/调图操作.docx"
        result = relative_link(src, dst)
        # Chinese chars must be percent-encoded
        assert "调图操作" not in result
        assert "%E8%B0%83" in result  # '调' encoded
        assert result.endswith(".docx")

    def test_preserves_slash_separator(self, tmp_path: Path) -> None:
        src = tmp_path / "a/b/from.md"
        dst = tmp_path / "a/b/c/d/to.md"
        result = relative_link(src, dst)
        # Slashes must not be encoded
        assert "/" in result
        assert "%2F" not in result

    def test_encodes_parentheses(self, tmp_path: Path) -> None:
        src = tmp_path / "synthesis/x/表.md"
        dst = tmp_path / "raw/x/同步屏后台(主).md"
        result = relative_link(src, dst)
        # Parens break markdown () link syntax if not encoded
        assert "(" not in result
        assert ")" not in result
        assert "%28" in result
        assert "%29" in result

    def test_result_is_a_valid_markdown_link_body(self, tmp_path: Path) -> None:
        src = tmp_path / "synthesis/xianche/数据流总表.md"
        dst = tmp_path / "raw/xianche/CS V3.0 (beta).pdf"
        link = f"[文件]({relative_link(src, dst)})"
        # A Markdown link body must contain no unescaped spaces or parens
        url_part = link[link.index("(") + 1 : link.rindex(")")]
        assert " " not in url_part
        assert "(" not in url_part
        assert ")" not in url_part

    @pytest.mark.parametrize(
        "src_rel,dst_rel,expected",
        [
            ("synthesis/ps/t.md", "atoms/ps/a.md", "../../atoms/ps/a.md"),
            ("a/b.md", "a/c.md", "c.md"),
            ("a/b/c.md", "a/b/d/e.md", "d/e.md"),
        ],
    )
    def test_path_computation_unchanged_for_ascii(
        self, tmp_path: Path, src_rel: str, dst_rel: str, expected: str,
    ) -> None:
        src = tmp_path / src_rel
        dst = tmp_path / dst_rel
        assert relative_link(src, dst) == expected
