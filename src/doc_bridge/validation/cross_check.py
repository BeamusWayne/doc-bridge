"""Cross-validation logic between different extraction types."""

from __future__ import annotations

import logging
import re
from typing import Any

from doc_bridge.models.atom import (
    DataFlowItem,
    EntityItem,
    GlossaryItem,
    LLMExtractionResult,
)
from doc_bridge.validation.blacklist import Blacklist

logger = logging.getLogger("doc_bridge.validation")

# Patterns for pure verbs (Chinese)
_PURE_VERB_PATTERN = re.compile(
    r"^(处理|传输|接收|发送|转发|读取|写入|删除|修改|更新|查询|计算|执行|运行|部署|配置|管理|监控|分析|验证)$"
)


def filter_by_blacklist(
    result: LLMExtractionResult,
    blacklist: Blacklist,
) -> tuple[LLMExtractionResult, list[dict[str, str]]]:
    """Filter extraction results through blacklist.

    Returns (filtered_result, list_of_filter_reasons).
    """
    filter_log: list[dict[str, str]] = []

    def _check(name: str, item_type: str) -> bool:
        matched, reason = blacklist.matches(name)
        if matched:
            filter_log.append({"name": name, "type": item_type, "reason": reason})
            return False
        # Entity-specific: reject pure verbs
        if item_type == "entity" and _PURE_VERB_PATTERN.match(name):
            filter_log.append({"name": name, "type": item_type, "reason": "pure_verb"})
            return False
        return True

    filtered_glossary = [g for g in result.glossary if _check(g.name, "glossary")]
    filtered_entities = [e for e in result.entities if _check(e.name, "entity")]
    filtered_flows = [f for f in result.data_flows if _check(f.name, "data-flow")]

    filtered = LLMExtractionResult(
        glossary=filtered_glossary,
        entities=filtered_entities,
        data_flows=filtered_flows,
    )
    return filtered, filter_log


def cross_validate(result: LLMExtractionResult) -> list[str]:
    """Run cross-validation checks. Returns list of warning messages."""
    warnings: list[str] = []

    # Check: entity and glossary name overlap
    entity_names = {e.name for e in result.entities}
    glossary_names = {g.name for g in result.glossary}
    overlap = entity_names & glossary_names
    for name in overlap:
        warnings.append(f"实体与术语重名: '{name}' 同时出现在 entities 和 glossary 中")

    # Check: data flow nodes should be known entities
    for flow in result.data_flows:
        all_nodes = [flow.source_entity, flow.target_entity] + flow.intermediate_entities
        for node in all_nodes:
            if node not in entity_names:
                warnings.append(
                    f"数据流 '{flow.name}' 的节点 '{node}' 未在实体列表中找到"
                )

    # Check: duplicates within same type
    seen_glossary: set[str] = set()
    for g in result.glossary:
        if g.name in seen_glossary:
            warnings.append(f"术语重复: '{g.name}'")
        seen_glossary.add(g.name)

    seen_entities: set[str] = set()
    for e in result.entities:
        if e.name in seen_entities:
            warnings.append(f"实体重复: '{e.name}'")
        seen_entities.add(e.name)

    return warnings
