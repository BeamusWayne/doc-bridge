"""Workspace path resolution utilities."""

from __future__ import annotations

from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig


def resolve_workspace(path: str | Path | None = None) -> WorkspaceConfig:
    root = Path(path) if path else Path.cwd()
    root = root.resolve()
    return WorkspaceConfig(root=root)


def list_systems(ws: WorkspaceConfig) -> list[str]:
    if not ws.raw_dir.exists():
        return []
    return sorted(
        d.name for d in ws.raw_dir.iterdir() if d.is_dir()
    )


def list_raw_files(ws: WorkspaceConfig, system: str) -> list[Path]:
    raw_dir = ws.system_raw_dir(system)
    if not raw_dir.exists():
        return []
    suffixes = {".docx", ".pdf", ".doc"}
    return sorted(
        f for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in suffixes
    )


def atom_dir_for_file(ws: WorkspaceConfig, system: str, filename: str) -> Path:
    stem = Path(filename).stem
    return ws.system_atoms_dir(system) / stem


def relative_link(from_file: Path, to_file: Path) -> str:
    """Compute markdown relative link path between two files."""
    try:
        rel = to_file.relative_to(from_file.parent)
        return str(rel)
    except ValueError:
        # Not a sub-path; compute relative manually
        from_parts = from_file.parent.parts
        to_parts = to_file.parts
        # Find common prefix length
        common = 0
        for a, b in zip(from_parts, to_parts):
            if a == b:
                common += 1
            else:
                break
        ups = len(from_parts) - common
        downs = to_parts[common:]
        return str(Path(*( [".."] * ups + list(downs) )))
