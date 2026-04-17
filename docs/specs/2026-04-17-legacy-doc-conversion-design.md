# Legacy Office 文档（.doc/.ppt/.xls）转换设计

**日期**: 2026-04-17
**状态**: 待实现
**关联模块**: `src/doc_bridge/core/converter.py`, 新增 `src/doc_bridge/core/soffice.py`

## 背景

`atomize` 命令通过 `markitdown` 将 `raw/<system>/*.*` 转成 `markdown/<system>/*.md`。`markitdown` 不支持二进制 `.doc/.ppt/.xls` 格式，遇到时直接报 `No converter attempted a conversion`。用户的 raw 目录混有 `.doc` 文件，导致转换流水线带着 known failure 跑完。

需在 `atomize` 的转换阶段透明处理这三类 legacy Office 格式。

## 约束与决策

| 维度 | 决策 | 理由 |
|---|---|---|
| 运行环境 | 跨平台：macOS / Linux / Windows + CI | 用户指定 |
| 覆盖格式 | `.doc`、`.ppt`、`.xls` 三类 | 用户 raw 目录常混存，边际成本接近零 |
| 转换后端 | LibreOffice (`soffice --headless`) | 纯 Python 方案对二进制 .doc 无可用库；LibreOffice 是唯一跨平台 OSS 方案 |
| 中间产物位置 | 进程内临时目录，用完即删 | 最小侵入，不引入新目录；state tracker 已吸收重跑成本 |
| 集成方式 | 独立模块 `core/soffice.py`，由 `_convert_single` 调用 | 契合现有 `core/` 模块化风格，soffice 逻辑独立可测 |
| Helper 抽象 | `_convert_single` 两个分支各自调 markitdown，不抽 helper | 只被调用两次、内部两行，抽象摩擦 > 重复成本 |

## 架构

```
raw/<system>/方案.doc
       │
       ▼
┌─────────────────────────────────────────┐
│ converter.convert_files                 │
│   (主进程预检: find_soffice 若有 legacy)│
└─────────────────────────────────────────┘
       │  ProcessPoolExecutor (max 4 workers)
       ▼
┌─────────────────────────────────────────┐
│ converter._convert_single  (worker)     │
│   ├ legacy 分支:                        │
│   │   with TemporaryDirectory as tmp:   │
│   │     soffice.convert_to_modern(...)  │◄─── soffice --headless
│   │     markitdown.convert(tmp/*.docx)  │
│   └ 非 legacy 分支:                     │
│       markitdown.convert(src)           │
└─────────────────────────────────────────┘
       │
       ▼
markdown/<system>/方案.md
```

## 模块设计

### `src/doc_bridge/core/soffice.py`（新增）

**公开 API**:

```python
LEGACY_EXTENSIONS: dict[str, str] = {
    ".doc": "docx",
    ".ppt": "pptx",
    ".xls": "xlsx",
}

class SofficeNotFoundError(RuntimeError): ...
class SofficeConversionError(RuntimeError): ...

def is_legacy(path: Path) -> bool
def find_soffice() -> Path
def convert_to_modern(src: Path, out_dir: Path, timeout: int = 120) -> Path
```

**`find_soffice` 检测顺序**（第一个命中即返回，结果用 `functools.cache` 缓存）:

1. 环境变量 `DOC_BRIDGE_SOFFICE`（显式覆盖，最高优先级）
2. `shutil.which("soffice")` → `shutil.which("libreoffice")`
3. 平台常见安装路径:
   - macOS: `/Applications/LibreOffice.app/Contents/MacOS/soffice`
   - Windows: `C:\Program Files\LibreOffice\program\soffice.exe`、`C:\Program Files (x86)\LibreOffice\program\soffice.exe`
   - Linux: `/usr/bin/soffice`、`/usr/lib/libreoffice/program/soffice`

全部失败抛 `SofficeNotFoundError`，message 根据 `sys.platform` 包含对应安装指令（brew / apt / choco / 环境变量覆盖提示）。

**`convert_to_modern` 实现要点**:

```python
def convert_to_modern(src: Path, out_dir: Path, timeout: int = 120) -> Path:
    target_ext = LEGACY_EXTENSIONS[src.suffix.lower()]
    soffice = find_soffice()

    with tempfile.TemporaryDirectory(prefix="soffice-profile-") as profile_dir:
        cmd = [
            str(soffice),
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", target_ext,
            "--outdir", str(out_dir),
            str(src),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise SofficeConversionError(
                f"soffice 转换超时 ({timeout}s): {src.name}"
            ) from e

    if result.returncode != 0:
        raise SofficeConversionError(
            f"soffice 转换失败 ({src.name}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    expected = out_dir / f"{src.stem}.{target_ext}"
    if not expected.exists():
        raise SofficeConversionError(f"soffice 返回成功但产物缺失: {expected}")
    return expected
```

**关键设计点**:
- `-env:UserInstallation=file://<tmp>`：每次调用独立用户配置目录，避免 `ProcessPoolExecutor` 下多个 soffice 进程共享 `~/Library/Application Support/LibreOffice/` 导致的锁冲突
- `--norestore --nolockcheck`：headless 下关掉崩溃恢复/锁检查，减少噪音
- `check=False` + 手动判 `returncode` + 验证产物存在：soffice 偶发 exit 0 但未生成产物，必须双重检查
- `timeout=120`：默认 2 分钟上限，大文件有余量，真卡住 kill 掉好过无限等

### `src/doc_bridge/core/converter.py`（修改）

**改动 1：`_convert_single` 加 legacy 预处理**

```python
def _convert_single(src: Path, dst: Path) -> tuple[str, bool, str]:
    try:
        from markitdown import MarkItDown
        from doc_bridge.core.soffice import LEGACY_EXTENSIONS, convert_to_modern

        if src.suffix.lower() in LEGACY_EXTENSIONS:
            with tempfile.TemporaryDirectory(prefix="doc-bridge-legacy-") as tmp:
                modern = convert_to_modern(src, Path(tmp))
                md = MarkItDown()
                result = md.convert(str(modern))
        else:
            md = MarkItDown()
            result = md.convert(str(src))

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(result.text_content, encoding="utf-8")
        return src.name, True, ""
    except Exception as e:
        return src.name, False, str(e)
```

**改动 2：`convert_files` 加预检**

在 `with ProcessPoolExecutor(...)` 之前：

```python
from doc_bridge.core.soffice import (
    LEGACY_EXTENSIONS, SofficeNotFoundError, find_soffice,
)

has_legacy = any(src.suffix.lower() in LEGACY_EXTENSIONS for src, _ in tasks)
if has_legacy:
    try:
        find_soffice()
    except SofficeNotFoundError as e:
        flow_logger.error(str(e))
        raise
```

理由：若 soffice 未安装，让整个 `atomize` 早失败并打印清晰的平台安装指令，而不是让 4 个 worker 各自失败 10 次。

## 错误处理策略

| 错误类型 | 触发位置 | 策略 | 表现 |
|---|---|---|---|
| soffice 未安装 | `convert_files` 预检 | 整体中止 | `atomize` 退出，打印平台化安装指令 |
| 单文件转换失败 | worker 内 `convert_to_modern`（exit ≠ 0 / 产物缺失 / 文件损坏） | 跳过该文件，继续其他 | 沿用现有 `转换失败: X — <原因>` 日志路径 |
| 单文件超时（> 120s） | worker 内 `subprocess.run` | 跳过该文件 | message 明示"超时"，便于区分与格式问题 |

**判定原则**：用户可一次性解决的错误（装个 soffice）→ 整体中止；文件特有问题 → 单文件跳过。

**worker 内 `except Exception` 不做特殊化**：即使 `SofficeNotFoundError` 意外到达 worker（预检后被卸载等极端场景），记一行"转换失败"也够用，不值得为零概率场景加复杂度。

## 测试计划

### 单元测试 `tests/core/test_soffice.py`（不依赖 soffice 二进制）

- `is_legacy` 大小写、正/反例
- `find_soffice` 的 env 变量覆盖、PATH 查找、libreoffice 别名回退、平台路径回退、三个平台的报错文案差异、cache 行为
- `convert_to_modern` 的成功路径、exit ≠ 0、产物缺失、`TimeoutExpired`、命令行参数（含 `-env:UserInstallation` 且每次唯一）

每个 case fixture 里 `find_soffice.cache_clear()`。

### `tests/core/test_converter.py` 扩展

- `convert_files` 在有 legacy 时调 `find_soffice`，没有 legacy 时不调（spy）
- `find_soffice` 抛异常时 `convert_files` 整体抛出，pool 未启动
- `_convert_single` legacy 分支 mock `convert_to_modern` + `MarkItDown`，验证流程
- `_convert_single` 非 legacy 分支行为保持不变

### 集成测试 `tests/integration/test_soffice_real.py`

- `pytest.skipif(not SOFFICE_AVAILABLE)` 自动跳过
- Fixture: `tests/fixtures/sample.doc`（最小 .doc 样本，<20KB）
- 验证真实调用产出 `.docx` 且可读

### CI 适配

GitHub Actions Linux runner 加 `sudo apt install libreoffice -y`，集成测试自动运行。本地用户未装不影响单测。

### 覆盖率

遵循项目 80%+ 基线；`soffice.py` 目标 ≥95%（分支少，外部依赖易 mock）。

## 范围外（明确不做）

- Windows COM (`pywin32` + Word) fallback — 对 CI 无用，暂不需要
- 转换后持久化 `.docx` 到 raw/ 或独立缓存目录 — 已选临时目录方案（Q3 = A）
- 独立的 `doc-bridge normalize` CLI 子命令 — 和透明集成方向冲突
- `.rtf` 支持 — 未在选定范围内
- `.wps` 等其他中文老格式 — 用户未提及，YAGNI

## 依赖与环境

- 新增运行时依赖：**LibreOffice**（系统级，非 Python 包）
  - macOS: `brew install --cask libreoffice`
  - Linux (Debian/Ubuntu): `apt install libreoffice`
  - Windows: `choco install libreoffice-fresh`
- 无新增 Python 包依赖
- 环境变量（可选）: `DOC_BRIDGE_SOFFICE` — 覆盖二进制路径
