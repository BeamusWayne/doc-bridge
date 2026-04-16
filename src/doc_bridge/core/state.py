"""Incremental processing state management."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from doc_bridge.models.config import WorkspaceConfig


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def load_state(ws: WorkspaceConfig) -> dict[str, Any]:
    if ws.state_file.exists():
        return json.loads(ws.state_file.read_text(encoding="utf-8"))
    return {}


def save_state(ws: WorkspaceConfig, state: dict[str, Any]) -> None:
    ws.state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def needs_processing(
    ws: WorkspaceConfig,
    state: dict[str, Any],
    system: str,
    raw_path: Path,
    prompt_versions: dict[str, str],
) -> bool:
    """Check if a file needs (re)processing."""
    system_state = state.get(system, {})
    file_state = system_state.get(raw_path.name, {})

    if not file_state:
        return True

    current_hash = _file_hash(raw_path)
    if file_state.get("file_hash") != current_hash:
        return True

    saved_versions = file_state.get("prompt_versions", {})
    for key, version in prompt_versions.items():
        if saved_versions.get(key) != version:
            return True

    return False


def mark_processed(
    state: dict[str, Any],
    system: str,
    raw_path: Path,
    prompt_versions: dict[str, str],
) -> None:
    if system not in state:
        state[system] = {}

    state[system][raw_path.name] = {
        "file_hash": _file_hash(raw_path),
        "converted_at": datetime.now().isoformat(),
        "extracted_at": datetime.now().isoformat(),
        "prompt_versions": prompt_versions,
    }
