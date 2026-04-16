"""Pydantic-based structural validation for LLM extraction output."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from doc_bridge.models.atom import (
    DataFlowItem,
    EntityItem,
    GlossaryItem,
    LLMExtractionResult,
)

logger = logging.getLogger("doc_bridge.validation")


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract JSON from LLM response text (handles markdown code fences)."""
    text = raw.strip()
    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end])

    return json.loads(text)


def validate_extraction(raw_json: dict[str, Any], total_paragraphs: int) -> LLMExtractionResult:
    """Validate LLM extraction output against Pydantic models.

    Raises ValidationError on structural failures.
    """
    result = LLMExtractionResult.model_validate(raw_json)

    errors: list[str] = []

    # Validate paragraph bounds
    for item_list_name in ("glossary", "entities", "data_flows"):
        items = getattr(result, item_list_name)
        for item in items:
            for p in item.paragraphs:
                if p > total_paragraphs:
                    errors.append(
                        f"{item.name}: 段落编号 §{p} 超出源文件范围 "
                        f"(共 {total_paragraphs} 段)"
                    )

    if errors:
        raise ValidationError.from_exception_data(
            title="ParagraphBoundsError",
            line_errors=[],
        )

    return result


def validate_single_glossary(data: dict[str, Any]) -> GlossaryItem:
    return GlossaryItem.model_validate(data)


def validate_single_entity(data: dict[str, Any]) -> EntityItem:
    return EntityItem.model_validate(data)


def validate_single_dataflow(data: dict[str, Any]) -> DataFlowItem:
    return DataFlowItem.model_validate(data)
