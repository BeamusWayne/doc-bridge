"""LLM extraction orchestration — entity, dataflow, glossary."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from doc_bridge.core.chunker import Chunk, count_paragraphs, prepare_chunks
from doc_bridge.llm.client import LLMClient
from doc_bridge.llm.prompt_loader import load_prompt
from doc_bridge.models.atom import (
    DataFlowItem,
    EntityItem,
    GlossaryItem,
    LLMExtractionResult,
)
from doc_bridge.models.config import LLMConfig, WorkspaceConfig
from doc_bridge.models.provenance import ContextQuote, Provenance
from doc_bridge.utils.frontmatter import write_atom_file
from doc_bridge.utils.workspace import atom_dir_for_file
from doc_bridge.validation.blacklist import Blacklist, load_blacklist
from doc_bridge.validation.cross_check import cross_validate, filter_by_blacklist
from doc_bridge.validation.schema import parse_llm_json


logger = logging.getLogger("doc_bridge.extractor")


async def _extract_type(
    client: LLMClient,
    prompt_text: str,
    prompt_file: str,
    prompt_version: str,
    chunk: Chunk,
    extraction_type: str,
    source_file: str,
    system: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call LLM once for a specific extraction type on a chunk."""
    user_content = (
        f"以下是需要分析的文档内容（段落范围: §{chunk.start_paragraph}-§{chunk.end_paragraph}）:\n\n"
        f"{chunk.text}"
    )

    for attempt in range(max_retries):
        raw = await client.extract(
            system_prompt=prompt_text,
            user_content=user_content,
            step=extraction_type,
            source_file=source_file,
            system_name=system,
            prompt_file=prompt_file,
            prompt_version=prompt_version,
        )
        try:
            parsed = parse_llm_json(raw)
            return parsed
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"LLM输出JSON解析失败 (尝试 {attempt+1}/{max_retries}): {e}"
            )
            if attempt == max_retries - 1:
                logger.error(f"JSON解析在 {max_retries} 次重试后仍失败，跳过此块")
                return {}
    return {}


def _sanitize_filename(name: str) -> str:
    """Create a safe filename from a name string."""
    safe = name.replace("/", "_").replace("\\", "_").replace(":", "_")
    safe = safe.replace(" ", "_").replace("→", "_").replace("->", "_")
    safe = safe.replace('"', "").replace("'", "").replace("?", "")
    safe = safe.replace("<", "").replace(">", "").replace("|", "")
    if len(safe) > 80:
        safe = safe[:80]
    return safe


def _build_provenance(
    ws: WorkspaceConfig,
    raw_path: Path,
    md_path: Path,
    paragraphs: list[int],
    prompt_file: str,
    prompt_version: str,
    llm_model: str,
) -> Provenance:
    return Provenance(
        original_file=str(raw_path.relative_to(ws.root)),
        markdown_file=str(md_path.relative_to(ws.root)),
        paragraphs=paragraphs,
        extraction_prompt=prompt_file,
        extracted_at=datetime.now(),
        prompt_version=prompt_version,
        llm_model=llm_model,
    )


def _write_glossary_atom(
    ws: WorkspaceConfig,
    system: str,
    doc_stem: str,
    item: GlossaryItem,
) -> Path:
    atom_base = ws.system_atoms_dir(system) / doc_stem / "glossary"
    filename = _sanitize_filename(item.name) + ".md"
    path = atom_base / filename

    metadata = {
        "type": "glossary",
        "name": item.name,
        "domain": item.domain,
        "aliases": item.aliases,
        "provenance": item.provenance.model_dump(mode="json") if item.provenance else {},
        "synthesis_backlinks": [],
    }

    quotes = ""
    for q in item.context_quotes:
        quotes += f'> **§{q.paragraph}**: "{q.quote}"\n'

    aliases_text = ""
    if item.aliases:
        aliases_text = f"\n别名: {', '.join(item.aliases)}\n"

    body = (
        f"# {item.name}\n\n"
        f"## 定义\n\n{item.definition}\n{aliases_text}\n"
        f"## 原文上下文\n\n{quotes}"
    )

    write_atom_file(path, metadata, body)
    return path


def _write_entity_atom(
    ws: WorkspaceConfig,
    system: str,
    doc_stem: str,
    item: EntityItem,
) -> Path:
    atom_base = ws.system_atoms_dir(system) / doc_stem / "entities"
    filename = _sanitize_filename(item.name) + ".md"
    path = atom_base / filename

    metadata = {
        "type": "entity",
        "name": item.name,
        "description": item.description,
        "provenance": item.provenance.model_dump(mode="json") if item.provenance else {},
        "synthesis_backlinks": [],
    }

    responsibilities = ""
    if item.responsibilities:
        responsibilities = "\n## 职责\n\n"
        for r in item.responsibilities:
            responsibilities += f"- {r}\n"

    quotes = ""
    for q in item.context_quotes:
        quotes += f'> **§{q.paragraph}**: "{q.quote}"\n'

    body = (
        f"# {item.name}\n\n"
        f"## 描述\n\n{item.description}\n"
        f"{responsibilities}\n"
        f"## 原文上下文\n\n{quotes}"
    )

    write_atom_file(path, metadata, body)
    return path


def _write_dataflow_atom(
    ws: WorkspaceConfig,
    system: str,
    doc_stem: str,
    item: DataFlowItem,
) -> Path:
    atom_base = ws.system_atoms_dir(system) / doc_stem / "data-flow"
    filename = _sanitize_filename(item.name) + ".md"
    path = atom_base / filename

    intermediates = ""
    if item.intermediate_entities:
        intermediates = f"\n中间实体: {', '.join(item.intermediate_entities)}\n"

    metadata = {
        "type": "data-flow",
        "name": item.name,
        "source_entity": item.source_entity,
        "target_entity": item.target_entity,
        "intermediate_entities": item.intermediate_entities,
        "data_content": item.data_content,
        "provenance": item.provenance.model_dump(mode="json") if item.provenance else {},
        "synthesis_backlinks": [],
    }

    quotes = ""
    for q in item.context_quotes:
        quotes += f'> **§{q.paragraph}**: "{q.quote}"\n'

    body = (
        f"# {item.name}\n\n"
        f"## 描述\n\n{item.description or '(见原文上下文)'}\n\n"
        f"## 数据内容\n\n{item.data_content}{intermediates}\n\n"
        f"## 原文上下文\n\n{quotes}"
    )

    write_atom_file(path, metadata, body)
    return path


def _merge_extraction_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge extraction results from multiple chunks."""
    merged: dict[str, list] = {"glossary": [], "entities": [], "data_flows": []}
    for r in results:
        merged["glossary"].extend(r.get("glossary", []))
        merged["entities"].extend(r.get("entities", []))
        merged["data_flows"].extend(r.get("data_flows", []))

    # Deduplicate by name within each type
    for key in merged:
        seen: set[str] = set()
        deduped: list = []
        for item in merged[key]:
            name = item.get("name", "")
            if name and name not in seen:
                seen.add(name)
                deduped.append(item)
        merged[key] = deduped

    return merged


async def extract_document(
    ws: WorkspaceConfig,
    llm_config: LLMConfig,
    client: LLMClient,
    system: str,
    raw_path: Path,
    md_path: Path,
    flow_logger: logging.Logger,
) -> dict[str, int]:
    """Run full extraction pipeline on a single document.

    Returns counts: {"entities": N, "data_flows": N, "glossary": N}
    """
    md_text = md_path.read_text(encoding="utf-8")
    total_paragraphs = count_paragraphs(md_text)
    chunks = prepare_chunks(md_text)
    doc_stem = raw_path.stem

    flow_logger.info(
        f"LLM抽取开始: {md_path.name} "
        f"({total_paragraphs} 段, {len(chunks)} 个块)"
    )

    blacklist = load_blacklist(ws, system)

    # Load prompts
    entity_prompt, entity_pf, entity_pv = load_prompt(ws, "entity_extraction", system)
    dataflow_prompt, dataflow_pf, dataflow_pv = load_prompt(ws, "dataflow_extraction", system)
    glossary_prompt, glossary_pf, glossary_pv = load_prompt(ws, "glossary_extraction", system)

    # Extract from all chunks concurrently (3 types × N chunks)
    all_results: list[dict[str, Any]] = []
    for chunk in chunks:
        tasks = [
            _extract_type(
                client, entity_prompt, entity_pf, entity_pv,
                chunk, "entity_extraction",
                str(md_path.relative_to(ws.root)), system,
            ),
            _extract_type(
                client, dataflow_prompt, dataflow_pf, dataflow_pv,
                chunk, "dataflow_extraction",
                str(md_path.relative_to(ws.root)), system,
            ),
            _extract_type(
                client, glossary_prompt, glossary_pf, glossary_pv,
                chunk, "glossary_extraction",
                str(md_path.relative_to(ws.root)), system,
            ),
        ]
        chunk_results = await asyncio.gather(*tasks)

        # Merge the three results into one dict
        merged_chunk: dict[str, list] = {"glossary": [], "entities": [], "data_flows": []}
        for r in chunk_results:
            merged_chunk["glossary"].extend(r.get("glossary", []))
            merged_chunk["entities"].extend(r.get("entities", []))
            merged_chunk["data_flows"].extend(r.get("data_flows", []))
        all_results.append(merged_chunk)

    # Merge across chunks
    merged = _merge_extraction_results(all_results)

    # Validate with Pydantic
    try:
        result = LLMExtractionResult.model_validate(merged)
    except Exception as e:
        flow_logger.error(f"结构校验失败: {e}")
        return {"entities": 0, "data_flows": 0, "glossary": 0}

    # Blacklist filtering
    result, filter_log = filter_by_blacklist(result, blacklist)
    for entry in filter_log:
        flow_logger.warning(f"黑名单剔除: \"{entry['name']}\" ({entry['reason']})")

    # Cross validation
    warnings = cross_validate(result)
    for w in warnings:
        flow_logger.warning(f"交叉校验: {w}")

    # Attach provenance and persist
    counts = {"entities": 0, "data_flows": 0, "glossary": 0}

    for item in result.glossary:
        item.provenance = _build_provenance(
            ws, raw_path, md_path, item.paragraphs,
            glossary_pf, glossary_pv, llm_config.model,
        )
        _write_glossary_atom(ws, system, doc_stem, item)
        counts["glossary"] += 1

    for item in result.entities:
        item.provenance = _build_provenance(
            ws, raw_path, md_path, item.paragraphs,
            entity_pf, entity_pv, llm_config.model,
        )
        _write_entity_atom(ws, system, doc_stem, item)
        counts["entities"] += 1

    for item in result.data_flows:
        item.provenance = _build_provenance(
            ws, raw_path, md_path, item.paragraphs,
            dataflow_pf, dataflow_pv, llm_config.model,
        )
        _write_dataflow_atom(ws, system, doc_stem, item)
        counts["data_flows"] += 1

    flow_logger.info(
        f"LLM抽取完成: entities={counts['entities']}, "
        f"data_flows={counts['data_flows']}, glossary={counts['glossary']}"
    )

    return counts
