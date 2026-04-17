"""Unit tests for system_ops helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_bridge.models.config import WorkspaceConfig
from doc_bridge.utils.system_ops import (
    create_system_dirs,
    suggest_close_system,
    validate_system_name,
)


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


class TestCreateSystemDirs:
    def test_creates_all_dirs_for_new_system(self, tmp_workspace: Path) -> None:
        ws = WorkspaceConfig(root=tmp_workspace)
        created = create_system_dirs(ws, "system-B")

        assert created is True
        assert (tmp_workspace / "raw" / "system-B").is_dir()
        assert (tmp_workspace / "config" / "systems" / "system-B" / "prompts").is_dir()
        assert (tmp_workspace / "config" / "systems" / "system-B" / "blacklists").is_dir()
        yaml_file = (
            tmp_workspace / "config" / "systems" / "system-B" / "blacklists" / "system.yaml"
        )
        assert yaml_file.is_file()
        content = yaml_file.read_text(encoding="utf-8")
        assert "tech_terms" in content
        assert "brands" in content
        assert "parameter_patterns" in content

    def test_idempotent_when_already_exists(self, tmp_workspace: Path) -> None:
        ws = WorkspaceConfig(root=tmp_workspace)
        create_system_dirs(ws, "system-B")

        # User edits the yaml
        yaml_file = (
            tmp_workspace / "config" / "systems" / "system-B" / "blacklists" / "system.yaml"
        )
        yaml_file.write_text("custom: true\n", encoding="utf-8")

        created_again = create_system_dirs(ws, "system-B")

        assert created_again is False
        # User's edit is preserved
        assert yaml_file.read_text(encoding="utf-8") == "custom: true\n"

    def test_falls_back_to_embedded_template_when_defaults_missing(
        self, tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Point the template resolver at a non-existent path
        import doc_bridge.utils.system_ops as mod

        monkeypatch.setattr(mod, "_template_path", lambda: Path("/nonexistent/x.yaml"))

        ws = WorkspaceConfig(root=tmp_workspace)
        create_system_dirs(ws, "system-C")

        yaml_file = (
            tmp_workspace / "config" / "systems" / "system-C" / "blacklists" / "system.yaml"
        )
        assert yaml_file.is_file()
        content = yaml_file.read_text(encoding="utf-8")
        assert "tech_terms" in content
