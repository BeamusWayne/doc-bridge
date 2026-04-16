"""Blacklist loading and matching — global + system-level merged."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from doc_bridge.models.config import WorkspaceConfig


@dataclass
class Blacklist:
    tech_terms: set[str] = field(default_factory=set)
    languages_and_frameworks: set[str] = field(default_factory=set)
    brands: set[str] = field(default_factory=set)
    common_words: set[str] = field(default_factory=set)
    parameter_patterns: list[re.Pattern] = field(default_factory=list)

    @property
    def _all_exact(self) -> set[str]:
        return (
            self.tech_terms
            | self.languages_and_frameworks
            | self.brands
            | self.common_words
        )

    def matches(self, name: str) -> tuple[bool, str]:
        """Check if a name matches the blacklist.

        Returns (is_match, reason).
        """
        name_lower = name.lower().strip()

        # Exact match (case-insensitive)
        for term in self._all_exact:
            if name_lower == term.lower():
                category = self._category_of(term)
                return True, f"blacklist:{category}"

        # Regex pattern match
        for pattern in self.parameter_patterns:
            if pattern.search(name):
                return True, f"blacklist:parameter_pattern({pattern.pattern})"

        return False, ""

    def _category_of(self, term: str) -> str:
        term_lower = term.lower()
        for t in self.tech_terms:
            if t.lower() == term_lower:
                return "tech_term"
        for t in self.languages_and_frameworks:
            if t.lower() == term_lower:
                return "language_or_framework"
        for t in self.brands:
            if t.lower() == term_lower:
                return "brand"
        for t in self.common_words:
            if t.lower() == term_lower:
                return "common_word"
        return "unknown"


def _load_yaml_blacklist(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _merge_into(bl: Blacklist, data: dict) -> None:
    bl.tech_terms.update(data.get("tech_terms", []))
    bl.languages_and_frameworks.update(data.get("languages_and_frameworks", []))
    bl.brands.update(data.get("brands", []))
    bl.common_words.update(data.get("common_words", []))
    for p in data.get("parameter_patterns", []):
        try:
            bl.parameter_patterns.append(re.compile(p))
        except re.error:
            pass  # Skip invalid patterns


def load_blacklist(ws: WorkspaceConfig, system: str) -> Blacklist:
    """Load merged blacklist: global ∪ system-level."""
    bl = Blacklist()

    global_path = ws.blacklists_dir / "global.yaml"
    _merge_into(bl, _load_yaml_blacklist(global_path))

    system_path = ws.system_blacklists_dir(system) / "system.yaml"
    _merge_into(bl, _load_yaml_blacklist(system_path))

    return bl
