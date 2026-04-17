# Legacy Office 文档转换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `doc-bridge atomize` transparently handle `.doc`, `.ppt`, `.xls` by pre-converting via LibreOffice (`soffice --headless`) before feeding them to markitdown.

**Architecture:** New `core/soffice.py` module wraps LibreOffice CLI (detect binary, invoke with isolated user profile, map errors). `core/converter.py` gains a preflight check in `convert_files` and a legacy branch in `_convert_single` that routes legacy files through `soffice.py` into a per-call `tempfile.TemporaryDirectory()` before calling markitdown.

**Tech Stack:** Python 3.10+ / `subprocess` / `shutil` / `tempfile` / `functools.cache` / pytest / LibreOffice 7+.

**Spec:** `docs/specs/2026-04-17-legacy-doc-conversion-design.md`

---

## File Structure

**New files**:
- `src/doc_bridge/core/soffice.py` — LibreOffice wrapper
- `tests/core/__init__.py` — new test package marker
- `tests/core/test_soffice.py` — unit tests for soffice wrapper
- `tests/core/test_converter.py` — unit tests for converter.py (expands the previously test-less module)
- `tests/integration/__init__.py` — new integration package marker
- `tests/integration/test_soffice_real.py` — real soffice invocation (skip if missing)
- `tests/fixtures/sample.doc` — minimal binary `.doc` fixture (~15 KB)

**Modified files**:
- `src/doc_bridge/core/converter.py` — two small edits: preflight + legacy branch
- `README.md` — add LibreOffice to install prerequisites

---

## Task 1: Scaffold `soffice.py` with constants, exceptions, and `is_legacy`

**Files:**
- Create: `src/doc_bridge/core/soffice.py`
- Create: `tests/core/__init__.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Create empty test package marker**

```bash
mkdir -p tests/core
: > tests/core/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_soffice.py`:

```python
"""Unit tests for core/soffice.py."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_legacy_extensions_mapping():
    from doc_bridge.core.soffice import LEGACY_EXTENSIONS

    assert LEGACY_EXTENSIONS == {
        ".doc": "docx",
        ".ppt": "pptx",
        ".xls": "xlsx",
    }


@pytest.mark.parametrize(
    "name",
    ["a.doc", "A.DOC", "deck.ppt", "DECK.PPT", "data.xls", "Data.XLS"],
)
def test_is_legacy_true(name: str):
    from doc_bridge.core.soffice import is_legacy

    assert is_legacy(Path(name)) is True


@pytest.mark.parametrize(
    "name",
    ["a.docx", "deck.pptx", "data.xlsx", "readme.md", "paper.pdf", "notes.txt"],
)
def test_is_legacy_false(name: str):
    from doc_bridge.core.soffice import is_legacy

    assert is_legacy(Path(name)) is False


def test_exceptions_are_runtime_errors():
    from doc_bridge.core.soffice import (
        SofficeConversionError,
        SofficeNotFoundError,
    )

    assert issubclass(SofficeNotFoundError, RuntimeError)
    assert issubclass(SofficeConversionError, RuntimeError)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/core/test_soffice.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'doc_bridge.core.soffice'`

- [ ] **Step 4: Create the module**

Create `src/doc_bridge/core/soffice.py`:

```python
"""LibreOffice (soffice) wrapper for converting legacy Office formats."""

from __future__ import annotations

from pathlib import Path

LEGACY_EXTENSIONS: dict[str, str] = {
    ".doc": "docx",
    ".ppt": "pptx",
    ".xls": "xlsx",
}


class SofficeNotFoundError(RuntimeError):
    """Raised when the LibreOffice (soffice) binary cannot be located."""


class SofficeConversionError(RuntimeError):
    """Raised when soffice fails to convert a file."""


def is_legacy(path: Path) -> bool:
    """Return True if the file extension is one of the legacy Office formats."""
    return path.suffix.lower() in LEGACY_EXTENSIONS
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: 10 passed (1 mapping + 6 true + 6 false − parametrize expands; real count: 1 + 6 + 6 + 1 = 14, passed=14)

- [ ] **Step 6: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/__init__.py tests/core/test_soffice.py
git commit -m "feat(soffice): scaffold module with legacy extension map and exceptions"
```

---

## Task 2: `find_soffice` — environment variable override

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_soffice.py`:

```python
@pytest.fixture(autouse=True)
def _clear_soffice_cache():
    """find_soffice uses functools.cache; clear between tests."""
    from doc_bridge.core import soffice

    soffice.find_soffice.cache_clear()
    yield
    soffice.find_soffice.cache_clear()


def test_find_soffice_from_env(monkeypatch, tmp_path: Path):
    fake = tmp_path / "soffice"
    fake.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake))

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == fake
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_soffice.py::test_find_soffice_from_env -v`
Expected: FAIL with `ImportError: cannot import name 'find_soffice'`

- [ ] **Step 3: Add minimal `find_soffice`**

Edit `src/doc_bridge/core/soffice.py`. Add imports at the top:

```python
from __future__ import annotations

import functools
import os
from pathlib import Path
```

Append to the module:

```python
@functools.cache
def find_soffice() -> Path:
    """Locate the soffice binary. Cached per-process."""
    override = os.environ.get("DOC_BRIDGE_SOFFICE")
    if override:
        return Path(override)

    raise SofficeNotFoundError("soffice not found")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_soffice.py::test_find_soffice_from_env -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): support DOC_BRIDGE_SOFFICE env var override for find_soffice"
```

---

## Task 3: `find_soffice` — PATH lookup with `soffice` and `libreoffice` aliases

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/core/test_soffice.py`:

```python
def test_find_soffice_from_path_soffice(monkeypatch, tmp_path: Path):
    fake = tmp_path / "soffice"
    fake.touch()
    monkeypatch.delenv("DOC_BRIDGE_SOFFICE", raising=False)

    def fake_which(name: str) -> str | None:
        return str(fake) if name == "soffice" else None

    monkeypatch.setattr("shutil.which", fake_which)

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == fake


def test_find_soffice_falls_back_to_libreoffice_alias(monkeypatch, tmp_path: Path):
    fake = tmp_path / "libreoffice"
    fake.touch()
    monkeypatch.delenv("DOC_BRIDGE_SOFFICE", raising=False)

    calls: list[str] = []

    def fake_which(name: str) -> str | None:
        calls.append(name)
        return str(fake) if name == "libreoffice" else None

    monkeypatch.setattr("shutil.which", fake_which)

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == fake
    assert calls == ["soffice", "libreoffice"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_soffice.py -v -k find_soffice_from_path or find_soffice_falls_back`
Expected: both FAIL with `SofficeNotFoundError`

- [ ] **Step 3: Add PATH lookup to `find_soffice`**

Edit `src/doc_bridge/core/soffice.py`. Add `import shutil` to the imports. Replace the `find_soffice` body:

```python
@functools.cache
def find_soffice() -> Path:
    """Locate the soffice binary. Cached per-process."""
    override = os.environ.get("DOC_BRIDGE_SOFFICE")
    if override:
        return Path(override)

    for candidate in ("soffice", "libreoffice"):
        found = shutil.which(candidate)
        if found:
            return Path(found)

    raise SofficeNotFoundError("soffice not found")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all tests so far PASS

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): look up soffice/libreoffice via PATH"
```

---

## Task 4: `find_soffice` — platform-specific fallback paths

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/core/test_soffice.py`:

```python
@pytest.fixture
def _no_env_no_path(monkeypatch):
    monkeypatch.delenv("DOC_BRIDGE_SOFFICE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)


def test_find_soffice_macos_fallback(monkeypatch, tmp_path: Path, _no_env_no_path):
    mac_path = tmp_path / "LibreOffice.app/Contents/MacOS/soffice"
    mac_path.parent.mkdir(parents=True)
    mac_path.touch()

    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(
        "doc_bridge.core.soffice._MACOS_CANDIDATES",
        (mac_path,),
    )

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == mac_path


def test_find_soffice_linux_fallback(monkeypatch, tmp_path: Path, _no_env_no_path):
    linux_path = tmp_path / "usr/bin/soffice"
    linux_path.parent.mkdir(parents=True)
    linux_path.touch()

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(
        "doc_bridge.core.soffice._LINUX_CANDIDATES",
        (linux_path,),
    )

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == linux_path


def test_find_soffice_windows_fallback(monkeypatch, tmp_path: Path, _no_env_no_path):
    win_path = tmp_path / "Program Files/LibreOffice/program/soffice.exe"
    win_path.parent.mkdir(parents=True)
    win_path.touch()

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(
        "doc_bridge.core.soffice._WINDOWS_CANDIDATES",
        (win_path,),
    )

    from doc_bridge.core.soffice import find_soffice

    assert find_soffice() == win_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_soffice.py -v -k "fallback"`
Expected: 3 FAIL (module has no `_MACOS_CANDIDATES` etc.)

- [ ] **Step 3: Add platform fallback candidates**

Edit `src/doc_bridge/core/soffice.py`. Add `import sys` to the imports. After `LEGACY_EXTENSIONS`:

```python
_MACOS_CANDIDATES: tuple[Path, ...] = (
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
)
_LINUX_CANDIDATES: tuple[Path, ...] = (
    Path("/usr/bin/soffice"),
    Path("/usr/bin/libreoffice"),
    Path("/usr/lib/libreoffice/program/soffice"),
)
_WINDOWS_CANDIDATES: tuple[Path, ...] = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)


def _platform_candidates() -> tuple[Path, ...]:
    if sys.platform == "darwin":
        return _MACOS_CANDIDATES
    if sys.platform == "win32":
        return _WINDOWS_CANDIDATES
    return _LINUX_CANDIDATES
```

Update `find_soffice` to check candidates before raising:

```python
@functools.cache
def find_soffice() -> Path:
    """Locate the soffice binary. Cached per-process."""
    override = os.environ.get("DOC_BRIDGE_SOFFICE")
    if override:
        return Path(override)

    for candidate in ("soffice", "libreoffice"):
        found = shutil.which(candidate)
        if found:
            return Path(found)

    for path in _platform_candidates():
        if path.exists():
            return path

    raise SofficeNotFoundError("soffice not found")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): platform-specific fallback paths for binary detection"
```

---

## Task 5: `find_soffice` — not-found error with platform-specific hints

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/core/test_soffice.py`:

```python
def _force_not_found(monkeypatch):
    monkeypatch.delenv("DOC_BRIDGE_SOFFICE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "doc_bridge.core.soffice._platform_candidates", lambda: ()
    )


def test_find_soffice_not_found_macos(monkeypatch):
    _force_not_found(monkeypatch)
    monkeypatch.setattr("sys.platform", "darwin")

    from doc_bridge.core.soffice import SofficeNotFoundError, find_soffice

    with pytest.raises(SofficeNotFoundError) as exc:
        find_soffice()
    assert "brew install" in str(exc.value)
    assert "DOC_BRIDGE_SOFFICE" in str(exc.value)


def test_find_soffice_not_found_linux(monkeypatch):
    _force_not_found(monkeypatch)
    monkeypatch.setattr("sys.platform", "linux")

    from doc_bridge.core.soffice import SofficeNotFoundError, find_soffice

    with pytest.raises(SofficeNotFoundError) as exc:
        find_soffice()
    assert "apt install" in str(exc.value)


def test_find_soffice_not_found_windows(monkeypatch):
    _force_not_found(monkeypatch)
    monkeypatch.setattr("sys.platform", "win32")

    from doc_bridge.core.soffice import SofficeNotFoundError, find_soffice

    with pytest.raises(SofficeNotFoundError) as exc:
        find_soffice()
    assert "choco install" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_soffice.py -v -k not_found`
Expected: 3 FAIL (message doesn't contain install hints)

- [ ] **Step 3: Improve the error message**

Edit `src/doc_bridge/core/soffice.py`. Add this function above `find_soffice`:

```python
def _install_hint() -> str:
    if sys.platform == "darwin":
        cmd = "brew install --cask libreoffice"
    elif sys.platform == "win32":
        cmd = "choco install libreoffice-fresh  (or download from libreoffice.org)"
    else:
        cmd = "apt install libreoffice  (or equivalent for your distro)"
    return (
        "未找到 LibreOffice (soffice)。处理 .doc/.ppt/.xls 需要它。\n"
        f"  安装: {cmd}\n"
        "  已安装但没找到？设置环境变量 DOC_BRIDGE_SOFFICE=/path/to/soffice"
    )
```

Replace the raise in `find_soffice`:

```python
    raise SofficeNotFoundError(_install_hint())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): platform-specific install hints in not-found error"
```

---

## Task 6: `convert_to_modern` — success path with isolated UserInstallation

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_soffice.py`:

```python
def test_convert_to_modern_success(monkeypatch, tmp_path: Path):
    # Set up fake soffice
    fake_soffice = tmp_path / "soffice"
    fake_soffice.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake_soffice))

    # Source .doc file (content irrelevant; we mock subprocess)
    src = tmp_path / "input.doc"
    src.write_bytes(b"dummy")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Capture the subprocess call and simulate a produced file.
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        (out_dir / "input.docx").write_bytes(b"produced")

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    from doc_bridge.core.soffice import convert_to_modern

    result = convert_to_modern(src, out_dir)
    assert result == out_dir / "input.docx"
    assert result.read_bytes() == b"produced"

    cmd = captured["cmd"]
    assert str(fake_soffice) in cmd
    assert "--headless" in cmd
    assert "--convert-to" in cmd
    assert "docx" in cmd
    assert "--outdir" in cmd
    assert str(out_dir) in cmd
    assert str(src) in cmd
    assert any(arg.startswith("-env:UserInstallation=file://") for arg in cmd)


def test_convert_to_modern_user_installation_is_unique(monkeypatch, tmp_path: Path):
    fake_soffice = tmp_path / "soffice"
    fake_soffice.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake_soffice))

    src = tmp_path / "input.doc"
    src.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    seen: list[str] = []

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-env:UserInstallation="):
                seen.append(arg)
        (out_dir / "input.docx").write_bytes(b"x")

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    from doc_bridge.core.soffice import convert_to_modern

    convert_to_modern(src, out_dir)
    # Remove stale output so second call re-creates it
    (out_dir / "input.docx").unlink()
    convert_to_modern(src, out_dir)

    assert len(seen) == 2
    assert seen[0] != seen[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_soffice.py -v -k convert_to_modern_success`
Expected: FAIL with `ImportError: cannot import name 'convert_to_modern'`

- [ ] **Step 3: Implement `convert_to_modern`**

Edit `src/doc_bridge/core/soffice.py`. Add to imports:

```python
import subprocess
import tempfile
```

Append at the end of the module:

```python
def convert_to_modern(src: Path, out_dir: Path, timeout: int = 120) -> Path:
    """Convert a legacy .doc/.ppt/.xls to its modern counterpart in out_dir."""
    target_ext = LEGACY_EXTENSIONS[src.suffix.lower()]
    soffice = find_soffice()

    with tempfile.TemporaryDirectory(prefix="soffice-profile-") as profile_dir:
        cmd = [
            str(soffice),
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to",
            target_ext,
            "--outdir",
            str(out_dir),
            str(src),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    expected = out_dir / f"{src.stem}.{target_ext}"
    if not expected.exists():
        raise SofficeConversionError(
            f"soffice 返回成功但产物缺失: {expected}"
        )
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all pass (error paths tested in Task 7-9)

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): convert_to_modern happy path with isolated user profile"
```

---

## Task 7: `convert_to_modern` — non-zero exit maps to SofficeConversionError

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_soffice.py`:

```python
def test_convert_to_modern_nonzero_exit(monkeypatch, tmp_path: Path):
    fake_soffice = tmp_path / "soffice"
    fake_soffice.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake_soffice))

    src = tmp_path / "input.doc"
    src.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 77
            stdout = "out message"
            stderr = "broken ole stream"

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    from doc_bridge.core.soffice import (
        SofficeConversionError,
        convert_to_modern,
    )

    with pytest.raises(SofficeConversionError) as exc:
        convert_to_modern(src, out_dir)
    assert "input.doc" in str(exc.value)
    assert "broken ole stream" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_soffice.py -v -k nonzero_exit`
Expected: FAIL — currently the function raises `SofficeConversionError` with "产物缺失" instead of stderr

- [ ] **Step 3: Add non-zero-exit branch**

Edit `src/doc_bridge/core/soffice.py`. In `convert_to_modern`, insert before `expected = ...`:

```python
    if result.returncode != 0:
        raise SofficeConversionError(
            f"soffice 转换失败 ({src.name}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): map non-zero soffice exit to SofficeConversionError"
```

---

## Task 8: `convert_to_modern` — missing output maps to SofficeConversionError

This case is already covered by the `expected.exists()` check in Task 6, but needs explicit test coverage.

**Files:**
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the test**

Append to `tests/core/test_soffice.py`:

```python
def test_convert_to_modern_missing_output(monkeypatch, tmp_path: Path):
    fake_soffice = tmp_path / "soffice"
    fake_soffice.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake_soffice))

    src = tmp_path / "input.doc"
    src.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()  # no output file produced

    monkeypatch.setattr("subprocess.run", fake_run)

    from doc_bridge.core.soffice import (
        SofficeConversionError,
        convert_to_modern,
    )

    with pytest.raises(SofficeConversionError) as exc:
        convert_to_modern(src, out_dir)
    assert "产物缺失" in str(exc.value)
    assert "input.docx" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `pytest tests/core/test_soffice.py -v -k missing_output`
Expected: PASS (behavior already implemented in Task 6)

- [ ] **Step 3: Commit the coverage**

```bash
git add tests/core/test_soffice.py
git commit -m "test(soffice): cover missing-output error path explicitly"
```

---

## Task 9: `convert_to_modern` — timeout maps to SofficeConversionError

**Files:**
- Modify: `src/doc_bridge/core/soffice.py`
- Test: `tests/core/test_soffice.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_soffice.py`:

```python
def test_convert_to_modern_timeout(monkeypatch, tmp_path: Path):
    import subprocess

    fake_soffice = tmp_path / "soffice"
    fake_soffice.touch()
    monkeypatch.setenv("DOC_BRIDGE_SOFFICE", str(fake_soffice))

    src = tmp_path / "input.doc"
    src.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr("subprocess.run", fake_run)

    from doc_bridge.core.soffice import (
        SofficeConversionError,
        convert_to_modern,
    )

    with pytest.raises(SofficeConversionError) as exc:
        convert_to_modern(src, out_dir, timeout=5)
    assert "超时" in str(exc.value)
    assert "5" in str(exc.value)
    assert "input.doc" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_soffice.py -v -k timeout`
Expected: FAIL — raw `TimeoutExpired` leaks out, not wrapped

- [ ] **Step 3: Wrap TimeoutExpired**

Edit `src/doc_bridge/core/soffice.py`. Replace the `subprocess.run(...)` call in `convert_to_modern` with:

```python
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise SofficeConversionError(
                f"soffice 转换超时 ({timeout}s): {src.name}"
            ) from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_soffice.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/soffice.py tests/core/test_soffice.py
git commit -m "feat(soffice): wrap subprocess timeout as SofficeConversionError"
```

---

## Task 10: `convert_files` preflight detects missing soffice for legacy inputs

**Files:**
- Modify: `src/doc_bridge/core/converter.py`
- Create: `tests/core/test_converter.py`

- [ ] **Step 1: Create the test file with failing tests**

Create `tests/core/test_converter.py`:

```python
"""Unit tests for core/converter.py."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


def _make_workspace(tmp_path: Path):
    from doc_bridge.models.config import WorkspaceConfig

    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "raw").mkdir(exist_ok=True)
    (tmp_path / "markdown").mkdir(exist_ok=True)
    (tmp_path / "atoms").mkdir(exist_ok=True)
    (tmp_path / "synthesis").mkdir(exist_ok=True)
    return WorkspaceConfig(root=tmp_path)


def test_preflight_raises_when_legacy_present_and_soffice_missing(
    monkeypatch, tmp_path: Path
):
    from doc_bridge.core import converter, soffice

    soffice.find_soffice.cache_clear()

    ws = _make_workspace(tmp_path)
    raw_dir = tmp_path / "raw" / "sys"
    raw_dir.mkdir(parents=True)
    doc = raw_dir / "a.doc"
    doc.write_bytes(b"x")

    def raise_missing():
        raise soffice.SofficeNotFoundError("missing")

    monkeypatch.setattr("doc_bridge.core.soffice.find_soffice", raise_missing)

    flow_logger = logging.getLogger("test_preflight_missing")

    with pytest.raises(soffice.SofficeNotFoundError):
        converter.convert_files(ws, "sys", [doc], flow_logger)


def test_preflight_skipped_when_no_legacy(monkeypatch, tmp_path: Path):
    from doc_bridge.core import converter, soffice

    soffice.find_soffice.cache_clear()

    ws = _make_workspace(tmp_path)
    raw_dir = tmp_path / "raw" / "sys"
    raw_dir.mkdir(parents=True)
    pdf = raw_dir / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    calls = {"count": 0}

    def fake_find():
        calls["count"] += 1
        raise soffice.SofficeNotFoundError("should not be called")

    monkeypatch.setattr("doc_bridge.core.soffice.find_soffice", fake_find)

    # Stub out the actual pool-based conversion so the test stays unit-scope.
    monkeypatch.setattr(
        "doc_bridge.core.converter._convert_single",
        lambda src, dst: (src.name, True, ""),
    )
    # Also stub the pool to avoid spinning workers; use a synchronous shim.
    class _SyncPool:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def submit(self, fn, *args, **kwargs):
            class _F:
                def __init__(self, value):
                    self._value = value

                def result(self):
                    return self._value

            return _F(fn(*args, **kwargs))

    monkeypatch.setattr(
        "doc_bridge.core.converter.ProcessPoolExecutor", _SyncPool
    )
    monkeypatch.setattr(
        "doc_bridge.core.converter.as_completed", lambda fs: list(fs)
    )

    flow_logger = logging.getLogger("test_preflight_skipped")
    converter.convert_files(ws, "sys", [pdf], flow_logger)

    assert calls["count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_converter.py -v`
Expected: `test_preflight_raises_*` FAIL (no preflight yet); `test_preflight_skipped_*` may pass if pool stubs work, but better to confirm with `-v`.

- [ ] **Step 3: Add preflight to `convert_files`**

Edit `src/doc_bridge/core/converter.py`. Replace the whole file with:

```python
"""Document to Markdown conversion using markitdown (no LLM)."""

from __future__ import annotations

import logging
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from doc_bridge.core.soffice import (
    LEGACY_EXTENSIONS,
    SofficeNotFoundError,
    convert_to_modern,
    find_soffice,
)
from doc_bridge.models.config import WorkspaceConfig

logger = logging.getLogger("doc_bridge.converter")


def _convert_single(src: Path, dst: Path) -> tuple[str, bool, str]:
    """Convert a single file. Runs in a worker process."""
    try:
        from markitdown import MarkItDown

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


def convert_files(
    ws: WorkspaceConfig,
    system: str,
    files: list[Path],
    flow_logger: logging.Logger,
) -> list[tuple[Path, Path]]:
    """Convert raw files to markdown using ProcessPoolExecutor.

    Returns list of (raw_path, markdown_path) for successfully converted files.
    """
    md_dir = ws.system_markdown_dir(system)
    md_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[Path, Path]] = []
    for f in files:
        dst = md_dir / f"{f.stem}.md"
        tasks.append((f, dst))

    if not tasks:
        return []

    has_legacy = any(src.suffix.lower() in LEGACY_EXTENSIONS for src, _ in tasks)
    if has_legacy:
        try:
            find_soffice()
        except SofficeNotFoundError as e:
            flow_logger.error(str(e))
            raise

    results: list[tuple[Path, Path]] = []
    max_workers = min(len(tasks), 4)

    flow_logger.info(f"转换开始: {len(tasks)} 个文件, workers={max_workers}")

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_convert_single, src, dst): (src, dst)
            for src, dst in tasks
        }
        for future in as_completed(futures):
            src, dst = futures[future]
            name, success, error = future.result()
            if success:
                flow_logger.info(f"转换完成: {name} → {dst.name}")
                results.append((src, dst))
            else:
                flow_logger.error(f"转换失败: {name} — {error}")

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/ -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/doc_bridge/core/converter.py tests/core/test_converter.py
git commit -m "feat(converter): preflight soffice and route legacy files through it"
```

---

## Task 11: Unit-test `_convert_single` legacy and modern branches

**Files:**
- Modify: `tests/core/test_converter.py`

- [ ] **Step 1: Append branch tests**

Append to `tests/core/test_converter.py`:

```python
def test_convert_single_legacy_branch(monkeypatch, tmp_path: Path):
    from doc_bridge.core import converter

    src = tmp_path / "input.doc"
    src.write_bytes(b"ignored")
    dst = tmp_path / "out.md"

    def fake_convert_to_modern(src_path, out_dir, timeout=120):
        target = out_dir / "input.docx"
        target.write_bytes(b"converted")
        return target

    class FakeResult:
        text_content = "# converted"

    class FakeMarkItDown:
        def convert(self, path):
            assert path.endswith("input.docx")
            return FakeResult()

    monkeypatch.setattr(
        "doc_bridge.core.converter.convert_to_modern", fake_convert_to_modern
    )
    monkeypatch.setattr("markitdown.MarkItDown", FakeMarkItDown)

    name, ok, err = converter._convert_single(src, dst)

    assert ok is True
    assert err == ""
    assert name == "input.doc"
    assert dst.read_text(encoding="utf-8") == "# converted"


def test_convert_single_modern_branch_unchanged(monkeypatch, tmp_path: Path):
    from doc_bridge.core import converter

    src = tmp_path / "input.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    dst = tmp_path / "out.md"

    called = {"convert_to_modern": 0}

    def fake_convert_to_modern(*args, **kwargs):
        called["convert_to_modern"] += 1
        raise AssertionError("should not be called for pdf")

    class FakeResult:
        text_content = "# pdf body"

    class FakeMarkItDown:
        def convert(self, path):
            assert path.endswith("input.pdf")
            return FakeResult()

    monkeypatch.setattr(
        "doc_bridge.core.converter.convert_to_modern", fake_convert_to_modern
    )
    monkeypatch.setattr("markitdown.MarkItDown", FakeMarkItDown)

    name, ok, err = converter._convert_single(src, dst)

    assert ok is True
    assert called["convert_to_modern"] == 0
    assert dst.read_text(encoding="utf-8") == "# pdf body"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/core/test_converter.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_converter.py
git commit -m "test(converter): cover legacy and modern branches of _convert_single"
```

---

## Task 12: Real soffice integration test (skip if missing)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_soffice_real.py`
- Create: `tests/fixtures/sample.doc`

- [ ] **Step 1: Set up integration package marker**

```bash
mkdir -p tests/integration tests/fixtures
: > tests/integration/__init__.py
```

- [ ] **Step 2: Create the fixture `.doc`**

On any machine with LibreOffice installed:

```bash
cat > /tmp/sample.txt <<'EOF'
Hello legacy .doc fixture.

This file exists to exercise the doc-bridge soffice wrapper
on a real binary .doc (not .docx).
EOF
soffice --headless --convert-to doc --outdir tests/fixtures /tmp/sample.txt
ls -la tests/fixtures/sample.doc
file tests/fixtures/sample.doc
```

Expected: file exists, size ~15–25 KB, `file` reports "Composite Document File V2 Document".

- [ ] **Step 3: Write the integration test**

Create `tests/integration/test_soffice_real.py`:

```python
"""Real end-to-end soffice invocation. Skipped if soffice is absent."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from doc_bridge.core.soffice import find_soffice

    find_soffice()
    _SOFFICE_AVAILABLE = True
except Exception:
    _SOFFICE_AVAILABLE = False

requires_soffice = pytest.mark.skipif(
    not _SOFFICE_AVAILABLE, reason="requires LibreOffice (soffice)"
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.doc"


@requires_soffice
@pytest.mark.integration
def test_real_doc_to_docx(tmp_path: Path):
    from doc_bridge.core.soffice import convert_to_modern

    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"

    out = convert_to_modern(FIXTURE, tmp_path)

    assert out.suffix == ".docx"
    assert out.exists()
    assert out.stat().st_size > 0
    # Basic sanity: .docx is a ZIP; first bytes should be PK
    assert out.read_bytes()[:2] == b"PK"
```

- [ ] **Step 4: Register the `integration` marker**

Edit `pyproject.toml`. Replace the existing `[tool.pytest.ini_options]` block with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: tests that require external tooling (LibreOffice, network, ...)",
]
```

- [ ] **Step 5: Run the integration test locally**

Run: `pytest tests/integration/test_soffice_real.py -v`
Expected: on a machine with LibreOffice → PASS. On a machine without → SKIPPED.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_soffice_real.py tests/fixtures/sample.doc pyproject.toml
git commit -m "test(soffice): real-binary integration test gated on LibreOffice availability"
```

---

## Task 13: README — document the LibreOffice prerequisite

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the install section**

Edit `README.md`. Replace the "### 安装" block (around line 30) with:

```markdown
### 安装

```bash
git clone https://github.com/BeamusWayne/doc-bridge.git
cd doc-bridge
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

处理 `.doc` / `.ppt` / `.xls` 等二进制老格式需要 **LibreOffice**（系统级依赖，非 Python 包）：

| 平台 | 安装命令 |
|---|---|
| macOS | `brew install --cask libreoffice` |
| Debian/Ubuntu | `sudo apt install libreoffice` |
| Windows | `choco install libreoffice-fresh` 或从 [libreoffice.org](https://www.libreoffice.org) 下载 |

若已安装但 doc-bridge 没找到，可设 `DOC_BRIDGE_SOFFICE=/path/to/soffice` 覆盖自动检测。新格式（`.docx`/`.pptx`/`.xlsx`）和 `.pdf` 不需要 LibreOffice。
```

- [ ] **Step 2: Verify the file still renders**

Run: `grep -n "LibreOffice" README.md`
Expected: new block found; also confirms the existing line 26 mention still exists.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document LibreOffice prerequisite for legacy Office conversion"
```

---

## Final Verification

- [ ] **Run the full test suite**

Run: `pytest --cov=src --cov-report=term-missing`
Expected:
- all unit tests in `tests/core/` pass
- `tests/integration/test_soffice_real.py` passes locally (or skips in CI without LibreOffice)
- coverage for `src/doc_bridge/core/soffice.py` ≥ 95%; overall coverage ≥ 80%

- [ ] **Try the real pipeline**

On a machine with LibreOffice installed, in a workspace that has a `.doc` under `raw/<system>/`:

```bash
doc-bridge atomize --system <system>
```

Expected: the `.doc` no longer appears as "转换失败: Could not convert stream to Markdown". It converts successfully and the atomize pipeline proceeds to LLM extraction.
