# Design: `add-system` command + atomize typo protection

**Date:** 2026-04-17
**Status:** Approved (brainstorming phase)
**Scope:** Add a dedicated command to register a new system in a doc-bridge workspace, and improve the typo/error experience of `atomize --system <name>`.

---

## 1. Motivation

Today a user adds a new system by manually running `mkdir -p raw/<name>` and, if needed, creating `config/systems/<name>/...` themselves. This is low-discovery, error-prone (typos produce silent divergence between `raw/` and config), and does not match the ergonomics of the rest of the CLI (which has `init`, `atomize`, `synthesize`, `status`, `prompts`).

Additionally, `atomize --system <name>` currently fails hard with a `mkdir` hint (`src/doc_bridge/commands/atomize_cmd.py:44-47`) when the target system directory is missing — including on trivial typos — without suggesting the likely intended system.

## 2. Goals

- One command creates all directories needed for a new system.
- Typos in `atomize --system <name>` surface a closest-match suggestion and a list of existing systems.
- No behavioural change to `init`, `synthesize`, `status`, or `prompts`.
- No new runtime dependencies. Pure stdlib + existing Click.

## 3. Non-goals

- No interactive wizard / TUI.
- No `--from <existing-system>` copy flag (deferred).
- No `--dry-run` flag (deferred).
- No integration test that exercises the full `docx → LLM → synthesis` pipeline.
- No auto-creation of missing system directories inside `atomize` (`--create` rejected in brainstorming to avoid overlapping responsibility with `add-system`).

## 4. CLI surface

### 4.1 New command: `doc-bridge add-system <name>`

```bash
doc-bridge add-system system-B
```

**Arguments:**

- `<name>` (required, positional): system name. Validation rules in §6.

**Flags:** none in v1. (Reserved for future: `--from`, `--dry-run`.)

**Preconditions:**

`add-system` resolves the workspace via the existing `resolve_workspace()` helper and calls `ws.validate()` before any creation work. If the current directory is not an initialised workspace, it prints the existing `工作空间未初始化: ... 请先运行: doc-bridge init` message and exits `1`. This matches the behaviour of `atomize` and `synthesize`.

**Successful new-system output:**

```
系统已创建: system-B
  原始文档: raw/system-B/
  专用配置: config/systems/system-B/
下一步: 把文档放入 raw/system-B/，然后运行 doc-bridge atomize --system system-B
```

**Idempotent re-run output:**

```
系统 'system-B' 已存在: raw/system-B/
```

Exit code `0` in both successful and already-exists cases.

### 4.2 Modified command: `doc-bridge atomize --system <name>`

The hard-error branch in `src/doc_bridge/commands/atomize_cmd.py:44-47` is replaced with a richer message.

**When `raw/` has no systems at all:**

```
错误: 工作空间还没有任何系统。
  新增系统: doc-bridge add-system <name>
```

**When a close match is found:**

```
错误: 系统 'sytem-A' 不存在。
  你是不是想: system-A?
  新增系统: doc-bridge add-system sytem-A
  已有系统: system-A, ps, system-B
```

**When no close match is found:**

```
错误: 系统 'zzz' 不存在。
  新增系统: doc-bridge add-system zzz
  已有系统: system-A, ps, system-B
```

Exit code `1` in all error cases.

## 5. Directory creation

When `add-system system-B` runs on a valid new name, it creates:

```
raw/system-B/
config/systems/system-B/prompts/
config/systems/system-B/blacklists/
config/systems/system-B/blacklists/system.yaml        # from defaults template
```

It does **not** create `markdown/system-B/`, `atoms/system-B/`, or `synthesis/system-B/`. Those are created by downstream commands on demand. Verify this assumption during implementation; if any downstream code assumes the per-system output dir pre-exists, add its creation here and note it in the implementation plan.

**`system.yaml` template** (shipped as `defaults/system_blacklist.template.yaml`):

```yaml
# 系统专用黑名单 - 与 config/blacklists/global.yaml 取并集
tech_terms: []          # 例: ["SomeSystemSpecificTerm"]
brands: []              # 例: ["某特定供应商"]
parameter_patterns: []  # 正则，例: ["^PARAM_.*$"]
```

**Template lookup order** (in `create_system_dirs`):

1. The package's `defaults/system_blacklist.template.yaml` (resolved the same way `init_cmd.py` locates the `defaults/` directory: `Path(__file__).resolve().parent.parent.parent.parent / "defaults"`).
2. If the file is not found (slimmed installation), fall back to a string literal embedded in `system_ops.py`, matching the existing `_write_builtin_defaults` pattern in `init_cmd.py:65-78`.

The template is **not** copied into the workspace by `init`. `add-system` reads it fresh each time. This keeps `init`'s responsibilities unchanged and treats the template as a package-level artefact, unlike prompts/blacklists (which users are expected to edit per-workspace).

## 6. Name validation

`validate_system_name(name: str) -> None` lives in `src/doc_bridge/utils/system_ops.py`. It raises `ValueError` with a user-facing Chinese message on any violation.

**Rules:**

| Rule | Rejection reason |
|---|---|
| `name == ""` | 系统名不能为空 |
| `name in {".", ".."}` | 系统名不能为保留字 |
| `len(name) > 64` | 系统名过长 (>64 字符) |
| contains any of `' '`, `'/'`, `'\\'`, `'.'` | 系统名含非法字符 (空格 / 斜杠 / 反斜杠 / 点) |

**Accepted examples:** `system-A`, `ps`, `cbtc_v2`, `系统一`, `ATP-2`
**Rejected examples:** `""`, `" "`, `"sys a"`, `"sys/a"`, `"sys\\a"`, `"."`, `".."`, `"a" * 65`

**Case sensitivity:** names are compared case-sensitively. `System-A` and `system-a` are treated as two distinct systems. No normalisation is performed; collisions on case-insensitive filesystems surface as `OSError` during `mkdir` and are reported verbatim.

## 7. Error handling

| Scenario | Behaviour | Exit |
|---|---|---|
| `add-system <any>` from a non-workspace directory | Print existing `工作空间未初始化` message | `1` |
| `add-system <invalid>` | Print `ValueError` message | `1` |
| `add-system <existing>` | Print "已存在" line | `0` |
| `add-system <new>`, `mkdir` fails | Print `OSError` + hint to check workspace root / permissions | `1` |
| `atomize --system <missing>` | Error message per §4.2 | `1` |
| `atomize --system <exists, empty>` | Unchanged: "所有文件均已处理" / space walk | `0` |

No retries, no interactive confirmation. Messages are single-pass and complete.

## 8. Typo suggestion

Uses `difflib.get_close_matches(name, existing, n=1, cutoff=0.6)` from the stdlib.

- `cutoff=0.6` is the library default; empirically matches `sytem-A` → `system-A` without false-positives on unrelated inputs.
- Only the top-1 match is surfaced, to keep the message short.
- If the result is empty, the "你是不是想" line is omitted — the "已有系统" list still appears.

The existing-systems list is produced by `list_existing_systems(ws)`, which enumerates `ws.raw_dir.iterdir()`, keeps only directories, and returns names sorted with `sorted(key=str.casefold)` for stable, readable output.

## 9. Code layout

### 9.1 New files

| Path | Purpose | Approx LOC |
|---|---|---|
| `src/doc_bridge/commands/add_system_cmd.py` | Click command, wires validate/create/format | ~60 |
| `src/doc_bridge/utils/system_ops.py` | `validate_system_name`, `create_system_dirs`, `list_existing_systems`, `suggest_close_system` | ~60 |
| `defaults/system_blacklist.template.yaml` | Blacklist template copied into each new system | ~5 |
| `tests/commands/test_add_system_cmd.py` | Click `CliRunner` tests | ~80 |
| `tests/utils/test_system_ops.py` | Pure unit tests | ~80 |
| `tests/commands/test_atomize_cmd.py` | Tests for the new error branch only | ~40 |
| `tests/conftest.py` (if absent) or extension | `tmp_workspace` fixture | ~15 |

### 9.2 Modified files

| Path | Change |
|---|---|
| `src/doc_bridge/cli.py` | Import `add_system_cmd` and `main.add_command(...)` it |
| `src/doc_bridge/commands/atomize_cmd.py` | Replace lines 44-47 with a call to `list_existing_systems` + `suggest_close_system`, formatted per §4.2 |
| `README.md` | Add `add-system` to the command table; update the "加新系统" flow |

### 9.3 Not modified

- `src/doc_bridge/models/config.py` — `WorkspaceConfig` / `LLMConfig` unchanged.
- Existing prompt / blacklist files in `defaults/`.
- `synthesize`, `status`, `prompts` commands.

## 10. Testing

Target: 80%+ coverage on all new code. Framework: `pytest` + Click's `CliRunner`, per project standard (`rules/python/testing.md`). No new dependencies.

### 10.1 `tests/utils/test_system_ops.py`

- `validate_system_name`:
  - accepts `system-A`, `ps`, `cbtc_v2`, `系统一`, `ATP-2`
  - rejects `""`, `" "`, `"sys a"`, `"sys/a"`, `"sys\\a"`, `"."`, `".."`, `"a" * 65`
- `suggest_close_system`:
  - `"sytem-A"` + `["system-A", "ps"]` → `"system-A"`
  - `"xyz"` + `["system-A", "ps"]` → `None`
  - empty existing list → `None`
- `list_existing_systems`:
  - empty `raw/` → `[]`
  - multiple subdirs → sorted case-folded
  - non-directory entries (a stray file) ignored
- `create_system_dirs`:
  - new system: all four paths exist; `system.yaml` matches template bytes
  - already exists: returns `False`, does not overwrite `system.yaml`
  - template missing from `defaults/`: falls back to embedded string, still succeeds

### 10.2 `tests/commands/test_add_system_cmd.py`

All via `CliRunner`:

- new system: `exit_code == 0`, directories exist, output contains `doc-bridge atomize`
- already exists: `exit_code == 0`, output contains `已存在`
- invalid name (space): `exit_code == 1`, output contains `非法字符`
- invalid name (empty string): `exit_code == 1`
- Chinese name (`系统一`): `exit_code == 0`, directory created
- not inside a workspace (no `config/` at cwd): `exit_code == 1`, output contains `未初始化`

### 10.3 `tests/commands/test_atomize_cmd.py`

Only the error branch — LLM path is out of scope for this spec. Mock nothing beyond what the branch touches.

- `raw/` empty: output contains `工作空间还没有`
- system missing, close match exists: output contains `你是不是想: system-A`
- system missing, no close match: output contains `已有系统:` but not `你是不是想`

### 10.4 Running

```bash
pytest tests/ -v
pytest --cov=src/doc_bridge --cov-report=term-missing
```

## 11. Rollout / backwards compatibility

- Pure addition. No existing command contract changes except the text of one error message in `atomize`.
- No schema, no state file, no prompts changed.
- Users already on doc-bridge pick up the new command after reinstalling (`pip install -e .`). Existing manually-created `raw/<name>/` directories continue to work; `add-system` is idempotent, so a user can re-run it on an existing system to materialise the `config/systems/<name>/` scaffolding after the fact.

## 12. Open questions

None at design time. Implementation plan will confirm:

- Whether any downstream code (`extractor`, `converter`, `synthesizer`) assumes the per-system `markdown/`, `atoms/`, `synthesis/` directories pre-exist. If yes, `create_system_dirs` creates them too.
- Whether `tests/conftest.py` already exists in the repository; if so, extend it instead of creating a new one.
