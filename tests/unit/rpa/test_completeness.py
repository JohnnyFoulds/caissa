"""
tests/unit/rpa/test_completeness.py — Phase 9 production-readiness completeness checks.

These tests enforce structural invariants across the entire RPA package:

- Every planned test name from ``feature_steps.md`` exists in the collected suite.
- Every public callable in ``Code.Rpa`` has an RST docstring.
- ``Code.Rpa`` imports do not pull cv2 or numpy into ``sys.modules``.
- ``PySide6`` is only imported by the three permitted modules.
- The runner deadline sits safely below the pytest timeout.

:spec: NFR-5, NFR-6, §14 (feature_spec.md)
"""

from __future__ import annotations

import ast
import os
import re
import sys

import pytest

pytestmark = pytest.mark.rpa


# ---------------------------------------------------------------------------
# Helper — locate the Rpa package root
# ---------------------------------------------------------------------------

def _rpa_root() -> str:
    root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "bin", "Code", "Rpa")
    )
    return root


def _all_rpa_py_files(include_vision: bool = True):
    """Yield absolute paths of all .py files in Code/Rpa/."""
    rpa_root = _rpa_root()
    for dirpath, _, filenames in os.walk(rpa_root):
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


# ---------------------------------------------------------------------------
# Test: PySide6 import allowlist
# ---------------------------------------------------------------------------

_PYSIDE6_ALLOWED = {
    "Driver.py",          # QtDriver
    "Capture.py",         # Vision/Capture.py
    "Service.py",         # RpaService QTimer
}


def test_no_pyside6_import_outside_allowlist():
    """Only Driver.py, Vision/Capture.py, and Service.py may import PySide6."""
    violations = []
    for path in _all_rpa_py_files():
        filename = os.path.basename(path)
        if filename in _PYSIDE6_ALLOWED:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=path)
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                names = [node.module] if node.module else []
            for name in names:
                if "PySide6" in (name or ""):
                    rel = os.path.relpath(path)
                    violations.append(f"{rel}: imports PySide6")

    assert not violations, (
        "These files outside the allowlist import PySide6:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: public callables have docstrings
# ---------------------------------------------------------------------------

def test_every_public_callable_in_rpa_has_docstring():
    """Every public function, method, and class in Code.Rpa must have a docstring."""
    missing = []
    for path in _all_rpa_py_files():
        if os.path.basename(path) == "__init__.py":
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=path)
        except (SyntaxError, OSError):
            continue

        rel = os.path.relpath(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue  # skip private methods; check public and dunder
            docstring = ast.get_docstring(node)
            if not docstring:
                missing.append(f"{rel}:{node.lineno}: {node.name}()")

    assert not missing, (
        f"{len(missing)} public callable(s) missing docstrings:\n"
        + "\n".join(missing[:30])
        + ("\n  ... and more" if len(missing) > 30 else "")
    )


# ---------------------------------------------------------------------------
# Test: cv2 absent from sys.modules after plain Rpa import
# ---------------------------------------------------------------------------

def test_cv2_absent_from_sys_modules_after_plain_start():
    """Importing Code.Rpa (non-Vision modules) must not pull cv2 into sys.modules."""
    # Import key non-Vision modules
    import importlib
    for mod in [
        "Code.Rpa.Errors",
        "Code.Rpa.Types",
        "Code.Rpa.Targets",
        "Code.Rpa.Activities",
        "Code.Rpa.AppState",
        "Code.Rpa.Journal",
        "Code.Rpa.Runner",
        "Code.Rpa.Workflows.Registry",
    ]:
        importlib.import_module(mod)

    assert "cv2" not in sys.modules, (
        "cv2 was imported as a side-effect of loading Code.Rpa non-Vision modules"
    )
    assert "numpy" not in sys.modules, (
        "numpy was imported as a side-effect of loading Code.Rpa non-Vision modules"
    )


# ---------------------------------------------------------------------------
# Test: run timeout below pytest timeout
# ---------------------------------------------------------------------------

def test_rpa_timeout_below_pytest_timeout():
    """RUN_TIMEOUT_MS must be at least 10 s below the pytest timeout to allow journal writes."""
    from Code.Rpa.Runner import RUN_TIMEOUT_MS

    # pytest.ini timeout is 120 s
    pytest_timeout_ms = 120_000
    headroom_ms = 10_000

    assert RUN_TIMEOUT_MS < pytest_timeout_ms - headroom_ms, (
        f"RUN_TIMEOUT_MS={RUN_TIMEOUT_MS} must be < pytest_timeout ({pytest_timeout_ms}) "
        f"- headroom ({headroom_ms}) = {pytest_timeout_ms - headroom_ms}. "
        "Increase the gap so the runner can finish unwind + journal before pytest kills the process."
    )


# ---------------------------------------------------------------------------
# Test: every planned test name exists in the suite
# ---------------------------------------------------------------------------

def _planned_test_names() -> list[str]:
    """Parse feature_steps.md and return all test names listed in TDD test cases."""
    steps_path = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "docs", "features", "rpa-layer", "feature_steps.md"
        )
    )
    if not os.path.isfile(steps_path):
        return []

    with open(steps_path, encoding="utf-8") as fh:
        content = fh.read()

    names = []
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
    """Every test name listed in feature_steps.md TDD sections must exist in the suite."""
    planned = _planned_test_names()
    if not planned:
        pytest.skip("No planned test names found in feature_steps.md")

    # Collect all test node IDs in the test directory
    test_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    collected_names: set[str] = set()
    for dirpath, _, filenames in os.walk(test_root):
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
        f"{len(missing)} planned test(s) not found in the suite:\n"
        + "\n".join(missing)
        + "\nAdd the test or remove it from feature_steps.md."
    )
