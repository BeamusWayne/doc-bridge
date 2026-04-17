"""System-management helpers for add-system command and atomize error branch."""

from __future__ import annotations

import difflib

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


def suggest_close_system(name: str, existing: list[str]) -> str | None:
    """Return the single closest existing system name, or None if no reasonable match."""
    matches = difflib.get_close_matches(name, existing, n=1, cutoff=0.6)
    return matches[0] if matches else None
