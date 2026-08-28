"""
tests/unit/retro/test_foundations.py — Phase 2 foundation tests for the Caissa Retro Engine.

Covers:
- CaissaError promotion to Code.Base.CaissaErrors (D1)
- RetroError exception hierarchy
- Types.py dependency-freedom (N-RETRO-1)
- unicorn confined to Cpus/* (N-RETRO-2)
- PySide6 absent from Code.Retro (N-RETRO-5)
- Types.py import purity — no third-party imports at process level (N-RETRO-3)

All future-phase test names appear as ``xfail(strict=True)`` stubs so a completeness
gate can verify no planned test was quietly dropped.

:spec: N-RETRO-1 through N-RETRO-5, decisions.md D1
:phase: 2
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
_BASE_PKG   = _REPO_ROOT / "bin" / "Code" / "Base"


def _retro_py_files():
    """Yield absolute paths of all .py files in Code/Retro/."""
    yield from _RETRO_PKG.rglob("*.py")


def _ast_imports(path: Path):
    """Return set of top-level module names imported by *path*."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


_STDLIB = frozenset(sys.stdlib_module_names)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D1: CaissaError lives in Code.Base.CaissaErrors
# ---------------------------------------------------------------------------

def test_caissa_error_in_base():
    """CaissaError must be importable from Code.Base.CaissaErrors (D1).

    :spec: decisions.md D1
    """
    from Code.Base.CaissaErrors import CaissaError
    assert issubclass(CaissaError, Exception)
    assert CaissaError.__bases__ == (Exception,)


def test_rpa_errors_reexports_caissa_error():
    """Code.Rpa.Errors must still export CaissaError (backward compat, D1).

    :spec: decisions.md D1
    """
    from Code.Base.CaissaErrors import CaissaError as BaseCaissaError
    from Code.Rpa.Errors import CaissaError as RpaCaissaError
    assert RpaCaissaError is BaseCaissaError, "Rpa re-export must be the same object as Base"


# ---------------------------------------------------------------------------
# RetroError hierarchy
# ---------------------------------------------------------------------------

def test_retro_error_is_caissa_error_subclass():
    """RetroError must be a direct subclass of CaissaError.

    :spec: feature_spec.md §11
    """
    from Code.Base.CaissaErrors import CaissaError
    from Code.Retro.Errors import RetroError
    assert issubclass(RetroError, CaissaError)
    assert CaissaError in RetroError.__bases__


def test_all_retro_leaf_errors_are_retro_error_subclasses():
    """Every leaf Retro error must be a direct subclass of RetroError.

    :spec: feature_spec.md §11
    """
    from Code.Retro.Errors import (
        BridgeError,
        CpuError,
        EmulatorUnavailableError,
        HashMismatchError,
        ManifestError,
        OracleError,
        PackedBinaryError,
        RetroError,
        RomError,
        RomNotFoundError,
        ThinkError,
        UciError,
        UnsupportedRomError,
    )
    leaves = [
        RomError, RomNotFoundError, ManifestError, HashMismatchError, UnsupportedRomError,
        PackedBinaryError, CpuError, EmulatorUnavailableError, BridgeError,
        ThinkError, OracleError, UciError,
    ]
    for cls in leaves:
        assert issubclass(cls, RetroError), f"{cls.__name__} must subclass RetroError"
        assert RetroError in cls.__bases__, f"{cls.__name__} must directly subclass RetroError"


def test_hash_mismatch_error_stores_fields():
    """HashMismatchError must store .path and .digest attributes.

    :spec: feature_spec.md §11
    """
    from Code.Retro.Errors import HashMismatchError
    err = HashMismatchError("/some/rom", "a" * 64)
    assert err.path == "/some/rom"
    assert err.digest == "a" * 64
    assert "a" * 16 in str(err)


def test_emulator_unavailable_default_message():
    """EmulatorUnavailableError default message must mention requirements-retro.txt.

    :spec: feature_spec.md §11
    """
    from Code.Retro.Errors import EmulatorUnavailableError
    err = EmulatorUnavailableError()
    assert "requirements-retro.txt" in err.reason


# ---------------------------------------------------------------------------
# N-RETRO-1: Types.py has zero third-party imports
# ---------------------------------------------------------------------------

def test_types_module_has_no_third_party_imports():
    """Types.py must import only from stdlib (N-RETRO-1).

    :spec: N-RETRO-1
    """
    types_path = _RETRO_PKG / "Types.py"
    assert types_path.exists(), "bin/Code/Retro/Types.py not found"
    imports = _ast_imports(types_path)
    third_party = imports - _STDLIB - {"__future__"}
    # Allow intra-package references (Code.*)
    third_party = {m for m in third_party if not m.startswith("Code")}
    assert not third_party, f"Types.py has third-party imports: {third_party}"


def test_errors_module_only_imports_base_and_stdlib():
    """Errors.py must import only Code.Base and stdlib (N-RETRO-1 variant).

    :spec: N-RETRO-1
    """
    errors_path = _RETRO_PKG / "Errors.py"
    imports = _ast_imports(errors_path)
    allowed = _STDLIB | {"__future__", "Code"}
    disallowed = imports - allowed
    assert not disallowed, f"Errors.py has unexpected imports: {disallowed}"


# ---------------------------------------------------------------------------
# N-RETRO-2: unicorn confined to Cpus/*
# ---------------------------------------------------------------------------

def test_unicorn_not_imported_outside_cpus():
    """unicorn must not appear in any Retro module outside Cpus/.

    :spec: N-RETRO-2
    """
    violations = []
    for path in _retro_py_files():
        if "Cpus" in path.parts:
            continue
        imports = _ast_imports(path)
        if "unicorn" in imports:
            violations.append(str(path.relative_to(_REPO_ROOT)))
    assert not violations, f"unicorn imported outside Cpus/: {violations}"


# ---------------------------------------------------------------------------
# N-RETRO-5: PySide6 absent from Code.Retro
# ---------------------------------------------------------------------------

def test_no_pyside6_in_retro_package():
    """No module in Code.Retro may import PySide6 (N-RETRO-5).

    :spec: N-RETRO-5
    """
    violations = []
    for path in _retro_py_files():
        imports = _ast_imports(path)
        if "PySide6" in imports:
            violations.append(str(path.relative_to(_REPO_ROOT)))
    assert not violations, f"PySide6 imported in Retro package: {violations}"


# ---------------------------------------------------------------------------
# N-RETRO-3: importing Code.Retro does not pull unicorn into sys.modules
# ---------------------------------------------------------------------------

def test_importing_retro_does_not_pull_in_unicorn():
    """Importing Code.Retro must not cause unicorn to appear in sys.modules (N-RETRO-3).

    :spec: N-RETRO-3
    """
    bin_path = str(_REPO_ROOT / "bin")
    script = (
        "import sys; "
        f"sys.path.insert(0, {bin_path!r}); "
        "import Code.Retro; "
        "assert 'unicorn' not in sys.modules, 'unicorn leaked into sys.modules'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, (
        f"unicorn leaked into sys.modules on Code.Retro import:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Types.py — structural checks
# ---------------------------------------------------------------------------

def test_move_spec_is_frozen():
    """MoveSpec must be a frozen dataclass.

    :spec: N-RETRO-1
    """
    from Code.Retro.Types import MoveSpec
    m = MoveSpec(from_sq=0x10, to_sq=0x30, flags=0, piece=1, legal=1)
    with pytest.raises((AttributeError, TypeError)):
        m.from_sq = 0  # type: ignore[misc]


def test_move_spec_to_uci_e2e4():
    """MoveSpec.to_uci() must return the correct UCI string for e2→e4.

    0x88 encoding: e2 = rank 1 (0-indexed) << 4 | file 4 = 0x14; e4 = 0x34.

    :spec: feature_spec.md §4
    """
    from Code.Retro.Types import MoveSpec
    m = MoveSpec(from_sq=0x14, to_sq=0x34, flags=0, piece=1, legal=1)
    assert m.to_uci() == "e2e4"


def test_move_spec_to_uci_invalid_square_raises():
    """MoveSpec.to_uci() must raise ValueError for an off-board 0x88 square.

    :spec: feature_spec.md §4
    """
    from Code.Retro.Types import MoveSpec
    m = MoveSpec(from_sq=0x08, to_sq=0x30, flags=0, piece=1, legal=1)  # 0x08 & 0x88 != 0
    with pytest.raises(ValueError):
        m.to_uci()


def test_rom_id_rejects_bad_digest():
    """RomId must raise ValueError for a malformed sha256 digest.

    :spec: feature_spec.md §4
    """
    from Code.Retro.Types import Platform, RomId
    with pytest.raises(ValueError):
        RomId(sha256="tooshort", platform=Platform.AMIGA_68K, label="test")


def test_think_result_has_move():
    """ThinkResult.has_move must reflect whether move is None.

    :spec: feature_spec.md §4
    """
    from Code.Retro.Types import Level, MoveSpec, ThinkResult
    m = MoveSpec(from_sq=0x14, to_sq=0x34, flags=0, piece=1, legal=1)
    tr = ThinkResult(move=m, level=Level.NOVICE, instructions=1000)
    assert tr.has_move is True
    empty = ThinkResult(move=None, level=Level.NOVICE, instructions=0)
    assert empty.has_move is False


