"""doc-bridge atomize command."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import click

from doc_bridge.core.converter import convert_files
from doc_bridge.core.extractor import extract_document
from doc_bridge.core.state import (
    load_state,
    mark_processed,
    needs_processing,
    save_state,
)
from doc_bridge.llm.client import LLMClient
from doc_bridge.llm.logger import LLMCallLogger, setup_flow_logger
from doc_bridge.llm.prompt_loader import load_prompt
from doc_bridge.models.config import LLMConfig, WorkspaceConfig
from doc_bridge.utils.system_ops import suggest_close_system
from doc_bridge.utils.workspace import list_raw_files, list_systems, resolve_workspace


@click.command("atomize")
@click.option("--system", required=True, help="系统名（对应 raw/ 下的子目录名）")
@click.option("--file", "filename", default=None, help="指定单个文件名")
@click.option("--force", is_flag=True, default=False, help="强制全量重新处理")
@click.option("--concurrency", default=5, help="LLM 并发数")
def atomize_cmd(system: str, filename: str | None, force: bool, concurrency: int) -> None:
    """原子化: 将文档转为 Markdown 并抽取实体、数据流、术语。"""
    asyncio.run(_atomize(system, filename, force, concurrency))


async def _atomize(
    system: str, filename: str | None, force: bool, concurrency: int,
) -> None:
    ws = resolve_workspace()
    ws.validate()

    # Check system directory exists; produce a helpful error otherwise.
    raw_dir = ws.system_raw_dir(system)
    if not raw_dir.exists():
        _emit_missing_system_error(ws, system)
        raise SystemExit(1)

    # Setup logging
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    log_dir = ws.logs_dir / timestamp
    flow_logger = setup_flow_logger(log_dir, "atomize")
    llm_logger = LLMCallLogger(log_dir)

    try:
        llm_config = LLMConfig.from_env(ws.root)
    except ValueError as e:
        click.echo(f"错误: {e}")
        raise SystemExit(1)

    semaphore = asyncio.Semaphore(concurrency)
    client = LLMClient(llm_config, llm_logger, semaphore)

    # Determine files to process
    all_files = list_raw_files(ws, system)
    if filename:
        all_files = [f for f in all_files if f.name == filename]
        if not all_files:
            click.echo(f"错误: 文件未找到: {raw_dir / filename}")
            raise SystemExit(1)

    # Incremental check
    state = load_state(ws)
    prompt_versions = _get_prompt_versions(ws, system)

    if force:
        files_to_process = all_files
    else:
        files_to_process = [
            f for f in all_files
            if needs_processing(ws, state, system, f, prompt_versions)
        ]

    flow_logger.info(
        f"开始原子化: system={system}, "
        f"mode={'full' if force else 'incremental'}, "
        f"total={len(all_files)}, to_process={len(files_to_process)}"
    )

    if not files_to_process:
        click.echo("所有文件均已处理，无需更新。使用 --force 强制重新处理。")
        return

    click.echo(f"待处理文件: {len(files_to_process)} 个")

    # Phase 1: Convert to markdown
    converted = convert_files(ws, system, files_to_process, flow_logger)

    if not converted:
        flow_logger.error("所有文件转换失败")
        click.echo("错误: 所有文件转换失败，请查看日志")
        return

    # Phase 2-5: LLM extraction
    total_counts = {"entities": 0, "data_flows": 0, "glossary": 0}

    for raw_path, md_path in converted:
        try:
            counts = await extract_document(
                ws, llm_config, client, system, raw_path, md_path, flow_logger,
            )
            for k, v in counts.items():
                total_counts[k] += v

            mark_processed(state, system, raw_path, prompt_versions)
            save_state(ws, state)

        except Exception as e:
            flow_logger.error(f"抽取失败 {raw_path.name}: {e}")
            click.echo(f"警告: {raw_path.name} 抽取失败: {e}")

    flow_logger.info(
        f"原子化完成: entities={total_counts['entities']}, "
        f"data_flows={total_counts['data_flows']}, "
        f"glossary={total_counts['glossary']}"
    )

    click.echo(
        f"\n原子化完成!\n"
        f"  实体: {total_counts['entities']}\n"
        f"  数据流: {total_counts['data_flows']}\n"
        f"  术语: {total_counts['glossary']}\n"
        f"  日志: {log_dir}"
    )

    llm_logger.close()


def _get_prompt_versions(ws: WorkspaceConfig, system: str) -> dict[str, str]:
    """Get current prompt versions for incremental check."""
    versions = {}
    for name in ["entity_extraction", "dataflow_extraction", "glossary_extraction"]:
        try:
            _, _, version = load_prompt(ws, name, system)
            versions[name] = version
        except FileNotFoundError:
            versions[name] = "unknown"
    return versions


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
