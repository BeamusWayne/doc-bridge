"""Shared pytest fixtures for doc-bridge tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create an initialised workspace skeleton in a temp directory."""
    (tmp_path / "config" / "prompts").mkdir(parents=True)
    (tmp_path / "config" / "blacklists").mkdir(parents=True)
    (tmp_path / "config" / "systems").mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    (tmp_path / "markdown").mkdir()
    (tmp_path / "atoms").mkdir()
    (tmp_path / "synthesis").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path
