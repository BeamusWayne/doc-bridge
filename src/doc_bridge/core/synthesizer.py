"""Synthesis — aggregate atom files into summary tables.

Each summary table renders one row per atom in its dedup group. The group's
primary atom carries the entity/term/dataflow name; follow-up rows leave the
name cell empty so every remaining cell (description, responsibilities,
source links, paragraphs) maps 1:1 to a single atom. This preserves
phrase-level traceability across sources without collapsing content.
"""

from __future__ import annotations

import logging
from datetime import datetime
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


def _extract_section(body: str, heading: str) -> str:
    """Return the first non-empty line under a `## heading` section, or ''."""
    in_section = False
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped == heading:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped:
            return stripped
    return ""


def _extract_bullet_list(body: str, heading: str) -> list[str]:
    """Return bullet items (`- …`) under a `## heading` section."""
    items: list[str] = []
    in_section = False
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped == heading:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items


def _atom_source_cells(
    ws: WorkspaceConfig,
    atom_path: Path,
    meta: dict[str, Any],
    synthesis_path: Path,
) -> tuple[str, str, str]:
    """Build the three source cells (文件来源, 路径来源, 段落来源) for one atom.

    段落来源 format is unified across tables: ``<filename> §p, §q``.
    """
    prov = meta.get("provenance", {}) or {}
    original = prov.get("original_file", "")
    paragraphs = prov.get("paragraphs", []) or []
    orig_name = Path(original).name if original else ""
    orig_rel = relative_link(synthesis_path, ws.root / original) if original else ""
    atom_rel = relative_link(synthesis_path, atom_path)

    file_cell = f"[{orig_name}]({orig_rel})" if orig_name else ""
    atom_cell = f"[{atom_path.name}]({atom_rel})"
    para_tokens = ", ".join(f"§{p}" for p in paragraphs)
    if orig_name and para_tokens:
        para_cell = f"{orig_name} {para_tokens}"
    elif para_tokens:
        para_cell = para_tokens
    else:
        para_cell = orig_name
    return file_cell, atom_cell, para_cell


def _build_glossary_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    groups: list[list[int]],
    synthesis_path: Path,
) -> str:
    """Render glossary summary. One row per atom; name shown only on the group's first row."""
    source_docs = {
        (atoms[i][1].get("provenance", {}) or {}).get("original_file", "")
        for group in groups for i in group
    }
    lines = [
        f"# 术语总表 - {system}\n",
        f"> 生成时间: {datetime.now().isoformat()}",
        f"> 术语数量: {len(groups)}",
        f"> 来源文档: {len(source_docs)}\n",
        "| 术语名称 | 专业域 | 别名 | 定义 | 文件来源 | 路径来源 | 段落来源 |",
        "|----------|--------|------|------|----------|----------|----------|",
    ]

    for indices in groups:
        primary_name = atoms[indices[0]][1].get("name", "")
        for position, idx in enumerate(indices):
            atom_path, meta = atoms[idx]
            name_cell = primary_name if position == 0 else ""
            domain = meta.get("domain", "") or "待确认"
            aliases = "; ".join(meta.get("aliases", []) or [])
            definition = _extract_section(meta.get("_body", ""), "## 定义")
            file_cell, atom_cell, para_cell = _atom_source_cells(
                ws, atom_path, meta, synthesis_path,
            )
            lines.append(
                f"| {name_cell} | {domain} | {aliases} | {definition} "
                f"| {file_cell} | {atom_cell} | {para_cell} |"
            )

    return "\n".join(lines) + "\n"


def _build_entity_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    groups: list[list[int]],
    synthesis_path: Path,
) -> str:
    """Render entity summary. One row per atom; name shown only on the group's first row."""
    lines = [
        f"# 实体总表 - {system}\n",
        f"> 生成时间: {datetime.now().isoformat()}",
        f"> 实体数量: {len(groups)}\n",
        "| 实体名称 | 描述 | 职责 | 文件来源 | 路径来源 | 段落来源 |",
        "|----------|------|------|----------|----------|----------|",
    ]

    for indices in groups:
        primary_name = atoms[indices[0]][1].get("name", "")
        for position, idx in enumerate(indices):
            atom_path, meta = atoms[idx]
            name_cell = primary_name if position == 0 else ""
            description = meta.get("description", "") or ""
            responsibilities = _extract_bullet_list(meta.get("_body", ""), "## 职责")
            resp_cell = " / ".join(responsibilities)
            file_cell, atom_cell, para_cell = _atom_source_cells(
                ws, atom_path, meta, synthesis_path,
            )
            lines.append(
                f"| {name_cell} | {description} | {resp_cell} "
                f"| {file_cell} | {atom_cell} | {para_cell} |"
            )

    return "\n".join(lines) + "\n"


def _build_dataflow_table(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    groups: list[list[int]],
    synthesis_path: Path,
) -> str:
    """Render data flow summary. One row per atom; name shown only on the group's first row."""
    lines = [
        f"# 数据流总表 - {system}\n",
        f"> 生成时间: {datetime.now().isoformat()}",
        f"> 数据流数量: {len(groups)}\n",
        "| 数据流名称 | 源实体 | 目标实体 | 中间实体 | 数据内容 | 文件来源 | 路径来源 | 段落来源 |",
        "|-----------|--------|---------|---------|---------|----------|----------|----------|",
    ]

    for indices in groups:
        primary_name = atoms[indices[0]][1].get("name", "")
        for position, idx in enumerate(indices):
            atom_path, meta = atoms[idx]
            name_cell = primary_name if position == 0 else ""
            source_entity = meta.get("source_entity", "") or ""
            target_entity = meta.get("target_entity", "") or ""
            intermediates = ", ".join(meta.get("intermediate_entities", []) or [])
            data_content = meta.get("data_content", "") or ""
            file_cell, atom_cell, para_cell = _atom_source_cells(
                ws, atom_path, meta, synthesis_path,
            )
            lines.append(
                f"| {name_cell} | {source_entity} | {target_entity} "
                f"| {intermediates} | {data_content} "
                f"| {file_cell} | {atom_cell} | {para_cell} |"
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

    Returns counts per type (number of logical groups).
    """
    log = flow_logger or logger
    synthesis_dir = ws.system_synthesis_dir(system)
    synthesis_dir.mkdir(parents=True, exist_ok=True)

    glossary_atoms = _collect_atoms(ws, system, "glossary")
    entity_atoms = _collect_atoms(ws, system, "entities")
    dataflow_atoms = _collect_atoms(ws, system, "data-flow")

    log.info(
        f"合成开始: system={system}, "
        f"glossary={len(glossary_atoms)}, "
        f"entities={len(entity_atoms)}, "
        f"data_flows={len(dataflow_atoms)}"
    )

    if do_dedup and client and llm_config:
        glossary_groups = await _group_atoms(
            ws, system, "glossary", glossary_atoms, client, log,
        )
        entity_groups = await _group_atoms(
            ws, system, "entity", entity_atoms, client, log,
        )
        dataflow_groups = await _group_atoms(
            ws, system, "data-flow", dataflow_atoms, client, log,
        )
    else:
        glossary_groups = [[i] for i in range(len(glossary_atoms))]
        entity_groups = [[i] for i in range(len(entity_atoms))]
        dataflow_groups = [[i] for i in range(len(dataflow_atoms))]

    glossary_path = synthesis_dir / "术语总表.md"
    entity_path = synthesis_dir / "实体总表.md"
    dataflow_path = synthesis_dir / "数据流总表.md"

    glossary_path.write_text(
        _build_glossary_table(ws, system, glossary_atoms, glossary_groups, glossary_path),
        encoding="utf-8",
    )
    entity_path.write_text(
        _build_entity_table(ws, system, entity_atoms, entity_groups, entity_path),
        encoding="utf-8",
    )
    dataflow_path.write_text(
        _build_dataflow_table(ws, system, dataflow_atoms, dataflow_groups, dataflow_path),
        encoding="utf-8",
    )

    _write_backlinks(glossary_atoms, glossary_path)
    _write_backlinks(entity_atoms, entity_path)
    _write_backlinks(dataflow_atoms, dataflow_path)

    counts = {
        "glossary": len(glossary_groups),
        "entities": len(entity_groups),
        "data_flows": len(dataflow_groups),
    }
    log.info(f"合成完成: {counts}")
    return counts


async def _group_atoms(
    ws: WorkspaceConfig,
    system: str,
    atom_type: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    client: LLMClient,
    log: logging.Logger,
) -> list[list[int]]:
    """Use LLM to identify duplicate atoms.

    Returns list of groups; each group is atom indices belonging to the same
    entity/term/dataflow. Index 0 of each group is the representative.
    Singletons are returned as `[idx]`.
    """
    n = len(atoms)
    if n < 2:
        return [[i] for i in range(n)]

    DESC_PREVIEW = 60
    items: list[str] = []
    for i, (_, meta) in enumerate(atoms):
        name = meta.get("name", "")
        desc = meta.get("description", "") or ""
        if len(desc) > DESC_PREVIEW:
            desc = desc[:DESC_PREVIEW] + "..."
        items.append(f"[{i}] {name} — {desc}")

    try:
        prompt_text, prompt_file, prompt_version = load_synthesis_prompt(
            ws,
            f"{atom_type}_synthesis" if atom_type != "data-flow" else "dataflow_synthesis",
            system,
        )
    except FileNotFoundError:
        log.warning(f"未找到 {atom_type} 合成提示词，跳过去重分组")
        return [[i] for i in range(n)]

    user_content = (
        f"以下是从 {system} 系统的多份文档中抽取的{atom_type}列表，"
        f"每行格式 `[序号] 名称 — 描述`。请识别其中**指代同一实体的重复项**。\n\n"
        + "\n".join(items)
        + "\n\n请以JSON格式返回需要合并的组，**使用序号（整数）**标识，例如:\n"
        '{"merge_groups": [[0, 3, 7], [2, 5]]}\n'
        '如果没有重复项，返回: {"merge_groups": []}\n'
        "注意：必须返回序号（整数），不要返回名称。"
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
        merge_groups_raw = parsed.get("merge_groups", [])
    except Exception as e:
        log.warning(f"去重LLM输出解析失败: {e}，跳过分组")
        return [[i] for i in range(n)]

    assigned: set[int] = set()
    groups: list[list[int]] = []
    for group in merge_groups_raw:
        if not isinstance(group, list):
            continue
        valid: list[int] = []
        for idx in group:
            if not isinstance(idx, int):
                continue
            if idx < 0 or idx >= n:
                continue
            if idx in assigned or idx in valid:
                continue
            valid.append(idx)
        if len(valid) >= 2:
            for idx in valid:
                assigned.add(idx)
            groups.append(valid)
            names_preview = [atoms[i][1].get("name", "") for i in valid]
            log.info(f"{atom_type} 去重合并 indices={valid}: {names_preview}")

    for i in range(n):
        if i not in assigned:
            groups.append([i])

    return groups
