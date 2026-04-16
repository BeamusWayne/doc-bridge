"""doc-bridge synthesize command."""

from __future__ import annotations

import asyncio
from datetime import datetime

import click

from doc_bridge.core.synthesizer import synthesize_system
from doc_bridge.llm.client import LLMClient
from doc_bridge.llm.logger import LLMCallLogger, setup_flow_logger
from doc_bridge.models.config import LLMConfig
from doc_bridge.utils.workspace import list_systems, resolve_workspace


@click.command("synthesize")
@click.option("--system", default=None, help="系统名（不指定则处理所有系统）")
@click.option("--no-dedup", is_flag=True, default=False, help="跳过 LLM 去重步骤")
@click.option("--concurrency", default=5, help="LLM 并发数")
def synthesize_cmd(system: str | None, no_dedup: bool, concurrency: int) -> None:
    """合成: 将原子文件聚合为总表。"""
    asyncio.run(_synthesize(system, no_dedup, concurrency))


async def _synthesize(system: str | None, no_dedup: bool, concurrency: int) -> None:
    ws = resolve_workspace()
    ws.validate()

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    log_dir = ws.logs_dir / timestamp
    flow_logger = setup_flow_logger(log_dir, "synthesize")
    llm_logger = LLMCallLogger(log_dir)

    llm_config = None
    client = None

    if not no_dedup:
        try:
            llm_config = LLMConfig.from_env(ws.root)
            semaphore = asyncio.Semaphore(concurrency)
            client = LLMClient(llm_config, llm_logger, semaphore)
        except ValueError as e:
            flow_logger.warning(f"LLM 配置失败，将跳过去重: {e}")

    systems = [system] if system else list_systems(ws)
    if not systems:
        click.echo("未找到任何系统。请先将文档放入 raw/<系统名>/ 目录。")
        return

    # Synthesize all systems concurrently
    tasks = [
        synthesize_system(
            ws, s, llm_config, client,
            do_dedup=(not no_dedup),
            flow_logger=flow_logger,
        )
        for s in systems
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for s, result in zip(systems, results):
        if isinstance(result, Exception):
            flow_logger.error(f"合成失败 {s}: {result}")
            click.echo(f"警告: {s} 合成失败: {result}")
        else:
            click.echo(
                f"{s}: 术语 {result['glossary']} / "
                f"实体 {result['entities']} / "
                f"数据流 {result['data_flows']}"
            )

    click.echo(f"\n合成完成! 日志: {log_dir}")
    llm_logger.close()
