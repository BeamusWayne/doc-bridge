# Doc-Bridge

文档原子化与合成系统 — 将技术文档拆解为可溯源的知识原子，再聚合为结构化总表。

## 解决什么问题

面对大量 docx/pdf 格式的技术文档、开发手册、规范手册时，需要：
- 从中抽取**实体**（系统、模块、组件）、**数据流**（系统间数据传递）、**术语**（领域专有名词）
- 每条抽取结果都能**溯源到原始文档的具体段落**
- 将多份文档的抽取结果**汇总为总表**，支持去重和双向链接

Doc-Bridge 通过两条命令完成这一切：

```bash
doc-bridge atomize --system system-A      # 原子化
doc-bridge synthesize --system system-A   # 合成总表
```

## 核心特性

- **可溯源** — 每个原子文件记录完整溯源链：原始文档 → Markdown → 原子文件，包含段落编号和原文引用
- **反幻觉** — 三层校验体系（Pydantic结构校验 → 黑名单过滤 → 交叉校验），提示词内置自检清单和正反例
- **双向链接** — 总表链接到原子文件和原始文档，原子文件反向链接回总表
- **增量处理** — 自动检测文件变更和提示词版本变化，只处理需要更新的文件
- **两级配置** — 提示词和黑名单支持项目通用 + 系统专用两级覆盖
- **高效并发** — markitdown 转换用多进程，LLM 调用用 asyncio + 信号量控制并发

## 快速开始

### 安装

```bash
git clone https://github.com/BeamusWayne/doc-bridge.git
cd doc-bridge
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 初始化工作空间

```bash
mkdir ~/my-workspace && cd ~/my-workspace
doc-bridge init
```

编辑 `.env` 填入 LLM 配置：

```env
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=glm-5
```

### 新增系统 + 放入文档

```bash
doc-bridge add-system system-A
cp 开发手册.docx 接口规范.pdf raw/system-A/
```

`add-system` 幂等，重跑也安全。如果你已经手工建好 `raw/system-A/`，`atomize` 同样能用；`add-system` 的好处是顺带把 `config/systems/system-A/` 脚手架也建起来，方便以后加系统专用提示词或黑名单。

### 原子化

```bash
doc-bridge atomize --system system-A
```

处理流程：docx/pdf → Markdown → LLM抽取实体/数据流/术语 → 校验过滤 → 写入原子文件

### 合成总表

```bash
doc-bridge synthesize --system system-A
```

生成 `synthesis/system-A/` 下的术语总表、实体总表、数据流总表。

## 工作空间结构

```
workspace/
├── .env                            # LLM 配置
├── config/
│   ├── prompts/                    # 项目通用提示词（可编辑）
│   ├── blacklists/global.yaml      # 项目通用黑名单（可追加）
│   └── systems/<system>/           # 系统专用配置覆盖
│       ├── prompts/
│       └── blacklists/system.yaml
├── raw/<system>/                   # 原始文档
├── markdown/<system>/              # Markdown 转换结果
├── atoms/<system>/<doc>/           # 原子文件
│   ├── entities/
│   ├── data-flow/
│   └── glossary/
├── synthesis/<system>/             # 合成总表
│   ├── 术语总表.md
│   ├── 实体总表.md
│   └── 数据流总表.md
└── logs/                           # 运行日志 + LLM 调用记录
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `doc-bridge init` | 初始化当前目录为工作空间 |
| `doc-bridge add-system <name>` | 新增一个系统：创建 raw/ 目录和 config/systems/ 脚手架 |
| `doc-bridge atomize --system <name>` | 原子化指定系统的文档 |
| `doc-bridge synthesize --system <name>` | 合成指定系统的总表 |
| `doc-bridge status [--system <name>]` | 查看工作空间状态 |
| `doc-bridge prompts [--system <name>]` | 查看提示词覆盖关系 |

### atomize 选项

```
--system      系统名（必填）
--file        指定单个文件
--force       强制全量重新处理
--concurrency LLM 并发数（默认 5）
```

### synthesize 选项

```
--system      系统名（不指定则处理所有）
--no-dedup    跳过 LLM 去重
--concurrency LLM 并发数（默认 5）
```

## 配置覆盖机制

### 提示词

优先级：系统专用 > 项目通用

```
config/prompts/entity_extraction.md                    ← 通用（默认）
config/systems/system-A/prompts/entity_extraction.md   ← 系统专用（优先）
```

系统目录下只需放入需要覆盖的文件，其余自动回退到通用版本。

### 黑名单

合并策略：通用 ∪ 系统专用（取并集）

```yaml
# config/systems/system-A/blacklists/system.yaml
tech_terms:
  - "SomeSystemSpecificTerm"
brands:
  - "某特定供应商"
parameter_patterns:
  - "^PARAM_.*$"
```

## 原子文件示例

每个原子文件使用 YAML frontmatter 记录结构化元数据：

```markdown
---
type: glossary
name: "CTCS"
domain: "电务"
aliases: ["中国列车运行控制系统"]
provenance:
  original_file: "raw/system-A/开发手册.docx"
  markdown_file: "markdown/system-A/开发手册.md"
  paragraphs: [12, 45]
  extraction_prompt: "config/prompts/glossary_extraction.md"
  prompt_version: "v1.0"
  llm_model: "glm-5"
synthesis_backlinks:
  - "../../../synthesis/system-A/术语总表.md"
---

# CTCS

## 定义

保障列车运行安全的核心信号控制系统。

## 原文上下文

> **§12**: "CTCS（中国列车运行控制系统）是铁路信号系统的核心组成部分..."

## 关联总表

- [术语总表 - system-A](../../../synthesis/system-A/术语总表.md)
```

## 校验体系

| 层级 | 方式 | 行为 |
|------|------|------|
| 结构校验 | Pydantic | 失败重试（最多3次） |
| 语义校验 | 黑名单 + 正则 | 静默剔除 + 记录日志 |
| 交叉校验 | 程序逻辑 | 记录警告 |

预置黑名单覆盖：通用技术术语、编程语言/框架、品牌厂商、参数模式（版本号/IP/端口/配置项等）、常识性词汇。

## 日志

每次运行在 `logs/<timestamp>/` 下生成：
- `atomize.log` / `synthesize.log` — 流程日志
- `llm_calls.jsonl` — 每次 LLM 调用的完整记录（prompt、response、token 消耗、耗时）

## 技术栈

Python 3.10+ / Click / Anthropic SDK / markitdown / Pydantic v2 / asyncio / aiofiles

## License

MIT
