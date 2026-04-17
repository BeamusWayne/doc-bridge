"""System-management helpers for add-system command and atomize error branch."""

from __future__ import annotations

import difflib
from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig

_FORBIDDEN_CHARS = frozenset(" /\\.")
_RESERVED_NAMES = frozenset({".", ".."})
_MAX_NAME_LEN = 64

_EMBEDDED_BLACKLIST_TEMPLATE = (
    "# 系统专用黑名单 - 与 config/blacklists/global.yaml 取并集\n"
    "tech_terms: []          # 例: [\"SomeSystemSpecificTerm\"]\n"
    "brands: []              # 例: [\"某特定供应商\"]\n"
    "parameter_patterns: []  # 正则，例: [\"^PARAM_.*$\"]\n"
)


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


def suggest_close_system(name: str, existing: list[str]) -> str | None:
    """Return the single closest existing system name, or None if no reasonable match."""
    matches = difflib.get_close_matches(name, existing, n=1, cutoff=0.6)
    return matches[0] if matches else None


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
