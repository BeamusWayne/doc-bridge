"""Prompt loading with system-level > global-level priority."""

from __future__ import annotations

import re
from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig


PROMPT_NAMES = [
    "entity_extraction",
    "dataflow_extraction",
    "glossary_extraction",
]

SYNTHESIS_PROMPT_NAMES = [
    "glossary_synthesis",
    "entity_synthesis",
    "dataflow_synthesis",
]


def _extract_version(text: str) -> str:
    match = re.search(r"<!--\s*version:\s*(v[\d.]+)\s*-->", text)
    return match.group(1) if match else "v1.0"


def load_prompt(ws: WorkspaceConfig, prompt_name: str, system: str) -> tuple[str, str, str]:
    """Load a prompt by name with system-level override.

    Returns (prompt_text, prompt_file_path_relative, version).
    """
    system_path = ws.system_prompts_dir(system) / f"{prompt_name}.md"
    global_path = ws.prompts_dir / f"{prompt_name}.md"

    if system_path.exists():
        text = system_path.read_text(encoding="utf-8")
        rel = str(system_path.relative_to(ws.root))
        return text, rel, _extract_version(text)

    if global_path.exists():
        text = global_path.read_text(encoding="utf-8")
        rel = str(global_path.relative_to(ws.root))
        return text, rel, _extract_version(text)

    raise FileNotFoundError(
        f"找不到提示词文件: {prompt_name}.md\n"
        f"已检查: {system_path}, {global_path}"
    )


def load_synthesis_prompt(ws: WorkspaceConfig, prompt_name: str, system: str) -> tuple[str, str, str]:
    """Load a synthesis prompt. Same priority logic."""
    system_path = ws.system_prompts_dir(system) / "synthesis" / f"{prompt_name}.md"
    global_path = ws.prompts_dir / "synthesis" / f"{prompt_name}.md"

    if system_path.exists():
        text = system_path.read_text(encoding="utf-8")
        rel = str(system_path.relative_to(ws.root))
        return text, rel, _extract_version(text)

    if global_path.exists():
        text = global_path.read_text(encoding="utf-8")
        rel = str(global_path.relative_to(ws.root))
        return text, rel, _extract_version(text)

    raise FileNotFoundError(
        f"找不到合成提示词文件: {prompt_name}.md\n"
        f"已检查: {system_path}, {global_path}"
    )


def list_effective_prompts(ws: WorkspaceConfig, system: str | None) -> dict[str, dict[str, str]]:
    """List all prompts and which file is effective for a given system."""
    result: dict[str, dict[str, str]] = {}

    all_names = PROMPT_NAMES + [f"synthesis/{n}" for n in SYNTHESIS_PROMPT_NAMES]

    for name in all_names:
        entry: dict[str, str] = {}
        global_path = ws.prompts_dir / f"{name}.md"
        entry["global"] = str(global_path.relative_to(ws.root)) if global_path.exists() else "(未找到)"

        if system:
            system_path = ws.systems_config_dir / system / "prompts" / f"{name}.md"
            if system_path.exists():
                entry["effective"] = f"{system_path.relative_to(ws.root)} (系统级)"
            else:
                entry["effective"] = f"{entry['global']} (通用，无系统级覆盖)"
        else:
            entry["effective"] = entry["global"]

        result[name] = entry

    return result
