"""Document to Markdown conversion using markitdown (no LLM)."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from doc_bridge.models.config import WorkspaceConfig

logger = logging.getLogger("doc_bridge.converter")


def _convert_single(src: Path, dst: Path) -> tuple[str, bool, str]:
    """Convert a single file. Runs in a worker process."""
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(src))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(result.text_content, encoding="utf-8")
        return src.name, True, ""
    except Exception as e:
        return src.name, False, str(e)


def convert_files(
    ws: WorkspaceConfig,
    system: str,
    files: list[Path],
    flow_logger: logging.Logger,
) -> list[tuple[Path, Path]]:
    """Convert raw files to markdown using ProcessPoolExecutor.

    Returns list of (raw_path, markdown_path) for successfully converted files.
    """
    md_dir = ws.system_markdown_dir(system)
    md_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[Path, Path]] = []
    for f in files:
        dst = md_dir / f"{f.stem}.md"
        tasks.append((f, dst))

    if not tasks:
        return []

    results: list[tuple[Path, Path]] = []
    max_workers = min(len(tasks), 4)

    flow_logger.info(f"转换开始: {len(tasks)} 个文件, workers={max_workers}")

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_convert_single, src, dst): (src, dst)
            for src, dst in tasks
        }
        for future in as_completed(futures):
            src, dst = futures[future]
            name, success, error = future.result()
            if success:
                flow_logger.info(f"转换完成: {name} → {dst.name}")
                results.append((src, dst))
            else:
                flow_logger.error(f"转换失败: {name} — {error}")

    return results
