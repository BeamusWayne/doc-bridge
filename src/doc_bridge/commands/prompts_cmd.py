"""doc-bridge prompts command."""

from __future__ import annotations

import click

from doc_bridge.llm.prompt_loader import list_effective_prompts
from doc_bridge.utils.workspace import resolve_workspace


@click.command("prompts")
@click.option("--system", default=None, help="查看指定系统的生效提示词")
def prompts_cmd(system: str | None) -> None:
    """列出提示词文件及其覆盖关系。"""
    ws = resolve_workspace()
    try:
        ws.validate()
    except FileNotFoundError as e:
        click.echo(str(e))
        return

    effective = list_effective_prompts(ws, system)

    for name, info in effective.items():
        click.echo(f"\n{name}:")
        click.echo(f"  生效: {info['effective']}")
        if system and info.get("global"):
            click.echo(f"  通用: {info['global']}")
