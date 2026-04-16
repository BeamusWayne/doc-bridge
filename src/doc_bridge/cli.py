"""Doc-Bridge CLI entry point."""

import click

from doc_bridge.commands.atomize_cmd import atomize_cmd
from doc_bridge.commands.init_cmd import init_cmd
from doc_bridge.commands.prompts_cmd import prompts_cmd
from doc_bridge.commands.status_cmd import status_cmd
from doc_bridge.commands.synthesize_cmd import synthesize_cmd


@click.group()
@click.version_option(package_name="doc-bridge")
def main() -> None:
    """Doc-Bridge: 文档原子化与合成系统"""
    pass


main.add_command(init_cmd)
main.add_command(atomize_cmd)
main.add_command(synthesize_cmd)
main.add_command(status_cmd)
main.add_command(prompts_cmd)


if __name__ == "__main__":
    main()
