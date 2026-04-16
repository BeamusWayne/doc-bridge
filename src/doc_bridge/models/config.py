"""Configuration data models."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls, workspace: Path) -> LLMConfig:
        env_path = workspace / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)

        base_url = os.getenv("ANTHROPIC_BASE_URL", "")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model = os.getenv("ANTHROPIC_MODEL", "")

        if not all([base_url, api_key, model]):
            missing = []
            if not base_url:
                missing.append("ANTHROPIC_BASE_URL")
            if not api_key:
                missing.append("ANTHROPIC_API_KEY")
            if not model:
                missing.append("ANTHROPIC_MODEL")
            raise ValueError(
                f".env 缺少必要配置: {', '.join(missing)}\n"
                f"请检查 {env_path}"
            )

        return cls(base_url=base_url, api_key=api_key, model=model)


@dataclass(frozen=True)
class WorkspaceConfig:
    root: Path

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def prompts_dir(self) -> Path:
        return self.config_dir / "prompts"

    @property
    def blacklists_dir(self) -> Path:
        return self.config_dir / "blacklists"

    @property
    def systems_config_dir(self) -> Path:
        return self.config_dir / "systems"

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def markdown_dir(self) -> Path:
        return self.root / "markdown"

    @property
    def atoms_dir(self) -> Path:
        return self.root / "atoms"

    @property
    def synthesis_dir(self) -> Path:
        return self.root / "synthesis"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def state_file(self) -> Path:
        return self.root / ".doc-bridge-state.json"

    def system_prompts_dir(self, system: str) -> Path:
        return self.systems_config_dir / system / "prompts"

    def system_blacklists_dir(self, system: str) -> Path:
        return self.systems_config_dir / system / "blacklists"

    def system_raw_dir(self, system: str) -> Path:
        return self.raw_dir / system

    def system_markdown_dir(self, system: str) -> Path:
        return self.markdown_dir / system

    def system_atoms_dir(self, system: str) -> Path:
        return self.atoms_dir / system

    def system_synthesis_dir(self, system: str) -> Path:
        return self.synthesis_dir / system

    def validate(self) -> None:
        required = [self.config_dir, self.prompts_dir, self.raw_dir]
        for d in required:
            if not d.exists():
                raise FileNotFoundError(
                    f"工作空间未初始化: 缺少 {d.relative_to(self.root)}\n"
                    f"请先运行: doc-bridge init"
                )
