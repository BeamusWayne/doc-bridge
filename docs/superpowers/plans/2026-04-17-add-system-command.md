# `add-system` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `doc-bridge add-system <name>` command that creates all directories a new system needs, and enhance `atomize --system <name>` to suggest close matches on typos instead of failing hard.

**Architecture:** Three pure functions in a new `utils/system_ops.py` module (`validate_system_name`, `suggest_close_system`, `create_system_dirs`), plus a thin Click command in `commands/add_system_cmd.py` that wires them together. The existing `utils/workspace.list_systems` is reused for enumerating systems — no duplicate listing helper. `atomize_cmd.py`'s error branch is replaced with a call to the same helpers.

**Tech Stack:** Python 3.10+, Click 8, stdlib `difflib` for fuzzy matching, pytest + Click's `CliRunner` for tests. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-04-17-add-system-command-design.md`

---

## File Structure

### New

| Path | Purpose |
|---|---|
| `src/doc_bridge/utils/system_ops.py` | `validate_system_name`, `suggest_close_system`, `create_system_dirs` |
| `src/doc_bridge/commands/add_system_cmd.py` | Click command |
| `defaults/system_blacklist.template.yaml` | Per-system blacklist seed |
| `tests/conftest.py` | `tmp_workspace` fixture |
| `tests/utils/test_system_ops.py` | Unit tests for three helpers |
| `tests/commands/test_add_system_cmd.py` | `CliRunner` tests |
| `tests/commands/test_atomize_cmd.py` | Tests for the new error branch only |

### Modified

| Path | Change |
|---|---|
| `pyproject.toml` | Add `[project.optional-dependencies].dev` with `pytest`, `pytest-cov` |
| `src/doc_bridge/cli.py` | Import + register `add_system_cmd` |
| `src/doc_bridge/commands/atomize_cmd.py:44-47` | Replace hard error with suggestion message |
| `README.md` | Add `add-system` row to the command table; update "加新系统" flow |

---

## Task 0: Setup — pytest + test skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/utils/__init__.py` (empty)
- Create: `tests/commands/__init__.py` (empty)

- [ ] **Step 1: Add dev dependencies**

Modify `pyproject.toml`. After the `dependencies = [...]` block, insert:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Install dev extras**

Run: `source .venv/bin/activate && pip install -e '.[dev]'`
Expected: `pytest` and `pytest-cov` install without error.

- [ ] **Step 3: Create shared fixture**

Write `tests/conftest.py`:

```python
"""Shared pytest fixtures for doc-bridge tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create an initialised workspace skeleton in a temp directory."""
    (tmp_path / "config" / "prompts").mkdir(parents=True)
    (tmp_path / "config" / "blacklists").mkdir(parents=True)
    (tmp_path / "config" / "systems").mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    (tmp_path / "markdown").mkdir()
    (tmp_path / "atoms").mkdir()
    (tmp_path / "synthesis").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path
```

- [ ] **Step 4: Create empty package markers**

Create `tests/utils/__init__.py` (empty file).
Create `tests/commands/__init__.py` (empty file).

- [ ] **Step 5: Smoke-test pytest collection**

Run: `pytest --collect-only`
Expected: `collected 0 items` with no errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: add pytest + conftest skeleton"
```

---

## Task 1: `validate_system_name`

**Files:**
- Create: `src/doc_bridge/utils/system_ops.py`
- Test: `tests/utils/test_system_ops.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/utils/test_system_ops.py`:

```python
"""Unit tests for system_ops helpers."""

from __future__ import annotations

import pytest

from doc_bridge.utils.system_ops import validate_system_name


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/utils/test_system_ops.py -v`
Expected: `ImportError` or collection error (module does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `src/doc_bridge/utils/system_ops.py`:

```python
"""System-management helpers for add-system command and atomize error branch."""

from __future__ import annotations

_FORBIDDEN_CHARS = frozenset(" /\\.")
_RESERVED_NAMES = frozenset({".", ".."})
_MAX_NAME_LEN = 64


def validate_system_name(name: str) -> None:
    """Raise ValueError with a user-facing Chinese message if `name` is invalid.

    Rules:
        - non-empty
        - not in {".", ".."}
        - no space, "/", "\\", or "."
        - length <= 64
    """
    if not name:
        raise ValueError("系统名不能为空")
    if name in _RESERVED_NAMES:
        raise ValueError(f"系统名不能为保留字: {name!r}")
    if len(name) > _MAX_NAME_LEN:
        raise ValueError(f"系统名过长 (>{_MAX_NAME_LEN} 字符): {name!r}")
    bad = [c for c in _FORBIDDEN_CHARS if c in name]
    if bad:
        raise ValueError(
            f"系统名含非法字符 (空格 / 斜杠 / 反斜杠 / 点): {name!r}\n"
            f"允许: 字母 / 数字 / 连字符 / 下划线 / 中文"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/utils/test_system_ops.py::TestValidateSystemName -v`
Expected: all 14 parametrised cases PASS.

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/utils/system_ops.py tests/utils/test_system_ops.py
git commit -m "feat: validate_system_name helper with unit tests"
```

---

## Task 2: `suggest_close_system`

**Files:**
- Modify: `src/doc_bridge/utils/system_ops.py`
- Test: `tests/utils/test_system_ops.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/utils/test_system_ops.py`:

```python
from doc_bridge.utils.system_ops import suggest_close_system


class TestSuggestCloseSystem:
    def test_typo_matches_closest(self) -> None:
        assert suggest_close_system("sytem-A", ["system-A", "ps"]) == "system-A"

    def test_unrelated_returns_none(self) -> None:
        assert suggest_close_system("xyz", ["system-A", "ps"]) is None

    def test_empty_list_returns_none(self) -> None:
        assert suggest_close_system("anything", []) is None

    def test_exact_match_returns_match(self) -> None:
        assert suggest_close_system("ps", ["system-A", "ps"]) == "ps"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/utils/test_system_ops.py::TestSuggestCloseSystem -v`
Expected: `ImportError: cannot import name 'suggest_close_system'`.

- [ ] **Step 3: Append implementation**

Append to `src/doc_bridge/utils/system_ops.py`:

```python
import difflib


def suggest_close_system(name: str, existing: list[str]) -> str | None:
    """Return the single closest existing system name, or None if no reasonable match."""
    matches = difflib.get_close_matches(name, existing, n=1, cutoff=0.6)
    return matches[0] if matches else None
```

(Move the `import difflib` to the top of the file with other imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/utils/test_system_ops.py::TestSuggestCloseSystem -v`
Expected: all 4 cases PASS.

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/utils/system_ops.py tests/utils/test_system_ops.py
git commit -m "feat: suggest_close_system helper with unit tests"
```

---

## Task 3: `create_system_dirs` + blacklist template

**Files:**
- Create: `defaults/system_blacklist.template.yaml`
- Modify: `src/doc_bridge/utils/system_ops.py`
- Test: `tests/utils/test_system_ops.py`

> **Spec §12 note:** The planner verified during plan-writing that `core/converter.py` and `core/synthesizer.py` call `mkdir(parents=True, exist_ok=True)` on their own output dirs (`converter.py:21,39`; `synthesizer.py:217`). No downstream code assumes `markdown/<name>/`, `atoms/<name>/`, or `synthesis/<name>/` pre-exists. `create_system_dirs` therefore does **not** create those paths.

- [ ] **Step 1: Create the template file**

Write `defaults/system_blacklist.template.yaml`:

```yaml
# 系统专用黑名单 - 与 config/blacklists/global.yaml 取并集
tech_terms: []          # 例: ["SomeSystemSpecificTerm"]
brands: []              # 例: ["某特定供应商"]
parameter_patterns: []  # 正则，例: ["^PARAM_.*$"]
```

- [ ] **Step 2: Append failing tests**

Append to `tests/utils/test_system_ops.py`:

```python
from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig
from doc_bridge.utils.system_ops import create_system_dirs


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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/utils/test_system_ops.py::TestCreateSystemDirs -v`
Expected: `ImportError: cannot import name 'create_system_dirs'`.

- [ ] **Step 4: Append implementation**

Append to `src/doc_bridge/utils/system_ops.py`:

```python
from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig


_EMBEDDED_BLACKLIST_TEMPLATE = (
    "# 系统专用黑名单 - 与 config/blacklists/global.yaml 取并集\n"
    "tech_terms: []          # 例: [\"SomeSystemSpecificTerm\"]\n"
    "brands: []              # 例: [\"某特定供应商\"]\n"
    "parameter_patterns: []  # 正则，例: [\"^PARAM_.*$\"]\n"
)


def _template_path() -> Path:
    """Return the absolute path to the shipped blacklist template."""
    # system_ops.py is at src/doc_bridge/utils/system_ops.py; defaults/ is at repo root.
    return (
        Path(__file__).resolve().parent.parent.parent.parent
        / "defaults"
        / "system_blacklist.template.yaml"
    )


def _load_template() -> str:
    path = _template_path()
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return _EMBEDDED_BLACKLIST_TEMPLATE


def create_system_dirs(ws: WorkspaceConfig, name: str) -> bool:
    """Create the directory scaffolding for a new system.

    Creates:
        raw/<name>/
        config/systems/<name>/prompts/
        config/systems/<name>/blacklists/
        config/systems/<name>/blacklists/system.yaml  (from template, if absent)

    Returns True if the system was new (raw/<name>/ did not exist before),
    False if it already existed. Never overwrites an existing system.yaml.
    """
    raw = ws.system_raw_dir(name)
    is_new = not raw.exists()

    raw.mkdir(parents=True, exist_ok=True)
    ws.system_prompts_dir(name).mkdir(parents=True, exist_ok=True)
    bl_dir = ws.system_blacklists_dir(name)
    bl_dir.mkdir(parents=True, exist_ok=True)

    yaml_file = bl_dir / "system.yaml"
    if not yaml_file.exists():
        yaml_file.write_text(_load_template(), encoding="utf-8")

    return is_new
```

Also move the `from pathlib import Path` and `from doc_bridge.models.config import WorkspaceConfig` to the top of the file with the other imports, keeping imports grouped (stdlib, third-party, local).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/utils/test_system_ops.py::TestCreateSystemDirs -v`
Expected: all 3 cases PASS.

- [ ] **Step 6: Run full module tests**

Run: `pytest tests/utils/ -v`
Expected: all tests from Tasks 1, 2, 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add defaults/system_blacklist.template.yaml src/doc_bridge/utils/system_ops.py tests/utils/test_system_ops.py
git commit -m "feat: create_system_dirs helper + blacklist template"
```

---

## Task 4: `add-system` Click command

**Files:**
- Create: `src/doc_bridge/commands/add_system_cmd.py`
- Test: `tests/commands/test_add_system_cmd.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/commands/test_add_system_cmd.py`:

```python
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
        runner_in_workspace.invoke(add_system_cmd, ["system-B"])
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/commands/test_add_system_cmd.py -v`
Expected: `ImportError: cannot import name 'add_system_cmd'`.

- [ ] **Step 3: Write the command**

Create `src/doc_bridge/commands/add_system_cmd.py`:

```python
"""doc-bridge add-system command."""

from __future__ import annotations

import click

from doc_bridge.utils.system_ops import (
    create_system_dirs,
    validate_system_name,
)
from doc_bridge.utils.workspace import resolve_workspace


@click.command("add-system")
@click.argument("name")
def add_system_cmd(name: str) -> None:
    """新增一个系统：创建 raw/ 目录和 config/systems/ 专用配置脚手架。"""
    ws = resolve_workspace()

    try:
        ws.validate()
    except FileNotFoundError as e:
        click.echo(f"错误: {e}")
        raise SystemExit(1)

    try:
        validate_system_name(name)
    except ValueError as e:
        click.echo(f"错误: {e}")
        raise SystemExit(1)

    try:
        created = create_system_dirs(ws, name)
    except OSError as e:
        click.echo(f"错误: 创建目录失败: {e}")
        raise SystemExit(1)

    raw_rel = ws.system_raw_dir(name).relative_to(ws.root)
    cfg_rel = (ws.systems_config_dir / name).relative_to(ws.root)

    if not created:
        click.echo(f"系统 {name!r} 已存在: {raw_rel}/")
        return

    click.echo(
        f"系统已创建: {name}\n"
        f"  原始文档: {raw_rel}/\n"
        f"  专用配置: {cfg_rel}/\n"
        f"下一步: 把文档放入 {raw_rel}/，然后运行 doc-bridge atomize --system {name}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/commands/test_add_system_cmd.py -v`
Expected: all 6 cases PASS.

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/commands/add_system_cmd.py tests/commands/test_add_system_cmd.py
git commit -m "feat: add-system command creates system directories idempotently"
```

---

## Task 5: Register `add-system` in CLI

**Files:**
- Modify: `src/doc_bridge/cli.py`

- [ ] **Step 1: Register the command**

Edit `src/doc_bridge/cli.py`. Add the import after the other command imports:

```python
from doc_bridge.commands.add_system_cmd import add_system_cmd
```

And add the registration after the other `main.add_command(...)` lines:

```python
main.add_command(add_system_cmd)
```

Final file should look like:

```python
"""Doc-Bridge CLI entry point."""

import click

from doc_bridge.commands.add_system_cmd import add_system_cmd
from doc_bridge.commands.atomize_cmd import atomize_cmd
from doc_bridge.commands.init_cmd import init_cmd
from doc_bridge.commands.prompts_cmd import prompts_cmd
from doc_bridge.commands.status_cmd import status_cmd
from doc_bridge.commands.synthesize_cmd import synthesize_cmd


@click.group()
@click.version_option(package_name="doc-bridge")
def main() -> None:
    """Doc-Bridge: 文档原子化与合成系统"""
    pass


main.add_command(init_cmd)
main.add_command(add_system_cmd)
main.add_command(atomize_cmd)
main.add_command(synthesize_cmd)
main.add_command(status_cmd)
main.add_command(prompts_cmd)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the command is visible**

Run: `doc-bridge --help`
Expected: output includes the line `add-system  新增一个系统：创建 raw/ 目录和 config/systems/ 专用配置脚手架。`

Run: `doc-bridge add-system --help`
Expected: help shows `Usage: doc-bridge add-system [OPTIONS] NAME`.

- [ ] **Step 3: Commit**

```bash
git add src/doc_bridge/cli.py
git commit -m "feat: register add-system in CLI"
```

---

## Task 6: Replace atomize error branch

**Files:**
- Modify: `src/doc_bridge/commands/atomize_cmd.py:42-47`
- Test: `tests/commands/test_atomize_cmd.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/commands/test_atomize_cmd.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/commands/test_atomize_cmd.py -v`
Expected: all 3 cases FAIL (current branch emits different text and uses `SystemExit(1)` with a `mkdir` hint).

- [ ] **Step 3: Rewrite the error branch**

In `src/doc_bridge/commands/atomize_cmd.py`, replace lines 42-47 (the block starting `# Check system directory exists`) with:

```python
    # Check system directory exists; produce a helpful error otherwise.
    raw_dir = ws.system_raw_dir(system)
    if not raw_dir.exists():
        _emit_missing_system_error(ws, system)
        raise SystemExit(1)
```

Add at the top of the file, with the other imports:

```python
from doc_bridge.utils.system_ops import suggest_close_system
from doc_bridge.utils.workspace import list_raw_files, list_systems, resolve_workspace
```

(Merge the `list_systems` import into the existing `from doc_bridge.utils.workspace import ...` line rather than duplicating it.)

At the bottom of the file, after the existing `_get_prompt_versions` function, add:

```python
def _emit_missing_system_error(ws: WorkspaceConfig, system: str) -> None:
    """Print a helpful error for a missing system (typo-aware)."""
    existing = list_systems(ws)
    if not existing:
        click.echo(
            f"错误: 工作空间还没有任何系统。\n"
            f"  新增系统: doc-bridge add-system {system}"
        )
        return

    lines = [f"错误: 系统 {system!r} 不存在。"]
    close = suggest_close_system(system, existing)
    if close:
        lines.append(f"  你是不是想: {close}?")
    lines.append(f"  新增系统: doc-bridge add-system {system}")
    lines.append(f"  已有系统: {', '.join(existing)}")
    click.echo("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/test_atomize_cmd.py -v`
Expected: all 3 cases PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: all tests from Tasks 0-6 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/doc_bridge/commands/atomize_cmd.py tests/commands/test_atomize_cmd.py
git commit -m "feat: suggest close matches when atomize hits unknown system"
```

---

## Task 7: Update README

**Files:**
- Modify: `README.md:102-110` (command table)
- Modify: `README.md:55-60` (放入文档 section)

- [ ] **Step 1: Insert `add-system` in the command table**

Edit `README.md`. The current table is at lines 104-110:

```markdown
| 命令 | 说明 |
|------|------|
| `doc-bridge init` | 初始化当前目录为工作空间 |
| `doc-bridge atomize --system <name>` | 原子化指定系统的文档 |
| `doc-bridge synthesize --system <name>` | 合成指定系统的总表 |
| `doc-bridge status [--system <name>]` | 查看工作空间状态 |
| `doc-bridge prompts [--system <name>]` | 查看提示词覆盖关系 |
```

Replace with:

```markdown
| 命令 | 说明 |
|------|------|
| `doc-bridge init` | 初始化当前目录为工作空间 |
| `doc-bridge add-system <name>` | 新增一个系统：创建 raw/ 目录和 config/systems/ 脚手架 |
| `doc-bridge atomize --system <name>` | 原子化指定系统的文档 |
| `doc-bridge synthesize --system <name>` | 合成指定系统的总表 |
| `doc-bridge status [--system <name>]` | 查看工作空间状态 |
| `doc-bridge prompts [--system <name>]` | 查看提示词覆盖关系 |
```

- [ ] **Step 2: Replace the "放入文档" section**

In `README.md`, find the existing section:

- Heading: `### 放入文档`
- Body: a single `bash` fenced block containing `mkdir -p raw/system-A` and the `cp` line.

Replace the whole section (heading + fenced block) with a new `### 新增系统 + 放入文档` heading, a new `bash` fenced block containing `doc-bridge add-system system-A` and the same `cp` line, and a paragraph directly underneath that reads exactly:

> `add-system` 幂等，重跑也安全。如果你已经手工建好 `raw/system-A/`，`atomize` 同样能用；`add-system` 的好处是顺带把 `config/systems/system-A/` 脚手架也建起来，方便以后加系统专用提示词或黑名单。

- [ ] **Step 3: Verify rendering**

Run: `grep -n "add-system" README.md`
Expected: at least 3 matches (table row, two mentions in the new section).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document add-system command in README"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run the full test suite with coverage**

Run: `pytest --cov=src/doc_bridge --cov-report=term-missing`
Expected: all tests PASS, coverage on `utils/system_ops.py` and `commands/add_system_cmd.py` is >= 80%.

- [ ] **Step 2: Manual smoke test**

Run the following from a scratch workspace (NOT the source repo):

```bash
cd /tmp && rm -rf dbtest && mkdir dbtest && cd dbtest
doc-bridge init
doc-bridge add-system demo
ls raw/demo/ config/systems/demo/blacklists/system.yaml
doc-bridge add-system demo                       # should say 已存在
doc-bridge add-system "bad name"                 # should error
doc-bridge atomize --system dem                  # should suggest 'demo'
```

Expected outputs match the spec §4.

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin HEAD
gh pr create --title "feat: add-system command + atomize typo suggestions" --body "$(cat <<'EOF'
## Summary
- New `doc-bridge add-system <name>` command creates `raw/<name>/` and `config/systems/<name>/` scaffolding idempotently
- `atomize --system <name>` now suggests the closest existing system on typos instead of failing with a generic `mkdir` hint
- No new runtime dependencies; stdlib `difflib` only

## Test plan
- [ ] `pytest --cov=src/doc_bridge` passes with ≥80% coverage on new modules
- [ ] `doc-bridge add-system new-system` in a fresh workspace creates all expected directories
- [ ] `doc-bridge add-system new-system` on an existing system is idempotent (exit 0)
- [ ] `doc-bridge add-system "bad name"` rejects with non-zero exit and Chinese error
- [ ] `doc-bridge atomize --system typo` suggests close match and lists existing systems
EOF
)"
```

---

## Deferred (out of scope for this plan)

These are flagged in the spec §3 / §12 and explicitly not implemented here:

- `--from <existing-system>` flag to copy prompts from another system
- `--dry-run` flag
- End-to-end test that exercises the full `docx → LLM → synthesis` pipeline
- Integration with `init_cmd` to copy the blacklist template into the workspace (intentionally left at the package level; see spec §5)
