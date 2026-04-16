"""Synthesis — aggregate atom files into summary tables."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from doc_bridge.llm.client import LLMClient
from doc_bridge.llm.prompt_loader import load_synthesis_prompt
from doc_bridge.models.config import LLMConfig, WorkspaceConfig
from doc_bridge.utils.frontmatter import read_atom_file, update_backlinks
from doc_bridge.utils.workspace import relative_link

logger = logging.getLogger("doc_bridge.synthesizer")


def _collect_atoms(
    ws: WorkspaceConfig, system: str, atom_type: str,
) -> list[tuple[Path, dict[str, Any]]]:
    """Collect all atom files of a given type across all documents in a system."""
    atoms_dir = ws.system_atoms_dir(system)
    if not atoms_dir.exists():
        return []

    results = []
    for doc_dir in sorted(atoms_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        type_dir = doc_dir / atom_type
        if not type_dir.exists():
            continue
        for atom_file in sorted(type_dir.glob("*.md")):
            meta, body = read_atom_file(atom_file)
            meta["_atom_path"] = atom_file
            meta["_body"] = body
            results.append((atom_file, meta))

    return results


def _build_glossary_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    synthesis_path: Path,
) -> str:
    """Build glossary summary table markdown."""
    lines = [
        f"# 术语总表 - {system}\n",
        f"> 生成时间: {__import__('datetime').datetime.now().isoformat()}",
        f"> 术语数量: {len(atoms)}",
        f"> 来源文档: {len(set(m.get('provenance', {}).get('original_file', '') for _, m in atoms))}\n",
        "| 术语名称 | 专业域 | 别名 | 定义 | 文件来源 | 路径来源 | 段落来源 |",
        "|----------|--------|------|------|----------|----------|----------|",
    ]

    for atom_path, meta in atoms:
        name = meta.get("name", "")
        domain = meta.get("domain", "待确认")
        aliases = "; ".join(meta.get("aliases", []))
        prov = meta.get("provenance", {})
        original = prov.get("original_file", "")
        paragraphs = prov.get("paragraphs", [])

        # Extract definition from body
        body = meta.get("_body", "")
        definition = ""
        in_def = False
        for line in body.split("\n"):
            if line.strip() == "## 定义":
                in_def = True
                continue
            if in_def and line.startswith("## "):
                break
            if in_def and line.strip():
                definition = line.strip()
                break

        # Build relative links
        orig_rel = relative_link(synthesis_path, ws.root / original)
        atom_rel = relative_link(synthesis_path, atom_path)
        orig_name = Path(original).name
        atom_name = atom_path.name

        para_str = ", ".join(f"§{p}" for p in paragraphs)

        lines.append(
            f"| {name} | {domain} | {aliases} | {definition} "
            f"| [{orig_name}]({orig_rel}) "
            f"| [{atom_name}]({atom_rel}) "
            f"| {para_str} |"
        )

    return "\n".join(lines) + "\n"


def _build_entity_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    synthesis_path: Path,
) -> str:
    """Build entity summary table markdown."""
    lines = [
        f"# 实体总表 - {system}\n",
        f"> 生成时间: {__import__('datetime').datetime.now().isoformat()}",
        f"> 实体数量: {len(atoms)}\n",
        "| 实体名称 | 描述 | 职责 | 文件来源 | 路径来源 | 段落来源 |",
        "|----------|------|------|----------|----------|----------|",
    ]

    for atom_path, meta in atoms:
        name = meta.get("name", "")
        description = meta.get("description", "")
        prov = meta.get("provenance", {})
        original = prov.get("original_file", "")
        paragraphs = prov.get("paragraphs", [])

        # Extract responsibilities from body
        body = meta.get("_body", "")
        responsibilities: list[str] = []
        in_resp = False
        for line in body.split("\n"):
            if line.strip() == "## 职责":
                in_resp = True
                continue
            if in_resp and line.startswith("## "):
                break
            if in_resp and line.strip().startswith("- "):
                responsibilities.append(line.strip()[2:])

        resp_str = " / ".join(responsibilities) if responsibilities else ""

        orig_rel = relative_link(synthesis_path, ws.root / original)
        atom_rel = relative_link(synthesis_path, atom_path)
        orig_name = Path(original).name
        atom_name = atom_path.name
        para_str = ", ".join(f"§{p}" for p in paragraphs)

        lines.append(
            f"| {name} | {description} | {resp_str} "
            f"| [{orig_name}]({orig_rel}) "
            f"| [{atom_name}]({atom_rel}) "
            f"| {para_str} |"
        )

    return "\n".join(lines) + "\n"


def _build_dataflow_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    synthesis_path: Path,
) -> str:
    """Build data flow summary table markdown."""
    lines = [
        f"# 数据流总表 - {system}\n",
        f"> 生成时间: {__import__('datetime').datetime.now().isoformat()}",
        f"> 数据流数量: {len(atoms)}\n",
        "| 数据流名称 | 源实体 | 目标实体 | 中间实体 | 数据内容 | 文件来源 | 路径来源 | 段落来源 |",
        "|-----------|--------|---------|---------|---------|----------|----------|----------|",
    ]

    for atom_path, meta in atoms:
        name = meta.get("name", "")
        source = meta.get("source_entity", "")
        target = meta.get("target_entity", "")
        intermediates = ", ".join(meta.get("intermediate_entities", []))
        data_content = meta.get("data_content", "")
        prov = meta.get("provenance", {})
        original = prov.get("original_file", "")
        paragraphs = prov.get("paragraphs", [])

        orig_rel = relative_link(synthesis_path, ws.root / original)
        atom_rel = relative_link(synthesis_path, atom_path)
        orig_name = Path(original).name
        atom_name = atom_path.name
        para_str = ", ".join(f"§{p}" for p in paragraphs)

        lines.append(
            f"| {name} | {source} | {target} | {intermediates} | {data_content} "
            f"| [{orig_name}]({orig_rel}) "
            f"| [{atom_name}]({atom_rel}) "
            f"| {para_str} |"
        )

    return "\n".join(lines) + "\n"


def _write_backlinks(
    atoms: list[tuple[Path, dict[str, Any]]],
    synthesis_path: Path,
) -> None:
    """Update all atom files with backlinks to the synthesis table."""
    for atom_path, _meta in atoms:
        backlink = relative_link(atom_path, synthesis_path)
        update_backlinks(atom_path, [backlink])


async def synthesize_system(
    ws: WorkspaceConfig,
    system: str,
    llm_config: LLMConfig | None = None,
    client: LLMClient | None = None,
    do_dedup: bool = True,
    flow_logger: logging.Logger | None = None,
) -> dict[str, int]:
    """Synthesize summary tables for a system.

    Returns counts per type.
    """
    log = flow_logger or logger
    synthesis_dir = ws.system_synthesis_dir(system)
    synthesis_dir.mkdir(parents=True, exist_ok=True)

    # Collect all atoms
    glossary_atoms = _collect_atoms(ws, system, "glossary")
    entity_atoms = _collect_atoms(ws, system, "entities")
    dataflow_atoms = _collect_atoms(ws, system, "data-flow")

    log.info(
        f"合成开始: system={system}, "
        f"glossary={len(glossary_atoms)}, "
        f"entities={len(entity_atoms)}, "
        f"data_flows={len(dataflow_atoms)}"
    )

    # LLM dedup (if enabled and client provided)
    if do_dedup and client and llm_config:
        glossary_atoms = await _dedup_atoms(
            ws, system, "glossary", glossary_atoms, client, log,
        )
        entity_atoms = await _dedup_atoms(
            ws, system, "entity", entity_atoms, client, log,
        )
        dataflow_atoms = await _dedup_atoms(
            ws, system, "data-flow", dataflow_atoms, client, log,
        )

    # Build tables
    glossary_path = synthesis_dir / "术语总表.md"
    entity_path = synthesis_dir / "实体总表.md"
    dataflow_path = synthesis_dir / "数据流总表.md"

    glossary_md = _build_glossary_table(ws, system, glossary_atoms, glossary_path)
    entity_md = _build_entity_table(ws, system, entity_atoms, entity_path)
    dataflow_md = _build_dataflow_table(ws, system, dataflow_atoms, dataflow_path)

    glossary_path.write_text(glossary_md, encoding="utf-8")
    entity_path.write_text(entity_md, encoding="utf-8")
    dataflow_path.write_text(dataflow_md, encoding="utf-8")

    # Write backlinks
    _write_backlinks(glossary_atoms, glossary_path)
    _write_backlinks(entity_atoms, entity_path)
    _write_backlinks(dataflow_atoms, dataflow_path)

    counts = {
        "glossary": len(glossary_atoms),
        "entities": len(entity_atoms),
        "data_flows": len(dataflow_atoms),
    }
    log.info(f"合成完成: {counts}")
    return counts


async def _dedup_atoms(
    ws: WorkspaceConfig,
    system: str,
    atom_type: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    client: LLMClient,
    log: logging.Logger,
) -> list[tuple[Path, dict[str, Any]]]:
    """Use LLM to identify and merge duplicate entries."""
    if len(atoms) < 2:
        return atoms

    # Build a list of names for the LLM to check
    names = [meta.get("name", "") for _, meta in atoms]

    try:
        prompt_text, prompt_file, prompt_version = load_synthesis_prompt(
            ws, f"{atom_type}_synthesis" if atom_type != "data-flow" else "dataflow_synthesis",
            system,
        )
    except FileNotFoundError:
        log.warning(f"未找到 {atom_type} 合成提示词，跳过去重")
        return atoms

    user_content = (
        f"以下是从 {system} 系统的多份文档中抽取的{atom_type}列表，请识别其中的重复项。\n\n"
        f"名称列表:\n"
        + "\n".join(f"- {n}" for n in names)
        + "\n\n请以JSON格式返回需要合并的组，例如:\n"
        '{"merge_groups": [["名称A", "名称B"], ["名称C", "名称D"]]}\n'
        "如果没有重复项，返回: {\"merge_groups\": []}"
    )

    raw = await client.extract(
        system_prompt=prompt_text,
        user_content=user_content,
        step=f"dedup_{atom_type}",
        source_file="(synthesis)",
        system_name=system,
        prompt_file=prompt_file,
        prompt_version=prompt_version,
    )

    try:
        from doc_bridge.validation.schema import parse_llm_json
        parsed = parse_llm_json(raw)
        merge_groups: list[list[str]] = parsed.get("merge_groups", [])
    except Exception as e:
        log.warning(f"去重LLM输出解析失败: {e}，跳过去重")
        return atoms

    if not merge_groups:
        log.info(f"{atom_type} 去重: 未发现重复项")
        return atoms

    # Merge: keep the first item in each group, discard rest
    to_remove: set[str] = set()
    for group in merge_groups:
        if len(group) < 2:
            continue
        log.info(f"{atom_type} 去重合并: {group}")
        # Keep first, mark rest for removal
        for name in group[1:]:
            to_remove.add(name)

    return [(p, m) for p, m in atoms if m.get("name", "") not in to_remove]
