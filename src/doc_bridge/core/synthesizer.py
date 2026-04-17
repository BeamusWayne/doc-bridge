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

    # LLM dedup (if enabled and client provided) — returns index groups
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

    # Build tables
    glossary_path = synthesis_dir / "术语总表.md"
    entity_path = synthesis_dir / "实体总表.md"
    dataflow_path = synthesis_dir / "数据流总表.md"

    # glossary / dataflow: legacy flat rendering using group representatives
    glossary_flat = _flatten_groups(glossary_atoms, glossary_groups)
    dataflow_flat = _flatten_groups(dataflow_atoms, dataflow_groups)

    glossary_md = _build_glossary_table(ws, system, glossary_flat, glossary_path)
    entity_md = await _build_entity_table_grouped(
        ws, system, entity_atoms, entity_groups, entity_path, client, log,
    )
    dataflow_md = _build_dataflow_table(ws, system, dataflow_flat, dataflow_path)

    glossary_path.write_text(glossary_md, encoding="utf-8")
    entity_path.write_text(entity_md, encoding="utf-8")
    dataflow_path.write_text(dataflow_md, encoding="utf-8")

    # Write backlinks for ALL atoms in every group, not just primaries
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

    Fixes relative to the old `_dedup_atoms`:
    - Operates on atom indices (not names), so same-name atoms from different
      source files are properly distinguished.
    - Normalizes LLM output: each index is assigned to at most one group, and
      the representative is always preserved (can't be in `to_remove`).
    - Passes truncated descriptions to the LLM alongside names to help it
      disambiguate look-alike entries (e.g. `PAS接口机(主)` vs `(备)`).
    """
    n = len(atoms)
    if n < 2:
        return [[i] for i in range(n)]

    # Build indexed display list with names + short descriptions
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

    # Append singletons in original order so output is stable
    for i in range(n):
        if i not in assigned:
            groups.append([i])

    return groups


def _flatten_groups(
    atoms: list[tuple[Path, dict[str, Any]]],
    groups: list[list[int]],
) -> list[tuple[Path, dict[str, Any]]]:
    """Keep only the primary of each group. Used for glossary/dataflow legacy render."""
    return [atoms[g[0]] for g in groups]


def _extract_responsibilities(body: str) -> list[str]:
    """Pull bullet items under the `## 职责` section."""
    resps: list[str] = []
    in_resp = False
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped == "## 职责":
            in_resp = True
            continue
        if in_resp and stripped.startswith("## "):
            break
        if in_resp and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                resps.append(item)
    return resps


def _merge_group_A1(
    atoms: list[tuple[Path, dict[str, Any]]],
    indices: list[int],
) -> tuple[str, list[str]]:
    """Mechanical concat + substring dedup for description and responsibilities."""
    # Description: split each atom's description on common separators, dedup, rejoin.
    desc_parts: list[str] = []
    seen_desc: set[str] = set()
    for i in indices:
        desc = (atoms[i][1].get("description") or "").strip()
        if not desc:
            continue
        for sub in (s.strip() for s in desc.split("/")):
            if sub and sub not in seen_desc:
                seen_desc.add(sub)
                desc_parts.append(sub)
    merged_desc = " / ".join(desc_parts)

    # Responsibilities: union preserving first-seen order.
    resp_parts: list[str] = []
    seen_resp: set[str] = set()
    for i in indices:
        body = atoms[i][1].get("_body", "")
        for resp in _extract_responsibilities(body):
            if resp not in seen_resp:
                seen_resp.add(resp)
                resp_parts.append(resp)
    return merged_desc, resp_parts


async def _merge_group_A2(
    atoms: list[tuple[Path, dict[str, Any]]],
    indices: list[int],
    client: LLMClient | None,
    system: str,
    log: logging.Logger,
) -> tuple[str, list[str]]:
    """LLM-rewrite unified description and responsibilities for a merged group.

    Falls back to A1 on any failure. Single-element groups skip the LLM.
    """
    if len(indices) == 1 or client is None:
        return _merge_group_A1(atoms, indices)

    source_blocks: list[str] = []
    for i in indices:
        _, meta = atoms[i]
        name = meta.get("name", "") or ""
        desc = meta.get("description", "") or ""
        resps = _extract_responsibilities(meta.get("_body", ""))
        resp_line = "; ".join(resps) if resps else "(无)"
        source_blocks.append(
            f"[来源 {i}] 名称: {name}\n  描述: {desc}\n  职责: {resp_line}"
        )

    system_prompt = (
        "你是技术文档整合专家。以下是从不同来源抽取的同一实体的记录，"
        "请合并成一段统一的描述和一组去重后的职责列表。\n\n"
        "要求:\n"
        "- 描述：一句话概括，严禁编造未在给出内容中出现的信息；如各来源相互矛盾，保留并标注。\n"
        "- 职责：合并语义等价的项，保留所有独立职责，使用简短短语。\n\n"
        '严格输出 JSON:\n{"description": "合并后描述", "responsibilities": ["职责1", "职责2"]}'
    )
    user_content = "\n\n".join(source_blocks)

    try:
        raw = await client.extract(
            system_prompt=system_prompt,
            user_content=user_content,
            step="merge_entity_group",
            source_file="(synthesis)",
            system_name=system,
            prompt_file="(inline A2)",
            prompt_version="A2.v1",
        )
        from doc_bridge.validation.schema import parse_llm_json

        parsed = parse_llm_json(raw)
        desc = str(parsed.get("description", "")).strip()
        resps_out = parsed.get("responsibilities", [])
        if not isinstance(resps_out, list):
            raise ValueError("responsibilities 非列表")
        merged_resps = [str(r).strip() for r in resps_out if str(r).strip()]
        if not desc:
            raise ValueError("空描述")
        return desc, merged_resps
    except Exception as e:
        log.warning(f"A2 合并调用失败 indices={indices}: {e}，回退 A1")
        return _merge_group_A1(atoms, indices)


async def _build_entity_table_grouped(
    ws: WorkspaceConfig,
    system: str,
    atoms: list[tuple[Path, dict[str, Any]]],
    groups: list[list[int]],
    synthesis_path: Path,
    client: LLMClient | None,
    log: logging.Logger,
) -> str:
    """Render entity summary; merged descriptions come from LLM (A2) concurrently."""
    lines = [
        f"# 实体总表 - {system}\n",
        f"> 生成时间: {__import__('datetime').datetime.now().isoformat()}",
        f"> 实体数量: {len(groups)}\n",
        "| 实体名称 | 描述 | 职责 | 文件来源 | 路径来源 | 段落来源 |",
        "|----------|------|------|----------|----------|----------|",
    ]

    merge_tasks = [
        _merge_group_A2(atoms, indices, client, system, log) for indices in groups
    ]
    merged_contents = await asyncio.gather(*merge_tasks)

    for indices, (merged_desc, merged_resps) in zip(groups, merged_contents):
        primary_path, primary_meta = atoms[indices[0]]
        name = primary_meta.get("name", "")
        resp_str = " / ".join(merged_resps) if merged_resps else ""

        file_links: list[str] = []
        atom_links: list[str] = []
        para_parts: list[str] = []
        seen_files: set[str] = set()
        seen_atoms: set[Path] = set()

        for idx in indices:
            atom_path, meta = atoms[idx]
            prov = meta.get("provenance", {}) or {}
            original = prov.get("original_file", "")
            paragraphs = prov.get("paragraphs", []) or []

            orig_name = Path(original).name if original else ""
            orig_rel = relative_link(synthesis_path, ws.root / original) if original else ""
            atom_rel = relative_link(synthesis_path, atom_path)
            atom_name = atom_path.name

            if orig_name and orig_name not in seen_files:
                seen_files.add(orig_name)
                file_links.append(f"[{orig_name}]({orig_rel})")
            if atom_path not in seen_atoms:
                seen_atoms.add(atom_path)
                atom_links.append(f"[{atom_name}]({atom_rel})")
            if paragraphs:
                para_str = ", ".join(f"§{p}" for p in paragraphs)
                para_parts.append(f"{orig_name} {para_str}" if orig_name else para_str)

        files_cell = " / ".join(file_links)
        atoms_cell = " / ".join(atom_links)
        paras_cell = " / ".join(para_parts)

        lines.append(
            f"| {name} | {merged_desc} | {resp_str} "
            f"| {files_cell} | {atoms_cell} | {paras_cell} |"
        )

    return "\n".join(lines) + "\n"
