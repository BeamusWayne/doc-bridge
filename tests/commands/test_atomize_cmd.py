"""Tests for atomize error branch when system does not exist."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from doc_bridge.commands.atomize_cmd import atomize_cmd


@pytest.fixture
def runner_in_workspace(tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.chdir(tmp_workspace)
    # Avoid env-based LLM lookup crashing tests before we reach the branch under test
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test")
    return CliRunner()


class TestAtomizeMissingSystem:
    def test_empty_workspace_hints_add_system(
        self, runner_in_workspace: CliRunner
    ) -> None:
        result = runner_in_workspace.invoke(atomize_cmd, ["--system", "system-B"])

        assert result.exit_code == 1
        assert "工作空间还没有" in result.output
        assert "doc-bridge add-system" in result.output

    def test_typo_suggests_close_match(
        self, runner_in_workspace: CliRunner, tmp_workspace: Path
    ) -> None:
        (tmp_workspace / "raw" / "system-A").mkdir()
        (tmp_workspace / "raw" / "ps").mkdir()

        result = runner_in_workspace.invoke(atomize_cmd, ["--system", "sytem-A"])

        assert result.exit_code == 1
        assert "你是不是想: system-A" in result.output
        assert "已有系统:" in result.output

    def test_no_close_match_omits_suggestion(
        self, runner_in_workspace: CliRunner, tmp_workspace: Path
    ) -> None:
        (tmp_workspace / "raw" / "system-A").mkdir()
        (tmp_workspace / "raw" / "ps").mkdir()

        result = runner_in_workspace.invoke(atomize_cmd, ["--system", "zzz"])

        assert result.exit_code == 1
        assert "你是不是想" not in result.output
        assert "已有系统:" in result.output
