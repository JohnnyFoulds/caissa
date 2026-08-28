"""
tests/unit/rpa/test_foundations.py — Phase 1 foundation tests for the Caissa RPA layer.

Covers:
- CaissaError / RpaError exception hierarchy (Phase 1-A)
- Types.py dependency-freedom — Rect, ElementRef, Snapshot (Phase 1-A)
- Tooling invariants: marker discipline, ruff E722, LogSetup (Phase 1-B)

All future-phase test names appear as ``xfail(strict=True)`` stubs so Phase 9's
``test_every_planned_test_name_exists_in_suite`` can verify no planned test was quietly
dropped.  Each stub calls ``pytest.fail()`` so it correctly remains in the XFAIL state
until the owning phase lands and replaces it with a real implementation.

:spec: NFR-1, NFR-5, NFR-6, §11
:phase: 1
"""

import ast
import configparser
import logging
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.rpa

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]
_SUITE_MARKERS = {"unit", "ui", "rpa", "rpa_ui", "rpa_cv", "retro", "retro_emu", "retro_rom"}


def _get_rpa_errors():
    """Import and return the list of all 15 specific RPA exception classes."""
    from Code.Rpa.Errors import (
        AmbiguousMatchError,
        ConvergeError,
        DriverError,
        JournalError,
        ManifestError,
        PostconditionError,
        PreconditionError,
        RpaConfigError,
        RunAlreadyActiveError,
        RunNotFoundError,
        SelectorError,
        StateError,
        TargetNotFoundError,
        VisionUnavailableError,
        WorkflowNotFoundError,
    )
    return [
        DriverError, SelectorError, AmbiguousMatchError, TargetNotFoundError,
        PreconditionError, PostconditionError, ConvergeError, RunAlreadyActiveError,
        RunNotFoundError, WorkflowNotFoundError, VisionUnavailableError, ManifestError,
        JournalError, StateError, RpaConfigError,
    ]


# ---------------------------------------------------------------------------
# Phase 1-A: Exception hierarchy
# ---------------------------------------------------------------------------

def test_caissa_error_is_exception_subclass():
    """CaissaError must be a direct subclass of Exception.

    :spec: §11
    """
    from Code.Rpa.Errors import CaissaError
    assert issubclass(CaissaError, Exception)
    assert CaissaError.__bases__ == (Exception,)


def test_rpa_error_is_caissa_error_subclass():
    """RpaError must be a direct subclass of CaissaError (domain base).

    :spec: §11
    """
    from Code.Rpa.Errors import CaissaError, RpaError
    assert issubclass(RpaError, CaissaError)
    assert RpaError.__bases__ == (CaissaError,)


def test_all_rpa_error_types_are_rpa_error_subclasses():
    """All 15 specific RPA error types must be direct subclasses of RpaError.

    :spec: §11
    """
    from Code.Rpa.Errors import RpaError
    errors = _get_rpa_errors()
    assert len(errors) == 15, f"Expected 15 specific RPA errors, found {len(errors)}"
    for cls in errors:
        assert issubclass(cls, RpaError), f"{cls.__name__} must subclass RpaError"
        assert RpaError in cls.__bases__, (
            f"{cls.__name__} must be a DIRECT subclass of RpaError (base + one level rule)"
        )


# ---------------------------------------------------------------------------
# Phase 1-A: Types.py — dependency-free frozen dataclasses
# ---------------------------------------------------------------------------

def test_rect_is_frozen():
    """Rect must be a frozen dataclass (immutable).

    :spec: NFR-1, §4
    """
    from Code.Rpa.Types import Rect
    r = Rect(x=10, y=20, w=100, h=50)
    with pytest.raises((AttributeError, TypeError)):
        r.x = 99  # type: ignore[misc]


def test_element_ref_is_frozen():
    """ElementRef must be a frozen dataclass.

    :spec: NFR-1, §4
    """
    from Code.Rpa.Types import ElementRef, Rect
    ref = ElementRef(selector="obj:cls=QPushButton", rect=Rect(0, 0, 10, 10))
    with pytest.raises((AttributeError, TypeError)):
        ref.rect = Rect(1, 1, 5, 5)  # type: ignore[misc]


def test_snapshot_is_frozen():
    """Snapshot must be a frozen dataclass.

    :spec: NFR-1, §4
    """
    from Code.Rpa.Types import Snapshot
    snap = Snapshot(state_name="HOME", widget_tree=[], timestamp_ms=0.0)
    with pytest.raises((AttributeError, TypeError)):
        snap.state_name = "PLAYING"  # type: ignore[misc]


def test_types_module_has_no_third_party_imports():
    """Types.py must import nothing outside the Python standard library.

    Parsed via AST so the test never actually imports the third-party packages.

    :spec: NFR-1 (N-RPA-1)
    """
    types_path = _REPO_ROOT / "bin" / "Code" / "Rpa" / "Types.py"
    tree = ast.parse(types_path.read_text())

    third_party = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in _STDLIB_TOPS:
                    third_party.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top not in _STDLIB_TOPS and node.level == 0:
                    third_party.add(node.module)

    assert not third_party, (
        f"Types.py must have zero third-party imports. Found: {sorted(third_party)}. "
        f"N-RPA-1: every pure module imports Types.py, so a numpy import there "
        f"would drag numpy into a plain app start."
    )


def test_errors_module_has_no_third_party_imports():
    """Errors.py must import only stdlib and Code.Base (intra-project, D1).

    After D1 (Phase 2) Code.Rpa.Errors re-exports CaissaError from Code.Base.CaissaErrors.
    Code.Base is the only intra-project import allowed here; all other non-stdlib imports
    are treated as third-party violations.

    :spec: NFR-1, decisions.md D1
    """
    errors_path = _REPO_ROOT / "bin" / "Code" / "Rpa" / "Errors.py"
    tree = ast.parse(errors_path.read_text())

    third_party = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in _STDLIB_TOPS and top != "Code":
                    third_party.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top not in _STDLIB_TOPS and node.level == 0 and top != "Code":
                    third_party.add(node.module)

    assert not third_party, (
        f"Errors.py must have zero third-party imports. Found: {sorted(third_party)}."
    )


# Standard library top-level names (Python 3.12+, non-exhaustive but covers all our uses).
_STDLIB_TOPS = frozenset({
    "__future__", "_thread", "abc", "ast", "asyncio", "atexit", "base64", "binascii",
    "builtins", "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop",
    "collections", "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "csv", "ctypes", "curses", "dataclasses", "datetime",
    "dbm", "decimal", "difflib", "dis", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions", "ftplib",
    "functools", "gc", "getopt", "getpass", "gettext", "glob", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache", "locale",
    "logging", "lzma", "mailbox", "math", "mimetypes", "mmap", "modulefinder", "multiprocessing",
    "netrc", "nis", "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
    "reprlib", "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr",
    "socket", "socketserver", "spwd", "sqlite3", "sre_compile", "sre_constants",
    "sre_parse", "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "tomllib", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
})


# ---------------------------------------------------------------------------
# Phase 1-B: Marker discipline
# ---------------------------------------------------------------------------

def test_every_collected_test_has_exactly_one_suite_marker():
    """Every test file in tests/ must declare exactly one suite marker via pytestmark.

    Suite markers: unit, ui, rpa, rpa_ui, rpa_cv.

    Enforced by AST-parsing the module-level ``pytestmark`` assignment in each test file.
    A missing or duplicate marker causes ``make test`` (which filters by marker) to
    silently drop tests — the worst possible failure mode for a safety net.

    :spec: NFR-5
    """
    violations = []

    for test_file in sorted(_REPO_ROOT.glob("tests/**/test_*.py")):
        try:
            tree = ast.parse(test_file.read_text())
        except SyntaxError:
            violations.append(f"{test_file.relative_to(_REPO_ROOT)}: SyntaxError")
            continue

        suite_markers = _extract_suite_markers(tree)
        if len(suite_markers) != 1:
            violations.append(
                f"{test_file.relative_to(_REPO_ROOT)}: "
                f"expected 1 suite marker, found {sorted(suite_markers) or 'none'}"
            )

    assert not violations, (
        "The following test files are missing exactly one suite marker "
        "(unit/ui/rpa/rpa_ui/rpa_cv):\n" + "\n".join(f"  {v}" for v in violations)
    )


def _extract_suite_markers(tree: ast.Module) -> set:
    """Return the set of suite marker names applied via module-level pytestmark.

    Handles both single-mark (``pytestmark = pytest.mark.unit``) and list forms.
    """
    found = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == "pytestmark"):
                continue
            _collect_marks_from_node(node.value, found)
    return found & _SUITE_MARKERS


def _collect_marks_from_node(node: ast.expr, out: set) -> None:
    """Recursively collect marker names from a pytestmark assignment value."""
    if isinstance(node, ast.List):
        for elt in node.elts:
            _collect_marks_from_node(elt, out)
    elif isinstance(node, ast.Call):
        _collect_marks_from_attr(node.func, out)
    elif isinstance(node, ast.Attribute):
        _collect_marks_from_attr(node, out)


def _collect_marks_from_attr(node: ast.expr, out: set) -> None:
    """Extract the final attribute name from a pytest.mark.<name> expression."""
    if isinstance(node, ast.Attribute):
        out.add(node.attr)


# ---------------------------------------------------------------------------
# Phase 1-B: ruff config enforces E722
# ---------------------------------------------------------------------------

def test_ruff_config_enforces_e722(tmp_path):
    """ruff.toml must select E722 (bare except check) and not suppress it.

    Two-part test:
    1. Read ruff.toml and confirm E722 is selected and not in the ignore list.
    2. Run ruff with ``--select E722`` on a fixture to confirm it is detectable
       (guards against a ruff version that silently drops the rule).

    The ``--config ruff.toml`` form is verified by the separate concern that
    ``bin/pyproject.toml`` suppresses E722 and therefore ``make lint`` MUST use
    ``--config ruff.toml``. (D11)

    :spec: §5 (coding-standards)
    """
    ruff_toml = _REPO_ROOT / "ruff.toml"
    assert ruff_toml.exists(), "ruff.toml must exist at repo root (D11)"

    # Part 1: verify config selects E722 and does not ignore it.
    config = tomllib.loads(ruff_toml.read_text())
    select = config.get("lint", {}).get("select", [])
    ignore = config.get("lint", {}).get("ignore", [])
    assert any(s in ("E", "E7", "E72", "E722") for s in select), (
        f"ruff.toml [lint] select must include 'E' (or a more specific E722 superset). "
        f"Got: {select!r}"
    )
    assert "E722" not in ignore, (
        "ruff.toml must NOT suppress E722 — new Caissa code must not use bare except:"
    )

    # Part 2: confirm ruff actually reports E722 when invoked (behaviour check).
    ruff_bin = shutil.which("ruff")
    if ruff_bin is None:
        return  # config check passed; binary absent — skip behaviour half

    bad_py = tmp_path / "bad.py"
    bad_py.write_text("try:\n    pass\nexcept:\n    pass\n")
    result = subprocess.run(
        [ruff_bin, "check", "--select", "E722", "--no-cache", str(bad_py)],
        capture_output=True, text=True,
    )
    assert "E722" in result.stdout, (
        f"ruff --select E722 must report bare except:. stdout={result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Phase 1-B: LogSetup
# ---------------------------------------------------------------------------

def test_logsetup_configures_root_logger():
    """LogSetup.configure() must set the root logger level to the requested value.

    :spec: §3 (entry-point logging)
    """
    from Code.Main.LogSetup import configure, reset

    root = logging.getLogger()
    level_before = root.level
    reset()  # ensure _configured is False regardless of test order
    try:
        configure(level="WARNING")
        assert root.level == logging.WARNING, (
            f"configure(level='WARNING') must set root logger to WARNING; "
            f"got {root.level}"
        )
    finally:
        root.setLevel(level_before)
        reset()


def test_logsetup_reads_env_var(monkeypatch):
    """LogSetup.configure() reads CAISSA_LOG_LEVEL when level=None.

    :spec: §3 (entry-point logging)
    """
    from Code.Main.LogSetup import configure, reset

    root = logging.getLogger()
    level_before = root.level
    reset()  # ensure _configured is False
    monkeypatch.setenv("CAISSA_LOG_LEVEL", "DEBUG")
    try:
        configure()  # level=None — should read CAISSA_LOG_LEVEL=DEBUG
        assert root.level == logging.DEBUG, (
            f"configure() with CAISSA_LOG_LEVEL=DEBUG must set root to DEBUG; "
            f"got {root.level}"
        )
    finally:
        root.setLevel(level_before)
        reset()


# ---------------------------------------------------------------------------
# Phase 1-B: RPA timeout vs pytest timeout
# ---------------------------------------------------------------------------

def test_rpa_timeout_below_pytest_timeout():
    """RPA run deadline (90 000 ms) must be at least 30 s below pytest timeout (120 s).

    D12: this headroom ensures the runner always wins the race against pytest's
    process kill, so compensations run and the journal is persisted — the evidence
    for exactly the failures you most want to diagnose.

    The constant 90_000 will live in Runner.py (Phase 5). It is hardcoded here so
    Phase 9 can replace this line with an import and confirm the constant was not
    inadvertently raised.

    :spec: NFR-10 (N-RPA-10), D12
    """
    ini = configparser.ConfigParser()
    ini.read(_REPO_ROOT / "pytest.ini")
    pytest_timeout_s = int(ini["pytest"]["timeout"].strip())

    RUN_TIMEOUT_MS = 90_000  # Phase 5: replace with import from Code.Rpa.Runner
    headroom_ms = (pytest_timeout_s * 1000) - RUN_TIMEOUT_MS
    assert headroom_ms >= 30_000, (
        f"pytest timeout ({pytest_timeout_s}s × 1000) - RUN_TIMEOUT_MS ({RUN_TIMEOUT_MS}ms) "
        f"= {headroom_ms}ms < 30 000ms. D12."
    )


# ===========================================================================
# xfail stubs — Phase 2: Driver seam
# Each stub calls pytest.fail() so it remains xfail (expected failure) until
# the owning phase replaces it with a real implementation.
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_driver_base_raises_not_implemented_for_all_methods():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_fake_driver_overrides_all_driver_methods():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_qt_driver_overrides_all_driver_methods():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_fake_clock_advance_updates_now():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_fake_clock_run_due_fires_scheduled_callbacks():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_fake_driver_snapshot_returns_world_state():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_fake_driver_defer_schedules_via_fake_clock():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam); needs QtDriver + shiboken6")
def test_actuating_on_deleted_widget_raises_target_not_found():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam)")
def test_rpa_disabled_by_env_serves_no_rpa_verbs():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam); Runner.py must exist")
def test_importing_runner_does_not_import_cv2():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 (refactor/rpa-driver-seam); Code.Rpa package must be complete")
def test_no_pyside6_import_outside_allowlist():
    pytest.fail("not yet implemented — will be unblocked in Phase 2")


# ===========================================================================
# xfail stubs — Phase 3: Targets + object resolver
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_selector_compact_string_roundtrip():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_selector_json_roundtrip():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_selector_requires_discriminating_field():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_resolve_object_exact_name():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_resolve_object_exact_text():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_resolve_ambiguous_raises():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_resolve_anchor_right_of():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_object_confidence_exact_name_is_one():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_object_confidence_class_only_is_0_60():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 (feat/rpa-targets)")
def test_fallback_tier_win_emits_warning():
    pytest.fail("not yet implemented — will be unblocked in Phase 3")


# ===========================================================================
# xfail stubs — Phase 4: State model
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_recognise_dialog_config_priority():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_recognise_home():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_recognise_unknown_fallback():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_plan_home_to_playing():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_plan_avoids_force_cancel_when_cheaper_path_exists():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_every_state_can_reach_home():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_every_force_cancel_edge_declares_min_settle_at_least_600():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 (feat/rpa-state-model)")
def test_plan_rejects_unreachable_state():
    pytest.fail("not yet implemented — will be unblocked in Phase 4")


# ===========================================================================
# xfail stubs — Phase 5: Runner + journal + activities
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_sub_state_enum_has_exactly_14_members():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_state_machine_doc_lists_every_substate():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_happy_path_completes_to_succeeded():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_precondition_false_triggers_convergence():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_convergence_exhausts_budget_transitions_to_unwind():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_postcondition_retried_within_deadline():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_postcondition_timeout_triggers_decide_recovery():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_decide_recovery_retryable_backs_off():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_decide_recovery_compensable_compensates():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_compensate_success_retries_step():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_compensate_fail_unwinds():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_unwind_calls_compensate_in_reverse():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_frame_pop_resumes_parent():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_retry_scope_re_enters_on_failure():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_no_sleep_call_anywhere():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_one_pump_one_transition_max():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_run_timeout_triggers_cancelling():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_run_timeout_ms_less_than_pytest_timeout():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_second_concurrent_run_is_rejected():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_rpa_cancel_sets_cancelling_state():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_settled_ms_not_pumps():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_journal_written_on_terminal_transition():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_journal_env_block_records_dpr_theme_and_cv_availability():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_run_id_scheme_is_timestamp_plus_hex():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_backoff_reproducible_from_run_id():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_pump_reentrancy_guard_prevents_nested_pump():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 (feat/rpa-runner)")
def test_cancelling_transitions_to_cancelled_via_unwind():
    pytest.fail("not yet implemented — will be unblocked in Phase 5")


# ===========================================================================
# xfail stubs — Phase 6: Service + rpa_* verbs (rpa_ui suite)
# These live in tests/ui/test_rpa_service.py when Phase 6 lands — stubs here
# ensure Phase 9 can verify they were not dropped.
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_every_rpa_verb_returns_under_200ms_while_run_active():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_run_progresses_while_a_modal_dialog_is_open():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_run_returns_run_id():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_status_returns_pending_before_pump():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_cancel_accepted_during_run():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_find_returns_element_list():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_state_returns_current_state():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_capabilities_returns_cv_flags():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); rpa_ui suite")
def test_rpa_disabled_env_blocks_all_rpa_verbs_but_not_originals():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service); quickstart must be runnable")
def test_quickstart_executed_verbatim():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


# ===========================================================================
# xfail stubs — Phase 7: Vision (rpa_cv suite)
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_capture_rgb_channel_order():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_capture_handles_byteperline_padding():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_screenshot_logical_resizes_by_dpr():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_template_match_finds_known_template():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_template_multi_scale_warns_on_nonunit_scale():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_ocr_finds_multiword_phrase():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_ocr_grouped_by_block_par_line():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_manifest_hashes_match_files():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_manifest_missing_entry_raises():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); rpa_cv suite")
def test_availability_no_cv_returns_reason_with_install_command():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 (feat/rpa-vision); Code.Rpa package must be complete")
def test_no_toplevel_numpy_or_cv2_import_outside_vision():
    pytest.fail("not yet implemented — will be unblocked in Phase 7")


# ===========================================================================
# xfail stubs — Phase 8: Workflows + registry (rpa_ui suite)
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows)")
def test_registry_register_and_get():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows)")
def test_registry_unknown_raises_workflow_not_found_error():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows); rpa_ui suite")
def test_smoke_home_succeeds():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows); rpa_ui suite")
def test_classical_invariant_workflow_passes_on_classical_mode():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows); rpa_ui suite")
def test_config_roundtrip_succeeds():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


@pytest.mark.xfail(strict=True, reason="Requires Phase 8 (feat/rpa-workflows)")
def test_every_workflow_template_ref_is_in_manifest():
    pytest.fail("not yet implemented — will be unblocked in Phase 8")


# ===========================================================================
# xfail stubs — Phase 9: Production readiness (tests/unit/rpa/test_completeness.py)
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Requires Phase 9 (chore/rpa-production-readiness)")
def test_every_planned_test_name_exists_in_suite():
    pytest.fail("not yet implemented — will be unblocked in Phase 9")


@pytest.mark.xfail(strict=True, reason="Requires Phase 9 (chore/rpa-production-readiness)")
def test_every_public_callable_in_rpa_has_docstring():
    pytest.fail("not yet implemented — will be unblocked in Phase 9")


@pytest.mark.xfail(strict=True, reason="Requires Phase 9 (chore/rpa-production-readiness)")
def test_make_docs_builds_with_zero_warnings():
    pytest.fail("not yet implemented — will be unblocked in Phase 9")


@pytest.mark.xfail(strict=True, reason="Requires Phase 9 (chore/rpa-production-readiness)")
def test_cv2_absent_from_sys_modules_after_plain_start():
    pytest.fail("not yet implemented — will be unblocked in Phase 9")
