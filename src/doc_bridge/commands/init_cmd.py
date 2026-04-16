"""doc-bridge init command."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

import click


@click.command("init")
def init_cmd() -> None:
    """初始化当前目录为 Doc-Bridge 工作空间。"""
    root = Path.cwd()

    # Create directory structure
    dirs = ["config/prompts/synthesis", "config/blacklists", "raw", "markdown",
            "atoms", "synthesis", "logs"]
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)

    # Copy default files from the package's defaults/ directory
    defaults_src = Path(__file__).resolve().parent.parent.parent.parent / "defaults"

    if not defaults_src.exists():
        # Fallback: look relative to the installed package
        click.echo("警告: 未找到 defaults/ 目录，使用内置默认内容")
        _write_builtin_defaults(root)
        return

    # Copy prompts
    prompts_src = defaults_src / "prompts"
    prompts_dst = root / "config" / "prompts"
    if prompts_src.exists():
        for f in prompts_src.rglob("*.md"):
            rel = f.relative_to(prompts_src)
            dst = prompts_dst / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)

    # Copy blacklists
    bl_src = defaults_src / "blacklists" / "global.yaml"
    bl_dst = root / "config" / "blacklists" / "global.yaml"
    if bl_src.exists() and not bl_dst.exists():
        shutil.copy2(bl_src, bl_dst)

    # Copy .env template
    env_template = defaults_src / ".env.template"
    env_dst = root / ".env"
    if env_template.exists():
        tpl_dst = root / ".env.template"
        if not tpl_dst.exists():
            shutil.copy2(env_template, tpl_dst)
        if not env_dst.exists():
            shutil.copy2(env_template, env_dst)

    click.echo("工作空间初始化完成!")
    click.echo(f"  根目录: {root}")
    click.echo("  请将原始文档放入 raw/<系统名>/ 目录")
    click.echo("  请编辑 .env 文件配置 LLM 参数")


def _write_builtin_defaults(root: Path) -> None:
    """Write minimal built-in defaults when defaults/ dir is not found."""
    # .env template
    env_content = (
        "ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic\n"
        "ANTHROPIC_API_KEY=your_api_key_here\n"
        "ANTHROPIC_MODEL=glm-5\n"
    )
    env_path = root / ".env"
    if not env_path.exists():
        env_path.write_text(env_content, encoding="utf-8")
    tpl_path = root / ".env.template"
    if not tpl_path.exists():
        tpl_path.write_text(env_content, encoding="utf-8")

    click.echo("已生成最小默认配置，请手动创建提示词文件")
