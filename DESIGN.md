# Doc-Bridge 系统设计方案

> 版本: v0.1-draft
> 日期: 2026-04-16
> 状态: 待审阅

---

## 1. 系统概述

Doc-Bridge 是一个文档原子化与合成系统，用于处理行业技术文档（docx/pdf）。系统通过两条核心命令完成：

- **原子化（atomize）**：将文档转为 Markdown，再由 LLM 抽取实体、数据流、术语，生成独立的原子文件
- **合成（synthesize）**：将同一系统下所有原子文件聚合为总表，并通过 LLM 进行去重/别名合并

核心原则：**可溯源、可审计、反幻觉**。

---

## 2. 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | markitdown 生态、anthropic SDK |
| CLI | Click | 成熟稳定，装饰器风格 |
| LLM 调用 | anthropic SDK | 兼容 BigModel 端点 |
| 文档转换 | markitdown[all] | 支持 docx/pdf，本地已有仓库 |
| 数据校验 | Pydantic v2 | LLM 输出结构化校验 |
| YAML frontmatter | python-frontmatter | 原子文件读写 |
| 配置管理 | python-dotenv | 读取 .env |
| 异步I/O | asyncio + aiofiles | LLM 调用 + 文件读写 |
| 进程池 | concurrent.futures.ProcessPoolExecutor | markitdown 转换 |
| Token 估算 | tiktoken 或按字符比估算 | 分块决策 |

---

## 3. 工作空间目录结构

执行 `doc-bridge init` 后生成以下结构：

```
workspace/                          # CWD即工作空间
├── .env                            # LLM配置
│
├── config/                         # 所有配置集中管理
│   ├── prompts/                    # --- 项目通用提示词 ---
│   │   ├── entity_extraction.md
│   │   ├── dataflow_extraction.md
│   │   ├── glossary_extraction.md
│   │   └── synthesis/
│   │       ├── glossary_synthesis.md
│   │       ├── entity_synthesis.md
│   │       └── dataflow_synthesis.md
│   │
│   ├── blacklists/                 # --- 项目通用黑名单 ---
│   │   └── global.yaml
│   │
│   └── systems/                    # --- 系统级配置覆盖 ---
│       └── system-A/
│           ├── prompts/            # 系统专用提示词（覆盖通用）
│           │   └── entity_extraction.md   # 仅放需要覆盖的文件
│           └── blacklists/
│               └── system.yaml     # 系统专用黑名单（与通用合并）
│
├── raw/                            # 原始文档（用户放入）
│   ├── system-A/
│   │   ├── 开发手册.docx
│   │   └── 接口规范.pdf
│   └── system-B/
│       └── ...
│
├── markdown/                       # markitdown 转换结果
│   └── system-A/
│       ├── 开发手册.md
│       └── 接口规范.md
│
├── atoms/                          # 原子化抽取结果
│   └── system-A/
│       └── 开发手册/               # 每份原始文档对应一个子目录
│           ├── entities/
│           │   ├── 旅客服务系统.md
│           │   └── 售票子系统.md
│           ├── data-flow/
│           │   └── 旅客信息_售票系统_清算中心.md
│           └── glossary/
│               ├── CTCS.md
│               └── TVM.md
│
├── synthesis/                      # 合成总表
│   └── system-A/
│       ├── 术语总表.md
│       ├── 实体总表.md
│       └── 数据流总表.md
│
└── logs/                           # 运行日志
    └── 2026-04-16T10-30-00/        # 按运行时间戳分目录
        ├── atomize.log             # 流程日志
        └── llm_calls.jsonl         # LLM调用明细日志
```

---

## 4. 项目代码结构

```
doc-bridge/
├── pyproject.toml
├── README.md
├── src/
│   └── doc_bridge/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI入口
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── init_cmd.py         # doc-bridge init
│       │   ├── atomize_cmd.py      # doc-bridge atomize
│       │   ├── synthesize_cmd.py   # doc-bridge synthesize
│       │   ├── status_cmd.py       # doc-bridge status
│       │   └── prompts_cmd.py      # doc-bridge prompts
│       ├── core/
│       │   ├── __init__.py
│       │   ├── converter.py        # markitdown 转换（无LLM）
│       │   ├── chunker.py          # 大文档分块逻辑
│       │   ├── extractor.py        # LLM 抽取编排（entity/dataflow/glossary）
│       │   ├── synthesizer.py      # 总表合成编排
│       │   └── deduplicator.py     # LLM 去重逻辑
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py           # Anthropic SDK 封装，异步
│       │   ├── prompt_loader.py    # 提示词加载（系统级 > 通用）
│       │   └── logger.py           # LLM调用日志记录器
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── schema.py           # Pydantic 模型定义
│       │   ├── blacklist.py        # 黑名单加载与匹配（通用 + 系统级合并）
│       │   └── cross_check.py      # 交叉校验逻辑
│       ├── models/
│       │   ├── __init__.py
│       │   ├── atom.py             # 原子文件数据模型
│       │   ├── provenance.py       # 溯源链数据模型
│       │   └── config.py           # 配置数据模型
│       └── utils/
│           ├── __init__.py
│           ├── frontmatter.py      # YAML frontmatter 读写
│           ├── token_counter.py    # Token 估算
│           └── workspace.py        # 工作空间路径解析
├── defaults/                       # init时复制到workspace的默认文件
│   ├── prompts/
│   │   ├── entity_extraction.md
│   │   ├── dataflow_extraction.md
│   │   ├── glossary_extraction.md
│   │   └── synthesis/
│   │       └── ...
│   ├── blacklists/
│   │   └── global.yaml
│   └── .env.template
└── tests/
    ├── test_converter.py
    ├── test_extractor.py
    ├── test_synthesizer.py
    ├── test_validation.py
    └── fixtures/
        ├── sample.docx
        └── sample.md
```

---

## 5. CLI 命令设计

### 5.1 `doc-bridge init`

初始化当前目录为 Doc-Bridge 工作空间。

```bash
doc-bridge init
```

行为：
- 创建 `config/`、`raw/`、`markdown/`、`atoms/`、`synthesis/`、`logs/` 目录
- 复制默认提示词到 `config/prompts/`
- 复制默认黑名单到 `config/blacklists/global.yaml`
- 生成 `.env.template`（如果 `.env` 不存在则同时生成 `.env`）
- 幂等操作：已存在的文件不覆盖

### 5.2 `doc-bridge atomize`

```bash
# 处理某系统下所有文档
doc-bridge atomize --system system-A

# 处理单个文件
doc-bridge atomize --system system-A --file 开发手册.docx

# 强制全量重新处理（忽略增量状态）
doc-bridge atomize --system system-A --force
```

选项：
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--system` | 系统名（对应 raw/ 下的子目录名） | 必填 |
| `--file` | 指定单个文件名 | 可选，不指定则处理系统下所有文件 |
| `--force` | 强制全量重新处理 | 默认增量 |
| `--concurrency` | LLM 并发数 | 5 |

### 5.3 `doc-bridge synthesize`

```bash
# 合成某系统的总表
doc-bridge synthesize --system system-A

# 合成所有系统的总表
doc-bridge synthesize

# 不做LLM去重（纯程序聚合）
doc-bridge synthesize --system system-A --no-dedup
```

选项：
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--system` | 系统名 | 可选，不指定则处理所有系统 |
| `--no-dedup` | 跳过LLM去重步骤 | 默认启用去重 |
| `--concurrency` | LLM 并发数 | 5 |

### 5.4 `doc-bridge status`

```bash
doc-bridge status                    # 所有系统状态概览
doc-bridge status --system system-A  # 某系统详细状态
```

输出示例：
```
system-A:
  原始文档: 3 个
  已转换:   2 个 (开发手册.md, 接口规范.md)
  待转换:   1 个 (运维手册.docx)
  已抽取:   2 个 → 实体 8 / 数据流 3 / 术语 15
  已合成:   否
```

### 5.5 `doc-bridge prompts`

```bash
doc-bridge prompts                    # 列出所有提示词文件路径
doc-bridge prompts --system system-A  # 列出system-A生效的提示词（含覆盖关系）
```

输出示例：
```
entity_extraction:
  生效: config/systems/system-A/prompts/entity_extraction.md (系统级)
  通用: config/prompts/entity_extraction.md

dataflow_extraction:
  生效: config/prompts/dataflow_extraction.md (通用，无系统级覆盖)

glossary_extraction:
  生效: config/prompts/glossary_extraction.md (通用，无系统级覆盖)
```

---

## 6. 核心处理管线

### 6.1 原子化管线（atomize）

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 转换 (无LLM)                                         │
│  ┌─────────┐    ProcessPoolExecutor    ┌──────────┐            │
│  │ A.docx  │ ──────markitdown───────▶  │  A.md    │            │
│  │ B.pdf   │ ──────markitdown───────▶  │  B.md    │            │
│  └─────────┘     (CPU密集,多进程)       └──────────┘            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Token估算 + 分块决策 (无LLM)                          │
│                                                                 │
│  if tokens(A.md) <= 180K:   整文档处理                          │
│  if tokens(A.md) >  180K:   按标题层级分块                       │
│     → [A_chunk1.md, A_chunk2.md, ...]                          │
│                                                                 │
│  预留20K给prompt+response，阈值设为180K                          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: LLM抽取 (需要LLM, asyncio)                           │
│                                                                 │
│  对每个文档（或分块），并发调用3次LLM:                              │
│                                                                 │
│  asyncio.gather(                                                │
│      extract_entities(doc, prompt, blacklist),                  │
│      extract_dataflows(doc, prompt, blacklist),                 │
│      extract_glossary(doc, prompt, blacklist),                  │
│  )                                                              │
│                                                                 │
│  Semaphore(N) 控制全局并发数                                     │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 校验 + 过滤 (无LLM)                                   │
│                                                                 │
│  Pydantic结构校验 → 黑名单过滤 → 交叉校验                         │
│       ↓ 失败               ↓ 命中            ↓ 冲突             │
│    重试(≤3次)          静默剔除+日志        记录警告+日志          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: 持久化 (无LLM)                                        │
│                                                                 │
│  将校验通过的抽取结果写入 atoms/ 目录                               │
│  每个条目一个 .md 文件，含 YAML frontmatter 溯源信息               │
│  如果是分块处理的文档，此处合并各块结果并去重                        │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 合成管线（synthesize）

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 程序聚合 (无LLM)                                      │
│                                                                 │
│  读取 atoms/system-A/ 下所有原子文件的 YAML frontmatter           │
│  按类型分组: entities[], data-flow[], glossary[]                 │
│  拼接为原始总表（含全部溯源信息）                                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: LLM去重/别名合并 (需要LLM, asyncio)                    │
│                                                                 │
│  asyncio.gather(                                                │
│      dedup_glossary(raw_table),     # 识别同义术语               │
│      dedup_entities(raw_table),     # 识别同一实体               │
│      dedup_dataflows(raw_table),    # 识别等价数据流              │
│  )                                                              │
│                                                                 │
│  LLM 仅做判断："A和B是否同一事物？"                                │
│  不生成新内容，仅合并已有条目                                      │
│  合并时保留双方溯源信息                                            │
│                                                                 │
│  (可通过 --no-dedup 跳过此步骤)                                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 专业域推断 (需要LLM, 仅术语总表)                        │
│                                                                 │
│  对于专业域为空或"待确认"的术语:                                    │
│  将同系统下已确定域的术语作为上下文，请LLM推断                       │
│  LLM只能从16个枚举值中选择，否则标记"待确认"                        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 生成总表 (无LLM)                                      │
│                                                                 │
│  按固定模板输出 Markdown 表格                                     │
│  写入 synthesis/system-A/ 下                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. 原子文件格式

### 7.1 术语原子文件

```markdown
---
type: glossary
name: "CTCS"
domain: "电务"
aliases:
  - "中国列车运行控制系统"
  - "列控系统"
provenance:
  original_file: "raw/system-A/开发手册.docx"
  markdown_file: "markdown/system-A/开发手册.md"
  paragraphs: [12, 45, 78]
  extraction_prompt: "config/prompts/glossary_extraction.md"
  extracted_at: "2026-04-16T10:30:00"
  prompt_version: "v1.0"
  llm_model: "glm-5"
  llm_call_id: "call_20260416_103000_001"
synthesis_backlinks: []              # 合成阶段自动填入
---

# CTCS

## 定义

中国列车运行控制系统（Chinese Train Control System），用于保障列车运行安全的信号控制系统。

## 原文上下文

> **§12**: "CTCS（中国列车运行控制系统）是铁路信号系统的核心组成部分，负责..."
> **§45**: "CTCS-3级列控系统采用GSM-R无线通信技术实现车地双向信息传输..."
> **§78**: "本系统需对接CTCS接口，实现列车运行状态的实时监控..."

## 关联总表

<!-- 合成阶段自动生成，请勿手动编辑 -->
- [术语总表 - system-A](../../../synthesis/system-A/术语总表.md)
```

### 7.2 实体原子文件

```markdown
---
type: entity
name: "旅客服务系统"
description: "面向旅客提供信息查询、购票、改签等综合服务的信息系统"
provenance:
  original_file: "raw/system-A/开发手册.docx"
  markdown_file: "markdown/system-A/开发手册.md"
  paragraphs: [5, 23, 67]
  extraction_prompt: "config/prompts/entity_extraction.md"
  extracted_at: "2026-04-16T10:30:00"
  prompt_version: "v1.0"
  llm_model: "glm-5"
  llm_call_id: "call_20260416_103000_002"
synthesis_backlinks: []
---

# 旅客服务系统

## 描述

面向旅客提供信息查询、购票、改签等综合服务的信息系统。

## 职责

- 旅客信息查询
- 车票购买与改签
- 旅客通知推送

## 原文上下文

> **§5**: "旅客服务系统是客运信息化的核心平台，承载..."
> **§23**: "旅客服务系统需与售票子系统、检票子系统实现数据互通..."
> **§67**: "旅客服务系统的运维管理由信息技术部门负责..."

## 关联总表

<!-- 合成阶段自动生成，请勿手动编辑 -->
- [实体总表 - system-A](../../../synthesis/system-A/实体总表.md)
```

### 7.3 数据流原子文件

```markdown
---
type: data-flow
name: "旅客信息 → 售票系统 → 清算中心"
source_entity: "旅客服务系统"
target_entity: "清算中心"
intermediate_entities:
  - "售票系统"
data_content: "旅客购票交易数据"
provenance:
  original_file: "raw/system-A/开发手册.docx"
  markdown_file: "markdown/system-A/开发手册.md"
  paragraphs: [34, 35]
  extraction_prompt: "config/prompts/dataflow_extraction.md"
  extracted_at: "2026-04-16T10:30:00"
  prompt_version: "v1.0"
  llm_model: "glm-5"
  llm_call_id: "call_20260416_103000_003"
synthesis_backlinks: []
---

# 旅客信息 → 售票系统 → 清算中心

## 描述

旅客通过旅客服务系统发起购票请求，售票系统处理交易后将结算数据推送至清算中心。

## 数据内容

旅客购票交易数据（包含车次、席别、票价、支付方式等）

## 原文上下文

> **§34**: "售票系统在完成交易后，将交易明细数据按T+1周期汇总推送至清算中心..."
> **§35**: "清算中心接收各售票渠道的交易数据，进行跨局清算..."

## 关联总表

<!-- 合成阶段自动生成，请勿手动编辑 -->
- [数据流总表 - system-A](../../../synthesis/system-A/数据流总表.md)
```

---

## 8. 总表格式

### 8.1 术语总表

```markdown
# 术语总表 - system-A

> 生成时间: 2026-04-16T11:00:00
> 术语数量: 15
> 来源文档: 3

| 术语名称 | 专业域 | 别名 | 定义 | 文件来源 | 路径来源 | 段落来源 |
|----------|--------|------|------|----------|----------|----------|
| CTCS | 电务 | 中国列车运行控制系统; 列控系统 | 用于保障列车运行安全的信号控制系统 | [开发手册.docx](../../raw/system-A/开发手册.docx) | [CTCS.md](../../atoms/system-A/开发手册/glossary/CTCS.md) | §12, §45, §78 |
| TVM | 客运 | 自动售票机 | 设置在车站供旅客自助购票的终端设备 | [接口规范.docx](../../raw/system-A/接口规范.docx) | [TVM.md](../../atoms/system-A/接口规范/glossary/TVM.md) | §8, §22 |
| ... | ... | ... | ... | ... | ... | ... |
```

字段说明：
- **术语名称**：必填
- **专业域**：必填，枚举值（客运/货运/机务/车辆/工务/电务/供电/安监/计统/财务/人事/建设/物资/运输/企法/科信）
- **别名**：选填，多个别名用分号分隔
- **定义**：必填，从原文提取的定义
- **文件来源**：必填，Markdown 链接指向原始文档
- **路径来源**：必填，Markdown 链接指向原子文件
- **段落来源**：必填，段落编号

### 8.2 实体总表

```markdown
# 实体总表 - system-A

| 实体名称 | 描述 | 职责 | 文件来源 | 路径来源 | 段落来源 |
|----------|------|------|----------|----------|----------|
| 旅客服务系统 | 面向旅客提供综合服务的信息系统 | 信息查询/购票/改签 | [开发手册.docx](../../raw/system-A/开发手册.docx) | [旅客服务系统.md](../../atoms/system-A/开发手册/entities/旅客服务系统.md) | §5, §23 |
| ... | ... | ... | ... | ... | ... |
```

### 8.3 数据流总表

```markdown
# 数据流总表 - system-A

| 数据流名称 | 源实体 | 目标实体 | 中间实体 | 数据内容 | 文件来源 | 路径来源 | 段落来源 |
|-----------|--------|---------|---------|---------|----------|----------|----------|
| 旅客信息→售票系统→清算中心 | 旅客服务系统 | 清算中心 | 售票系统 | 购票交易数据 | [开发手册.docx](../../raw/system-A/开发手册.docx) | [旅客信息_售票系统_清算中心.md](../../atoms/system-A/开发手册/data-flow/旅客信息_售票系统_清算中心.md) | §34, §35 |
| ... | ... | ... | ... | ... | ... | ... | ... |
```

### 8.4 双向链接机制

总表与原子文件之间通过 Markdown 相对路径实现双向链接：

**正向（总表 → 原子文件 / 原始文档）**：
- 路径来源：`[CTCS.md](../../atoms/system-A/开发手册/glossary/CTCS.md)`
- 文件来源：`[开发手册.docx](../../raw/system-A/开发手册.docx)`

**反向（原子文件 → 总表）**：
每个原子文件的 YAML frontmatter 中包含 `synthesis_backlink` 字段，在合成阶段自动写入：

```yaml
provenance:
  original_file: "raw/system-A/开发手册.docx"
  markdown_file: "markdown/system-A/开发手册.md"
  # ...其他字段...
synthesis_backlinks:
  - "synthesis/system-A/术语总表.md"
```

原子文件 Markdown body 末尾也追加可读的反向链接：

```markdown
## 关联总表

- [术语总表 - system-A](../../../synthesis/system-A/术语总表.md)
```

**链接维护规则**：
- 正向链接在合成时自动生成（程序计算相对路径）
- 反向链接在合成时自动回写到原子文件（更新 frontmatter + 追加 body 区块）
- 重新合成时先清除旧的反向链接再写入新的，保证一致性

---

## 9. 提示词管理

### 9.1 层级与优先级

```
config/prompts/entity_extraction.md              ← 项目通用（默认）
config/systems/system-A/prompts/entity_extraction.md  ← 系统专用（优先）
```

**加载逻辑**：

```python
def load_prompt(prompt_name: str, system: str) -> str:
    system_path = f"config/systems/{system}/prompts/{prompt_name}.md"
    global_path = f"config/prompts/{prompt_name}.md"
    
    if exists(system_path):
        return read(system_path)   # 系统级优先
    return read(global_path)       # 回退到通用
```

### 9.2 提示词文件结构

每个提示词文件包含以下区块（以 `glossary_extraction.md` 为例）：

```markdown
# 术语抽取提示词

## 角色

你是一位铁路行业技术文档分析专家。

## 任务

从给定的 Markdown 文档中抽取所有领域专有术语。

## 定义与边界

### 什么是术语
- 需要专门定义才能被非专业人员理解的领域名词
- 行业特有的缩写或简称
- 具有特定技术含义的概念

### 什么不是术语（雷区）
- 通用技术术语（HTTP, JSON, SQL, API, REST, XML, TCP/IP 等）
- 编程语言和框架（Java, Python, Spring, Vue 等）
- 品牌和厂商名（华为, 中兴, Oracle, 达梦 等）
- 版本号和数字标识（v2.0, 3.1.4 等）
- 参数名、配置项、端口号、IP地址等技术参数
- 常识性词汇（服务器, 数据库, 网络 等）
- 文件格式名（.docx, .xml, .csv 等）

## 输出格式

严格按以下JSON格式输出，不要输出任何其他内容：

```json
{
  "glossary": [
    {
      "name": "术语名称",
      "domain": "专业域（从枚举值中选择）",
      "aliases": ["别名1", "别名2"],
      "definition": "从原文提取或归纳的定义",
      "paragraphs": [12, 45],
      "context_quotes": [
        {"paragraph": 12, "quote": "原文引用..."},
        {"paragraph": 45, "quote": "原文引用..."}
      ]
    }
  ]
}
```

## 专业域枚举

只能从以下值中选择：
客运、货运、机务、车辆、工务、电务、供电、安监、计统、财务、人事、建设、物资、运输、企法、科信

如果无法确定，填写"待确认"。

## 自检清单

输出前请逐项检查：
1. 每个术语是否在原文中明确出现？（不可凭空编造）
2. 是否误将通用技术术语纳入？
3. 是否误将品牌/厂商名纳入？
4. 是否误将参数/配置项纳入？
5. 每个引用的段落编号是否真实存在于原文中？
6. 定义是否基于原文内容而非外部知识？
7. 专业域是否从枚举值中选取？

## 示例

（此处放入具体的输入输出示例，帮助LLM理解预期行为）
```

### 9.3 提示词版本管理

每个提示词文件的首行注释包含版本号：

```markdown
<!-- version: v1.0 -->
# 术语抽取提示词
...
```

原子文件的 `provenance.prompt_version` 记录抽取时使用的版本号，用于溯源。

---

## 10. 黑名单管理

### 10.1 层级与合并

```
config/blacklists/global.yaml             ← 项目通用黑名单
config/systems/system-A/blacklists/system.yaml  ← 系统专用黑名单
```

**合并逻辑**：生效黑名单 = 通用黑名单 ∪ 系统专用黑名单（取并集）。

### 10.2 黑名单格式

```yaml
# global.yaml - 项目通用黑名单

# 通用技术术语
tech_terms:
  - HTTP
  - HTTPS
  - JSON
  - XML
  - SQL
  - API
  - REST
  - TCP
  - IP
  - UDP
  - FTP
  - SSH
  - SSL
  - TLS
  - WebSocket
  - gRPC
  - MQTT
  - SOAP
  - WSDL
  - JDBC
  - ODBC

# 编程语言与框架
languages_and_frameworks:
  - Java
  - Python
  - JavaScript
  - TypeScript
  - Go
  - Rust
  - C++
  - Spring
  - SpringBoot
  - Vue
  - React
  - Angular
  - MyBatis
  - Hibernate
  - Redis
  - Kafka
  - RabbitMQ
  - Nginx
  - Docker
  - Kubernetes
  - K8s
  - Linux
  - Windows

# 品牌与厂商
brands:
  - 华为
  - 中兴
  - Oracle
  - 达梦
  - 浪潮
  - 中国电科
  - 阿里云
  - 腾讯云
  - 百度
  - IBM
  - Microsoft
  - Amazon
  - VMware
  - Citrix

# 参数相关（正则模式）
parameter_patterns:
  - "^\\d+(\\.\\d+)*$"            # 纯数字/版本号: 2.0, 3.1.4
  - "^v\\d+"                      # v开头版本号: v2, v3.0
  - "^\\d+\\s*(ms|s|min|MB|GB|KB|TB|Hz|MHz|GHz)$"  # 带单位的数值
  - "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$"  # IP地址
  - "^\\d{2,5}$"                  # 端口号
  - "^[A-Z_]{2,}=.+$"            # 环境变量/配置项
  - "\\.(docx|pdf|xml|json|csv|xlsx|txt|log|conf|ini|yaml|yml)$"  # 文件扩展名

# 常识性词汇
common_words:
  - 服务器
  - 客户端
  - 数据库
  - 网络
  - 接口
  - 模块
  - 组件
  - 配置
  - 参数
  - 文件
  - 目录
  - 用户
  - 管理员
  - 系统
  - 平台
  - 打开
  - 翻页
  - 点击
  - 切换
  - 上页
  - 下页
  - 上翻
  - 下翻
```

```yaml
# system.yaml - 系统专用黑名单（示例）

# system-A 特有的需要排除的词
tech_terms:
  - "SomeFrameworkSpecificToThisSystem"

brands:
  - "某特定供应商"

parameter_patterns:
  - "^PARAM_.*$"   # 该系统特有的参数命名模式
```

### 10.3 黑名单匹配逻辑

```
对每个 LLM 抽取结果的 name 字段：
  1. 精确匹配：name in (tech_terms ∪ languages_and_frameworks ∪ brands ∪ common_words)
  2. 正则匹配：name matches any pattern in parameter_patterns
  3. 大小写不敏感匹配（英文）
  → 命中任一则剔除，记录到日志
```

---

## 11. 校验体系

### 11.1 第一层：结构校验（Pydantic，硬性，失败重试）

| 规则 | 适用类型 | 说明 |
|------|---------|------|
| name 非空且 2-50 字符 | 全部 | 过短=噪音，过长=句子 |
| paragraphs 非空数组 | 全部 | 无出处=可能是幻觉 |
| 段落编号 ≥ 1 且 ≤ 源文件总段落数 | 全部 | 越界=幻觉 |
| context_quotes 至少1条 | 全部 | 必须有原文引用 |
| domain 在16个枚举值内或为"待确认" | 术语 | 硬编码白名单 |
| source_entity 和 target_entity 非空 | 数据流 | 数据流必须有两端 |
| aliases 中的每一项 ≠ name | 术语 | 别名不能等于名称本身 |
| definition 非空 | 术语 | 术语必须有定义 |
| description 非空 | 实体 | 实体必须有描述 |
| data_content 非空 | 数据流 | 必须说明传输什么数据 |

校验失败 → 重试，最多3次。3次后仍失败 → 记录错误日志，跳过该条目。

### 11.2 第二层：语义校验（黑名单 + 正则，硬性，静默剔除）

| 规则 | 说明 |
|------|------|
| 名称命中黑名单 | 精确匹配 + 正则匹配，大小写不敏感 |
| 名称是纯数字/版本号 | parameter_patterns 兜底 |
| 名称是IP地址/端口号 | parameter_patterns 兜底 |
| 名称是文件扩展名 | parameter_patterns 兜底 |
| 名称是环境变量/配置项 | parameter_patterns 兜底 |
| 名称含带单位数值 | "100ms", "2GB" 等参数值 |
| 实体名称为纯动词 | "处理"、"传输"、"接收"不是实体 |

命中 → 静默剔除 + 记录到日志（含剔除原因）。

### 11.3 第三层：交叉校验（程序逻辑，软性警告）

| 规则 | 说明 |
|------|------|
| 同文档内实体和术语不重名 | 警告，记录到日志，保留两者 |
| 数据流节点应在实体列表中 | 警告，不阻断 |
| 同文档内无完全重复条目 | 自动去重，保留第一个 |
| 引用的原文在源文件中可验证 | 程序回查markdown文件，验证引用文本确实存在 |

---

## 12. 日志体系

### 12.1 日志目录结构

```
logs/
├── 2026-04-16T10-30-00/           # atomize system-A
│   ├── atomize.log                # 流程日志
│   └── llm_calls.jsonl            # LLM调用明细
├── 2026-04-16T11-00-00/           # synthesize system-A
│   ├── synthesize.log
│   └── llm_calls.jsonl
└── latest -> 2026-04-16T11-00-00/ # 软链接指向最近一次运行
```

### 12.2 流程日志格式（atomize.log）

```
2026-04-16 10:30:00 [INFO]  开始原子化: system=system-A, mode=incremental
2026-04-16 10:30:00 [INFO]  扫描文档: 发现3个文件, 2个需处理(增量)
2026-04-16 10:30:01 [INFO]  转换开始: 开发手册.docx → 开发手册.md
2026-04-16 10:30:05 [INFO]  转换完成: 开发手册.md (12345 tokens, 未超限, 整文档处理)
2026-04-16 10:30:05 [INFO]  LLM抽取开始: 开发手册.md → entities
2026-04-16 10:30:12 [INFO]  LLM抽取完成: entities=3, dataflows=1, glossary=4
2026-04-16 10:30:12 [INFO]  校验: 结构校验通过 8/8
2026-04-16 10:30:12 [WARN]  校验: 黑名单剔除 "Java"(tech_term), "v3.0"(parameter)
2026-04-16 10:30:12 [WARN]  校验: 实体"客票系统"与术语"客票系统"重名
2026-04-16 10:30:12 [INFO]  持久化: 写入 6 个原子文件
2026-04-16 10:30:13 [INFO]  原子化完成: 耗时13s, entities=3, dataflows=1, glossary=4
```

### 12.3 LLM调用日志格式（llm_calls.jsonl）

每行一个JSON对象：

```json
{
  "call_id": "call_20260416_103005_001",
  "timestamp": "2026-04-16T10:30:05",
  "step": "entity_extraction",
  "source_file": "markdown/system-A/开发手册.md",
  "system": "system-A",
  "prompt_file": "config/prompts/entity_extraction.md",
  "prompt_version": "v1.0",
  "prompt_hash": "sha256:a1b2c3d4...",
  "model": "glm-5",
  "input_tokens": 8523,
  "output_tokens": 1245,
  "duration_ms": 6800,
  "retry_count": 0,
  "request_messages": [ ... ],
  "response_raw": "{ ... }",
  "validation_result": "pass",
  "items_extracted": 3,
  "items_filtered": 1,
  "filter_reasons": [{"name": "Java", "reason": "blacklist:tech_term"}]
}
```

---

## 13. 增量处理机制

### 13.1 状态文件

在工作空间根目录维护 `.doc-bridge-state.json`：

```json
{
  "system-A": {
    "开发手册.docx": {
      "file_hash": "sha256:abc123...",
      "converted_at": "2026-04-16T10:30:00",
      "extracted_at": "2026-04-16T10:30:12",
      "prompt_versions": {
        "entity": "v1.0",
        "dataflow": "v1.0",
        "glossary": "v1.0"
      }
    }
  }
}
```

### 13.2 增量判定逻辑

文件需要重新处理的条件（满足任一）：
1. 文件 hash 变化（文档内容被修改）
2. 该文件从未处理过（新增文档）
3. 提示词版本变化（提示词被编辑）
4. 用户指定 `--force`

---

## 14. 并发模型

```
┌─────────────────────────────────────────────────────────┐
│                    主进程 (asyncio事件循环)               │
│                                                         │
│   ┌─────────────────────────────────┐                   │
│   │  Phase 1: 文档转换               │                   │
│   │  ProcessPoolExecutor(workers=N)  │  ← CPU密集        │
│   │  file1 ──▶ md1                  │                   │
│   │  file2 ──▶ md2   (并行)         │                   │
│   │  file3 ──▶ md3                  │                   │
│   └─────────────────────────────────┘                   │
│                    │                                     │
│                    ▼                                     │
│   ┌─────────────────────────────────┐                   │
│   │  Phase 2: LLM抽取               │                   │
│   │  Semaphore(concurrency)          │  ← I/O密集        │
│   │                                  │                   │
│   │  doc1_entities  ─┐               │                   │
│   │  doc1_dataflows ─┤  async        │                   │
│   │  doc1_glossary  ─┤  并发         │                   │
│   │  doc2_entities  ─┤               │                   │
│   │  doc2_dataflows ─┤               │                   │
│   │  doc2_glossary  ─┘               │                   │
│   └─────────────────────────────────┘                   │
│                    │                                     │
│                    ▼                                     │
│   ┌─────────────────────────────────┐                   │
│   │  Phase 3: 校验+持久化            │  ← 轻量计算        │
│   │  顺序处理（快，无需并发）          │                   │
│   └─────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘

合成阶段同理:
  多系统 × 3种总表 = 异步并发
  Semaphore 共享同一个，控制API调用总并发
```

**默认并发参数**:
- `ProcessPoolExecutor`: workers = `min(cpu_count, 文件数)`
- `Semaphore`: 默认5，可通过 `--concurrency` 调整
- 建议根据 BigModel API 的限流策略调整

---

## 15. 安装与分发

```toml
# pyproject.toml（关键部分）

[project]
name = "doc-bridge"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "anthropic>=0.30",
    "markitdown[all]",
    "pydantic>=2.0",
    "python-frontmatter>=1.0",
    "python-dotenv>=1.0",
    "aiofiles>=23.0",
    "pyyaml>=6.0",
]

[project.scripts]
doc-bridge = "doc_bridge.cli:main"
```

安装方式：

```bash
# 开发模式（推荐）
cd doc-bridge
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 之后在任意工作空间目录下即可使用
cd ~/my-workspace
doc-bridge init
doc-bridge atomize --system system-A
```

---

## 16. 错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| markitdown 转换失败 | 记录错误日志，跳过该文件，继续处理其他文件 |
| LLM API 调用失败（网络/限流） | 指数退避重试，最多3次，间隔 2s/4s/8s |
| LLM 返回非法JSON | 重试（附带格式修正提示），最多3次 |
| Pydantic 校验失败 | 重试（附带校验错误信息），最多3次 |
| 3次重试后仍失败 | 记录错误日志，跳过该条目/文件，继续处理 |
| .env 缺失或配置不全 | 启动时报错退出，给出明确提示 |
| 工作空间未初始化 | 提示用户运行 `doc-bridge init` |

---

## 17. 待定与后续扩展

以下功能不在 v0.1 范围内，但架构上预留扩展点：

1. **Web UI**：查看总表、浏览溯源链
2. **导出格式**：CSV、Excel、JSON 导出
3. **多语言文档**：英文文档支持
4. **自定义抽取类型**：除 entity/dataflow/glossary 外，支持用户定义新类型
5. **图片/表格处理**：markitdown-ocr 对图片中的文字进行识别
