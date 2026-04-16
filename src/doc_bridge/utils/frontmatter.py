"""YAML frontmatter read/write utilities for atom files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter


def read_atom_file(path: Path) -> tuple[dict[str, Any], str]:
    """Read an atom file and return (metadata_dict, body_content)."""
    post = frontmatter.load(str(path))
    return dict(post.metadata), post.content


def write_atom_file(path: Path, metadata: dict[str, Any], body: str) -> None:
    """Write an atom file with YAML frontmatter + markdown body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(body, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def update_backlinks(path: Path, backlinks: list[str]) -> None:
    """Update synthesis_backlinks in an atom file's frontmatter and body."""
    metadata, body = read_atom_file(path)
    metadata["synthesis_backlinks"] = backlinks

    # Remove old backlink section from body
    marker = "## 关联总表"
    if marker in body:
        body = body[:body.index(marker)].rstrip()

    # Append new backlink section
    if backlinks:
        lines = [f"\n\n{marker}\n", "<!-- 合成阶段自动生成，请勿手动编辑 -->"]
        for link in backlinks:
            name = Path(link).stem
            lines.append(f"- [{name}]({link})")
        body += "\n".join(lines) + "\n"

    write_atom_file(path, metadata, body)
