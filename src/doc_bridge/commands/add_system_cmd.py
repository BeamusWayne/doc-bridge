"""doc-bridge add-system command."""

from __future__ import annotations

import click

from doc_bridge.utils.system_ops import (
    create_system_dirs,
    validate_system_name,
)
from doc_bridge.utils.workspace import resolve_workspace


@click.command("add-system")
@click.argument("name")
def add_system_cmd(name: str) -> None:
    """新增一个系统：创建 raw/ 目录和 config/systems/ 专用配置脚手架。"""
    ws = resolve_workspace()

    try:
        ws.validate()
    except FileNotFoundError as e:
        click.echo(f"错误: {e}")
        raise SystemExit(1)

    try:
        validate_system_name(name)
    except ValueError as e:
        click.echo(f"错误: {e}")
        raise SystemExit(1)

    try:
        created = create_system_dirs(ws, name)
    except OSError as e:
        click.echo(f"错误: 创建目录失败: {e}")
        raise SystemExit(1)

    raw_rel = ws.system_raw_dir(name).relative_to(ws.root)
    cfg_rel = (ws.systems_config_dir / name).relative_to(ws.root)

    if not created:
        click.echo(f"系统 {name!r} 已存在: {raw_rel}/")
        return

    click.echo(
        f"系统已创建: {name}\n"
        f"  原始文档: {raw_rel}/\n"
        f"  专用配置: {cfg_rel}/\n"
        f"下一步: 把文档放入 {raw_rel}/，然后运行 doc-bridge atomize --system {name}"
    )
