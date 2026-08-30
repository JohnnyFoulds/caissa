"""
tests/unit/fritz/test_completeness.py — Structural completeness checks for the Fritz package.

Extends ``tests/unit/rpa/test_completeness.py`` with two additions:

1. **Transitive import resolution** — ``Game``/``Move`` import ``Nags`` which imports
   ``QtGui``, so a module that imports only ``Code.Base.Game`` is Qt-tainted without a
   direct ``PySide6`` line.  The allowlist check here resolves transitively.

2. **feature_steps.md test-name parity** — same mechanism as the RPA version but
   pointed at ``docs/features/fritz-polish/feature_steps.md`` and fails (does not skip)
   on a missing file, so a mistyped path cannot silently disable the check.

:spec: NFR-5, §4 (feature_spec.md)
"""

from __future__ import annotations

import ast
import os
import re
import sys

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fritz_root() -> str:
    """Absolute path to ``bin/Code/Fritz/``."""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "bin", "Code", "Fritz")
    )


def _all_fritz_py_files() -> list[str]:
    """All .py files under ``bin/Code/Fritz/``."""
    paths = []
    for dirpath, _, filenames in os.walk(_fritz_root()):
        for fn in filenames:
            if fn.endswith(".py"):
                paths.append(os.path.join(dirpath, fn))
    return paths


def _direct_imports(source: str, filename: str) -> list[str]:
    """Return all module names directly imported in *source*."""
    names: list[str] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def _contains_pyside6(source: str, filename: str) -> bool:
    """Return True if *source* directly imports anything from PySide6."""
    for name in _direct_imports(source, filename):
        if "PySide6" in (name or ""):
            return True
    return False


# Module names (relative to bin/Code/Fritz/) allowed to import PySide6 directly.
# Grows as widget modules are added — Phase 3 adds WFritzPane.py.
_PYSIDE6_ALLOWED_RELATIVE: set[str] = {
    "WFritzPane.py",
    "WFritzLCD.py",
    # Phase 5: FritzEtiquetaPGN delegate — Qt allowlist tier.
    "Delegates.py",
    # Phase 7: Ribbon widget and wiring — Qt allowlist tier.
    "WRibbon.py",
    "Ribbon.py",
    # Phase 2 (fritz-mode-phase2): Dropdown panel — Qt allowlist tier.
    "WDropdownPanel.py",
    # Phase 6 (fritz-mode-phase6): WFritz* widgets moved from UIModes/ — Qt allowlist tier.
    "WFritzAnalysisTable.py",
    "WFritzEvalGraph.py",
    "WFritzPlayerHeader.py",
    "WFritzNewGame.py",
}

# Adapter-tier modules (relative to bin/Code/Fritz/) that may import Qt-tainted
# upstream code without being in the full PySide6 allowlist.  They cannot import
# PySide6 directly — they merely call upstream functions that happen to use Qt
# internally (e.g. Nags.nag_color returns a QColor).
_ADAPTER_TAINT_ALLOWED_RELATIVE: set[str] = {
    "ThemeGateway.py",
    "ModeGateway.py",
    "ConfigGateway.py",
    "GeometryStore.py",
    "EngineGateway.py",   # reads Code.procesador — Qt-tainted via Code.*
}

# Qt-tainted upstream modules: importing these makes a module Qt-tainted even
# without a direct PySide6 import.  Validated against bin/Code/ in
# test_qt_taint_list_is_accurate below.
_QT_TAINTED_UPSTREAM = frozenset({
    "Code.Base.Game",
    "Code.Base.Move",
    "Code.Nags.Nags",
})


def _resolve_tainted_transitively(source: str, filename: str, visited: set[str] | None = None) -> bool:
    """Return True if *source* is Qt-tainted directly or via a tainted upstream import.

    Direct PySide6 imports and imports of any module in ``_QT_TAINTED_UPSTREAM``
    are both considered tainted.

    :param source: Python source text.
    :param filename: Used for AST error messages.
    :param visited: Recursion guard (internal).
    """
    if _contains_pyside6(source, filename):
        return True
    for name in _direct_imports(source, filename):
        if name in _QT_TAINTED_UPSTREAM:
            return True
    return False


# ---------------------------------------------------------------------------
# Test: PySide6 import allowlist (transitive)
# ---------------------------------------------------------------------------

def test_no_pyside6_import_outside_allowlist():
    """Only modules in ``_PYSIDE6_ALLOWED_RELATIVE`` may import PySide6 (directly or transitively).

    Transitive taint via ``_QT_TAINTED_UPSTREAM`` is also detected.

    :spec: §4 (purity tiers)
    """
    violations: list[str] = []
    fritz_root = _fritz_root()
    for path in _all_fritz_py_files():
        # Relative path from fritz_root, e.g. "Types.py" or "widgets/WFritzPane.py"
        rel_to_fritz = os.path.relpath(path, fritz_root)
        if rel_to_fritz in _PYSIDE6_ALLOWED_RELATIVE:
            continue
        # Adapter-tier modules may import Qt-tainted upstream but not PySide6 directly.
        if rel_to_fritz in _ADAPTER_TAINT_ALLOWED_RELATIVE:
            # Still check for a direct PySide6 import, which adapters must not have.
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            except OSError:
                continue
            if _contains_pyside6(source, path):
                violations.append(
                    f"{os.path.relpath(path)}: adapter module has direct PySide6 import"
                )
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        except OSError:
            continue
        if _resolve_tainted_transitively(source, path):
            violations.append(f"{os.path.relpath(path)}: Qt-tainted (direct or via tainted upstream)")

    assert not violations, (
        "These Fritz files outside the allowlist are Qt-tainted:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: Types.py has no third-party imports
# ---------------------------------------------------------------------------

def test_types_module_has_no_third_party_imports():
    """``Fritz/Types.py`` must import only stdlib modules.

    :spec: §4 (dependency-free tier), N-FRITZ-1
    """
    types_path = os.path.join(_fritz_root(), "Types.py")
    assert os.path.isfile(types_path), "Fritz/Types.py does not exist"

    with open(types_path, encoding="utf-8") as fh:
        source = fh.read()

    _STDLIB_PREFIXES = (
        "__future__", "abc", "ast", "collections", "contextlib", "copy", "dataclasses",
        "enum", "functools", "glob", "io", "itertools", "json", "logging", "math",
        "operator", "os", "pathlib", "re", "shutil", "sys", "tempfile", "typing",
        "types", "weakref",
    )
    violations: list[str] = []
    for name in _direct_imports(source, types_path):
        if not any(name.startswith(p) for p in _STDLIB_PREFIXES):
            violations.append(name)

    assert not violations, (
        "Fritz/Types.py imports non-stdlib modules:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: Errors.py has no third-party imports (beyond CaissaError)
# ---------------------------------------------------------------------------

def test_errors_module_imports_only_caissa_error():
    """``Fritz/Errors.py`` must import only ``Code.Rpa.Errors`` (for ``CaissaError``) and stdlib.

    :spec: §4 (dependency-free tier)
    """
    errors_path = os.path.join(_fritz_root(), "Errors.py")
    assert os.path.isfile(errors_path), "Fritz/Errors.py does not exist"

    with open(errors_path, encoding="utf-8") as fh:
        source = fh.read()

    allowed = {"Code.Rpa.Errors", "__future__"}
    violations: list[str] = []
    for name in _direct_imports(source, errors_path):
        if not any(name.startswith(a) for a in allowed):
            violations.append(name)

    assert not violations, (
        "Fritz/Errors.py has unexpected imports:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: no upstream Code.* module imports from Code.Fritz
# ---------------------------------------------------------------------------

_UPSTREAM_FRITZ_IMPORT_ALLOWLIST = {
    # Explicitly modified in Phase 2 to wire the fixed-window mechanism.
    # Paths are relative to BIN_DIR (conftest sets cwd to bin/).
    os.path.normpath("Code/Main/MainWindow.py"),
    os.path.normpath("Code/Board/Board.py"),
    # Caissa-authored mode hook — imports PaneSpec, WFritzPane, PaneRegistry (Phase 3).
    os.path.normpath("Code/UIModes/actions/modern_fritz_ui.py"),
    # Phase 4: LCD clock widget wired into the player header; eval model wired into the analysis table.
    os.path.normpath("Code/UIModes/WFritzPlayerHeader.py"),
    os.path.normpath("Code/UIModes/WFritzAnalysisTable.py"),
    # Phase 7: Ribbon installed inside WBase.create_toolbar.
    os.path.normpath("Code/Main/WBase.py"),
}


def test_no_upstream_imports_from_fritz():
    """Upstream modules must not import ``Code.Fritz`` — the dependency is one-way.

    Files listed in ``_UPSTREAM_FRITZ_IMPORT_ALLOWLIST`` are explicitly edited
    in Phase 2 to wire the fixed-window mechanism and are exempt.

    :spec: §4 (strangler-fig scope limit), docs/standards/architecture.md §4
    """
    bin_code = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "bin", "Code")
    )
    fritz_root = _fritz_root()
    violations: list[str] = []

    for dirpath, dirs, filenames in os.walk(bin_code):
        # Skip the Fritz package itself and any stale worktrees
        if os.path.abspath(dirpath).startswith(os.path.abspath(fritz_root)):
            continue
        if "worktrees" in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path)
            if os.path.normpath(rel) in _UPSTREAM_FRITZ_IMPORT_ALLOWLIST:
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            except OSError:
                continue
            for name in _direct_imports(source, path):
                if (name or "").startswith("Code.Fritz"):
                    violations.append(f"{rel}: imports {name!r}")

    assert not violations, (
        "Upstream modules must not import Code.Fritz:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: feature_steps.md planned test names exist in the suite
# ---------------------------------------------------------------------------

def _planned_test_names() -> list[str]:
    """Parse fritz-polish feature_steps.md and return all test function names."""
    steps_path = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "docs", "features", "_archive", "fritz-polish", "feature_steps.md",
        )
    )
    # Fail loudly if the file is missing — a mistyped path must not silently pass.
    if not os.path.isfile(steps_path):
        raise FileNotFoundError(
            f"feature_steps.md not found at expected path: {steps_path}\n"
            "Check that docs/features/_archive/fritz-polish/feature_steps.md exists."
        )

    with open(steps_path, encoding="utf-8") as fh:
        content = fh.read()

    names: list[str] = []
    in_tdd = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("**TDD test cases"):
            in_tdd = True
            continue
        if in_tdd:
            if stripped.startswith("**") and not stripped.startswith("**TDD"):
                in_tdd = False
                continue
            if stripped.startswith("## "):
                in_tdd = False
                continue
            m = re.match(r"^-\s+`?(test_\w+)`?", stripped)
            if m:
                names.append(m.group(1))
    return names


def test_every_planned_test_name_exists_in_suite(pytestconfig):
    """Every test name in fritz-polish/feature_steps.md TDD sections must exist in the suite.

    Unlike the RPA version, this test **fails** (not skips) when the steps file is
    missing — a mistyped path cannot silently disable the check.

    :spec: NFR-5
    """
    planned = _planned_test_names()
    if not planned:
        pytest.skip("No planned test names found in fritz-polish/feature_steps.md")

    test_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    collected_names: set[str] = set()
    for dirpath, _, filenames in os.walk(test_root):
        if "worktrees" in dirpath:
            continue
        for fn in filenames:
            if fn.startswith("test_") and fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8") as fh:
                        source = fh.read()
                    tree = ast.parse(source, filename=path)
                except (SyntaxError, OSError):
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_"):
                            collected_names.add(node.name)

    missing = [n for n in planned if n not in collected_names]
    assert not missing, (
        f"{len(missing)} planned test(s) not yet in the suite:\n"
        + "\n".join(missing)
        + "\nAdd the test (or an xfail stub) or remove it from feature_steps.md."
    )
