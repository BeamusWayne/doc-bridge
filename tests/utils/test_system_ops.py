"""Unit tests for system_ops helpers."""

from __future__ import annotations

import pytest

from doc_bridge.utils.system_ops import suggest_close_system, validate_system_name


class TestValidateSystemName:
    @pytest.mark.parametrize(
        "name",
        ["system-A", "ps", "cbtc_v2", "系统一", "ATP-2", "a"],
    )
    def test_accepts_valid_names(self, name: str) -> None:
        # Should not raise
        validate_system_name(name)

    @pytest.mark.parametrize(
        "name,fragment",
        [
            ("", "不能为空"),
            (".", "保留字"),
            ("..", "保留字"),
            ("sys a", "非法字符"),
            ("sys/a", "非法字符"),
            ("sys\\a", "非法字符"),
            ("sys.a", "非法字符"),
            ("a" * 65, "过长"),
        ],
    )
    def test_rejects_invalid_names(self, name: str, fragment: str) -> None:
        with pytest.raises(ValueError) as exc:
            validate_system_name(name)
        assert fragment in str(exc.value)


class TestSuggestCloseSystem:
    def test_typo_matches_closest(self) -> None:
        assert suggest_close_system("sytem-A", ["system-A", "ps"]) == "system-A"

    def test_unrelated_returns_none(self) -> None:
        assert suggest_close_system("xyz", ["system-A", "ps"]) is None

    def test_empty_list_returns_none(self) -> None:
        assert suggest_close_system("anything", []) is None

    def test_exact_match_returns_match(self) -> None:
        assert suggest_close_system("ps", ["system-A", "ps"]) == "ps"
