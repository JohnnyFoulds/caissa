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
    "Driver.py",          # QtDriver (Rpa root)
    "Vision/Capture.py",  # headless-Vision exception
    "Service.py",         # RpaService QTimer
}


def _rel_to_rpa(path: str) -> str:
    """Return *path* relative to the Rpa package root with forward slashes."""
    return os.path.relpath(path, _rpa_root()).replace(os.sep, "/")


def _direct_pyside6_import(path: str) -> bool:
    """Return True if *path* imports PySide6 anywhere (direct taint)."""
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any("PySide6" in a.name for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if "PySide6" in (node.module or ""):
                return True
    return False


def _top_level_rpa_deps(path: str) -> list[str]:
    """Return Code.Rpa-internal deps imported at module top level by *path*.

    Only top-level ``from Code.Rpa...`` / ``import Code.Rpa...`` statements count:
    a function-scoped ``from PySide6 import ...`` (as in Driver.py) does not taint
    importers at module-load time, so function-level Rpa imports are ignored here.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return []
    deps: list[str] = []
    for node in tree.body:
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods = [node.module]
        for mod in mods:
            if mod == "Code.Rpa" or mod.startswith("Code.Rpa."):
                deps.append(_resolve_rpa_import(path, mod, node))
    return [d for d in deps if d]


def _resolve_rpa_import(from_path: str, module: str, node: ast.AST) -> str | None:
    """Resolve ``Code.Rpa.*`` *module* to an absolute file path, or None."""
    parts = module.split(".")  # ["Code", "Rpa", ...]
    assert parts[:2] == ["Code", "Rpa"]
    rel_parts = parts[2:]
    base = _rpa_root()
    if not rel_parts:
        candidate = os.path.join(base, "__init__.py")
        return candidate if os.path.isfile(candidate) else None
    candidate = os.path.join(base, *rel_parts)
    if os.path.isfile(candidate + ".py"):
        return candidate + ".py"
    if os.path.isfile(os.path.join(candidate, "__init__.py")):
        names = getattr(node, "names", [])
        if len(names) == 1:
            leaf = os.path.join(candidate, names[0].name + ".py")
            if os.path.isfile(leaf):
                return leaf
        return os.path.join(candidate, "__init__.py")
    return None


def test_no_pyside6_import_outside_allowlist():
    """Only Driver.py, Vision/Capture.py, and Service.py may import PySide6."""
    violations = []
    for path in _all_rpa_py_files():
        if _rel_to_rpa(path) in _PYSIDE6_ALLOWED:
            continue
        if _direct_pyside6_import(path):
            violations.append(f"{os.path.relpath(path)}: imports PySide6")

    assert not violations, (
        "These files outside the allowlist import PySide6:\n"
        + "\n".join(violations)
    )


def _load_time_pyside6_import(path: str) -> bool:
    """Return True if *path* imports PySide6 at module top level (runs on import).

    Function-scoped ``from PySide6 import ...`` (as in Driver.py) does not taint
    importers at load time, so only module-level statements count here. Blocks
    guarded by ``TYPE_CHECKING`` are excluded — they never execute at runtime.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return False
    for node in tree.body:
        if isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "TYPE_CHECKING" in test:
                continue
        if isinstance(node, ast.Import):
            if any("PySide6" in a.name for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if "PySide6" in (node.module or ""):
                return True
    return False


def test_no_transitive_pyside6_outside_allowlist():
    """No non-allowlisted module may reach PySide6 via top-level Code.Rpa imports."""
    files = list(_all_rpa_py_files())
    direct_tainted = {p for p in files if _load_time_pyside6_import(p)}
    violations = []
    for path in files:
        if _rel_to_rpa(path) in _PYSIDE6_ALLOWED:
            continue
        seen: set[str] = set()
        stack = _top_level_rpa_deps(path)
        while stack:
            dep = stack.pop()
            if dep in seen or dep not in direct_tainted and dep not in files:
                seen.add(dep)
                continue
            if dep in seen:
                continue
            seen.add(dep)
            if dep in direct_tainted:
                violations.append(
                    f"{os.path.relpath(path)} transitively imports PySide6 via "
                    f"{os.path.relpath(dep)}"
                )
                break
            stack.extend(_top_level_rpa_deps(dep))

    assert not violations, (
        "These files reach PySide6 transitively:\n" + "\n".join(violations)
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

def _parse_test_names_from_steps(path: str) -> list[str]:
    """Parse one feature_steps.md and return all test names in TDD test cases sections."""
    names = []
    in_tdd = False
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
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


def _planned_test_names() -> list[str]:
    """Return all planned test names from all known feature_steps.md files.

    Reads the archived rpa-layer steps (allowed to be missing — it is under _archive/)
    plus any active feature steps files. Uses pytest.fail (not skip) when an active
    steps file exists but contains zero planned test names, so the gate stays binding.
    """
    repo_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    # Paths in priority order: (path, is_archived)
    candidates = [
        (os.path.join(repo_root, "docs", "features", "rpa-layer", "feature_steps.md"), True),
        (os.path.join(repo_root, "docs", "features", "rpa-design-vision", "feature_steps.md"), False),
    ]

    all_names: list[str] = []
    for path, is_archived in candidates:
        if not os.path.isfile(path):
            if not is_archived:
                pytest.fail(
                    f"Active feature_steps.md missing at {path}.\n"
                    "Restore the file or remove it from candidates — "
                    "a missing active steps file must not silently disable the gate."
                )
            continue
        names = _parse_test_names_from_steps(path)
        if not names and not is_archived:
            pytest.fail(
                f"Active feature_steps.md at {path} has no TDD test cases sections.\n"
                "Add at least one '**TDD test cases' section with test names, or "
                "the planned-test-name gate cannot enforce anything."
            )
        all_names.extend(names)

    return all_names


def test_every_planned_test_name_exists_in_suite(pytestconfig):
    """Every test name listed in feature_steps.md TDD sections must exist in the suite."""
    planned = _planned_test_names()
    if not planned:
        pytest.fail(
            "No planned test names found in any feature_steps.md — "
            "the gate would pass vacuously. Add TDD test cases or fix the parser."
        )

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
