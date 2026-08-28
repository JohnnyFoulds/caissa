"""
tests/unit/retro/test_completeness.py — Phase 10 production-readiness invariants.

Enforces:
- N-RETRO-7: every public callable in Code.Retro has a non-trivial docstring
- N-RETRO-11: importing classical mode does not pull in Code.Retro
- No wall-clock call (time.time / time.monotonic / time.sleep) in the think path

:spec: feature_spec.md §10, N-RETRO-7, N-RETRO-11, NFR-2
:phase: 10
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.retro

_REPO_ROOT = Path(__file__).parents[3]
_RETRO_PKG = _REPO_ROOT / "bin" / "Code" / "Retro"
_BIN = _REPO_ROOT / "bin"

_THINK_PATH_MODULES = [
    _RETRO_PKG / "Think.py",
    _RETRO_PKG / "Bridge.py",
    _RETRO_PKG / "Traps.py",
]

_WALLCLOCK_NAMES = frozenset({"time", "monotonic", "perf_counter", "sleep", "clock"})


# ---------------------------------------------------------------------------
# N-RETRO-7: docstring completeness
# ---------------------------------------------------------------------------

def _has_meaningful_docstring(node) -> bool:
    """Return True if the node has a docstring with >= 5 non-whitespace chars."""
    if not (node.body and isinstance(node.body[0], ast.Expr)):
        return False
    val = node.body[0].value
    if not isinstance(val, ast.Constant):
        return False
    text = str(val.value).strip()
    return len(text) >= 5


def test_retro_completeness_every_public_callable_has_docstring():
    """Every public module, class, and function in Code.Retro must have a docstring.

    :spec: N-RETRO-7
    """
    missing: list[str] = []

    for path in sorted(_RETRO_PKG.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(rel))

        # Check module-level docstring
        if not _has_meaningful_docstring(tree):
            missing.append(f"{rel}: module")

        # Check classes and functions at top level and in classes
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue  # private — exempt
                if not _has_meaningful_docstring(node):
                    missing.append(f"{rel}: function {node.name!r} (line {node.lineno})")
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                if not _has_meaningful_docstring(node):
                    missing.append(f"{rel}: class {node.name!r} (line {node.lineno})")

    assert not missing, (
        "Public callables without docstrings (N-RETRO-7):\n"
        + "\n".join(f"  {m}" for m in sorted(missing))
    )


# ---------------------------------------------------------------------------
# N-RETRO-11: classical mode does not import Code.Retro
# ---------------------------------------------------------------------------

def test_classical_start_does_not_import_code_retro():
    """Importing UIModes (classical mode entry point) must not pull in Code.Retro.

    :spec: N-RETRO-11
    """
    bin_path = str(_BIN)
    script = (
        "import sys; "
        f"sys.path.insert(0, {bin_path!r}); "
        "import Code.UIModes; "
        "retro_mods = [k for k in sys.modules if 'Retro' in k]; "
        "assert not retro_mods, f'Code.Retro leaked into classical mode: {retro_mods!r}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15,
        env={**__import__("os").environ, "PYTHONPATH": bin_path},
    )
    # UIModes may fail to import (Qt not available) — that's acceptable.
    # What we must NOT see is Code.Retro appearing in sys.modules.
    if result.returncode != 0 and "Code.Retro" not in (result.stderr + result.stdout):
        pytest.skip("UIModes failed to import (Qt not available in headless environment)")
    assert result.returncode == 0, (
        f"Code.Retro leaked into classical mode import:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Wall-clock audit: no time.time/monotonic/sleep in think path
# ---------------------------------------------------------------------------

def _ast_uses_wallclock(path: Path) -> list[str]:
    """Return a list of 'name (line N)' for each wall-clock call in *path*."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in _WALLCLOCK_NAMES:
                hits.append(f"{node.attr} (line {node.lineno})")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _WALLCLOCK_NAMES:
                hits.append(f"{node.func.id} (line {node.lineno})")
    return hits


def test_no_wallclock_call_in_think_path():
    """Think.py, Bridge.py, and Traps.py must not call wall-clock functions (NFR-2).

    :spec: NFR-2 — deterministic replay; wall-clock calls break reproducibility
    """
    violations: list[str] = []
    for path in _THINK_PATH_MODULES:
        if not path.exists():
            continue
        hits = _ast_uses_wallclock(path)
        for hit in hits:
            violations.append(f"{path.relative_to(_REPO_ROOT)}: {hit}")

    assert not violations, (
        "Wall-clock calls found in think path (NFR-2 violation):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
