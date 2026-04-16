"""doc-bridge status command."""

from __future__ import annotations

from pathlib import Path

import click

from doc_bridge.utils.workspace import list_raw_files, list_systems, resolve_workspace


@click.command("status")
@click.option("--system", default=None, help="查看指定系统的详细状态")
def status_cmd(system: str | None) -> None:
    """显示工作空间状态。"""
    ws = resolve_workspace()
    try:
        ws.validate()
    except FileNotFoundError as e:
        click.echo(str(e))
        return

    systems = [system] if system else list_systems(ws)
    if not systems:
        click.echo("未找到任何系统。请将文档放入 raw/<系统名>/ 目录。")
        return

    for s in systems:
        raw_files = list_raw_files(ws, s)
        md_dir = ws.system_markdown_dir(s)
        atoms_dir = ws.system_atoms_dir(s)
        synthesis_dir = ws.system_synthesis_dir(s)

        # Count converted
        converted = []
        pending = []
        for f in raw_files:
            md_path = md_dir / f"{f.stem}.md"
            if md_path.exists():
                converted.append(f.stem)
            else:
                pending.append(f.name)

        # Count atoms
        entity_count = 0
        dataflow_count = 0
        glossary_count = 0
        if atoms_dir.exists():
            for doc_dir in atoms_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                e_dir = doc_dir / "entities"
                if e_dir.exists():
                    entity_count += len(list(e_dir.glob("*.md")))
                d_dir = doc_dir / "data-flow"
                if d_dir.exists():
                    dataflow_count += len(list(d_dir.glob("*.md")))
                g_dir = doc_dir / "glossary"
                if g_dir.exists():
                    glossary_count += len(list(g_dir.glob("*.md")))

        # Check synthesis
        has_synthesis = synthesis_dir.exists() and any(synthesis_dir.glob("*.md"))

        click.echo(f"\n{s}:")
        click.echo(f"  原始文档: {len(raw_files)} 个")

        if converted:
            click.echo(f"  已转换:   {len(converted)} 个 ({', '.join(converted)})")
        if pending:
            click.echo(f"  待转换:   {len(pending)} 个 ({', '.join(pending)})")

        extracted_count = len([d for d in (atoms_dir.iterdir() if atoms_dir.exists() else []) if d.is_dir()])
        if extracted_count:
            click.echo(
                f"  已抽取:   {extracted_count} 个 → "
                f"实体 {entity_count} / 数据流 {dataflow_count} / 术语 {glossary_count}"
            )
        else:
            click.echo("  已抽取:   0 个")

        click.echo(f"  已合成:   {'是' if has_synthesis else '否'}")
