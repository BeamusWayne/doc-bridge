"""Tests for add-system Click command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from doc_bridge.commands.add_system_cmd import add_system_cmd


@pytest.fixture
def runner_in_workspace(tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    """Run CliRunner with cwd set to an initialised workspace."""
    monkeypatch.chdir(tmp_workspace)
    return CliRunner()


class TestAddSystemCmd:
    def test_creates_new_system(
        self, runner_in_workspace: CliRunner, tmp_workspace: Path
    ) -> None:
        result = runner_in_workspace.invoke(add_system_cmd, ["system-B"])

        assert result.exit_code == 0, result.output
        assert (tmp_workspace / "raw" / "system-B").is_dir()
        assert (tmp_workspace / "config" / "systems" / "system-B" / "prompts").is_dir()
        assert "doc-bridge atomize" in result.output

    def test_idempotent_when_already_exists(
        self, runner_in_workspace: CliRunner, tmp_workspace: Path
    ) -> None:
        first = runner_in_workspace.invoke(add_system_cmd, ["system-B"])
        assert first.exit_code == 0, first.output

        result = runner_in_workspace.invoke(add_system_cmd, ["system-B"])

        assert result.exit_code == 0, result.output
        assert "已存在" in result.output

    def test_rejects_name_with_space(self, runner_in_workspace: CliRunner) -> None:
        result = runner_in_workspace.invoke(add_system_cmd, ["sys a"])

        assert result.exit_code == 1
        assert "非法字符" in result.output

    def test_rejects_empty_name(self, runner_in_workspace: CliRunner) -> None:
        result = runner_in_workspace.invoke(add_system_cmd, [""])

        assert result.exit_code == 1
        assert "不能为空" in result.output

    def test_accepts_chinese_name(
        self, runner_in_workspace: CliRunner, tmp_workspace: Path
    ) -> None:
        result = runner_in_workspace.invoke(add_system_cmd, ["系统一"])

        assert result.exit_code == 0, result.output
        assert (tmp_workspace / "raw" / "系统一").is_dir()

    def test_fails_outside_workspace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # tmp_path has no config/, raw/, etc.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(add_system_cmd, ["system-B"])

        assert result.exit_code == 1
        assert "未初始化" in result.output
