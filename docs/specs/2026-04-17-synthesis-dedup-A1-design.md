# Synthesis 去重与来源聚合 — A1 方案（机械拼接）

> **状态：已采用**。选型理由见 `2026-04-17-dedup-decision.md`。

> 2026-04-17 · 针对 xianche 实体总表的去重失败与单一来源问题

## 问题

1. 同名 atom 来自不同文档时 LLM dedup 不生效（例：`应急系统` 在湛江西和广州白云各一份，都保留）。
2. LLM 返回的 merge_group 包含代表项本身时，代表项反被删除（例：`['广播接口机程序', '广播接口程序', '广播接口机程序', ...]`）。
3. LLM dedup 只收到名称，无法区分主/备等同名但不同实体（例：`PAS接口机(主)` 与 `PAS接口机(备)` 被错合）。
4. 每个实体只显示单一 `文件来源` 和 `路径来源`，合并后被丢弃的 atom 来源信息丢失。

## 根因

`src/doc_bridge/core/synthesizer.py::_dedup_atoms`：
- 按 `name` 字符串过滤 atoms，无法处理同名不同源。
- `to_remove` 可能包含代表项。
- prompt 只发 name，不含 description。
- 合并即丢弃，渲染器每行只取一个 `provenance.original_file`。

## 方案概述

将"过滤丢弃"改为"分组聚合"。
- 去重步骤输出 `list[list[int]]`（atom 索引分组，每组首项为代表）。
- 实体渲染按组聚合来源（文件/路径/段落），描述和职责做**机械合并**。

## 关键变更

### 1. `_dedup_atoms` → `_group_atoms`
返回 atom 索引的分组。修复：
- 基于索引而非名称区分 atom，解决 Bug 1。
- 已分配索引不重复分配，`valid_indices[0]` 作为代表，解决 Bug 2。
- prompt 改为 `[序号] 名称 — 描述（前 60 字）`，LLM 返回 `merge_groups: [[int]]`，解决 Bug 3。

### 2. 新的实体渲染 `_build_entity_table_grouped`
每组聚合：
- 文件来源：按出现顺序 unique 的 `[docx](rel)` 列表，用 ` / ` 分隔。
- 路径来源：unique 的 atom 链接列表。
- 段落来源：按文件分组 `a.docx §1,§7 / b.docx §40,§41`。
- 描述：**A1 策略** — 拼接所有成员的 description，按 `/` 切片后剔除完全相同子串，用 ` / ` 重拼。
- 职责：按 ` / ` 聚合，去重 exact match，保留首现顺序。

### 3. 向后兼容
glossary 和 dataflow 继续使用旧的扁平渲染（取每组代表），同时享受 Bug 1/2/3 的修复。本次不改它们的渲染。

### 4. backlinks
所有 atom（包括被聚合的成员）都写入 `synthesis_backlinks`，保留 atom → synthesis 反向链。

## A1 策略细节（描述/职责合并）

**描述合并**
```python
def _merge_descriptions_A1(descs: list[str]) -> str:
    seen: list[str] = []
    for desc in descs:
        for sub in (s.strip() for s in desc.split("/")):
            if sub and sub not in seen:
                seen.append(sub)
    return " / ".join(seen)
```

**职责合并**：与描述相同逻辑，每条按行存储并去重。

## 取舍

- **成本**：0 额外 LLM 调用。
- **确定性**：完全确定，重跑同样结果。
- **可溯源**：拼接后每个子串可精确对回某个 atom。
- **代价**：描述可能较长/重复性高（但子串去重可消掉 60-80% 冗余）。

## 验收

- `synthesis/xianche/实体总表.md` 行数减少（期望 106 → ~80 左右）。
- `应急系统`、`导向后台`、`广播后台`、`导向接口机`、`TRS接口`、`旅服应急服务器` 等重复项各自合并为一行。
- 合并后的一行包含所有来源文档链接。

## 范围

**本次只改 entity 渲染**（用户限定 A/B 对比范围）。glossary、dataflow 保持旧行为。
