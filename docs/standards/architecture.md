# Architecture Standards

## Purpose

This document fixes the layering rules for new Caissa code. It generalises the conventions
established by `bin/Code/Rpa/` and extended by `bin/Code/Fritz/`, so that each subsequent feature
has a single authoritative source rather than reading prior feature specs.

---

## 1. The Feature Package Convention

Every non-trivial Caissa feature lives in a **flat package under `bin/Code/`**, named for the
feature:

```
bin/Code/Rpa/       ← RPA layer
bin/Code/Fritz/     ← Fritz visual layer
bin/Code/<Next>/    ← next feature
```

Not a shared `bin/Code/Caissa/` umbrella. Not a per-feature `models/`, `gateways/`,
`services/` sub-package hierarchy. A flat package with a clear name. The `Rpa/` precedent has
`Vision/` as a sub-package because computer-vision work is genuinely a distinct concern that cannot
be imported on headless runners; that is the exception, not the pattern.

Within the package, every module belongs to exactly one purity tier (§2).

---

## 2. Purity Tiers

Each module in a feature package declares its purity tier. The tier is stated in the feature's
`feature_spec.md` §4 table and is enforced by `tests/unit/<feature>/test_completeness.py`.

| Tier | May import | Example |
|---|---|---|
| **Dependency-free** | stdlib only | `Types.py`, `Errors.py` |
| **Pure** | stdlib + dependency-free modules + verified Qt-free upstream types | `BoardFit.py`, `RibbonModel.py`, `QssRules.py` |
| **Adapter** | Upstream `Code.*` + pure modules + stdlib | `ThemeGateway.py`, `ModeGateway.py` |
| **Qt allowlist** | Qt + everything above | `WFritzPane.py`, `WRibbon.py` |

The one-way rule: **pure → adapter → widget, never the reverse**. Upstream never imports a
feature package.

---

## 3. The AST Purity Test

Every feature package MUST have `tests/unit/<feature>/test_completeness.py` asserting:

- `test_no_pyside6_import_outside_allowlist`: walks every `.py` with `ast.walk`, resolves imports
  **transitively** (because `Game`/`Move` → `Nags` → `QtGui` makes a module Qt-tainted without a
  direct `PySide6` import), and fails if any non-allowlisted module is tainted. The allowlist matches
  on **path relative to `bin/Code/<feature>/`**, not on basename — a basename match would exempt any
  file named `Driver.py` anywhere in the tree.
- `test_types_module_has_no_third_party_imports`: `ast`-based, stdlib-only allowlist.
- `test_no_upstream_imports_from_feature_package`: asserts no `bin/Code/` module outside the feature
  package imports it, so `git diff` against upstream stays additive.

The RPA version (`tests/unit/rpa/test_completeness.py:51-86`) walks direct imports only. Every new
feature must resolve transitively.

---

## 4. The Strangler-Fig Scope Limit

**New Caissa code is pure by default. Upstream Lucas Chess R6 is reached only through adapter modules.**

Upstream is not re-tiered. Re-layering the ~60 existing packages would break the Classical Invariant
on day one and has no test coverage to protect it. The adapter pattern is the strangler fig: build a
clean layer above the legacy, shrink the surface of direct contact over time, never rewrite from the
top down.

Upstream edits by a feature are confined to a short, enumerated list in the feature's
`feature_spec.md` §5.7. Any edit outside that list requires spec-level justification.

---

## 5. No ABCs, No `typing.Protocol`

Plain base classes raising `NotImplementedError`. Not `abc.ABC`, not `typing.Protocol`.

`docs/standards/coding-standards.md:72`: "`typing.Protocol` is built on `ABCMeta`, so this
prohibition covers both."

The precedent is `bin/Code/ManagerBase/Manager.py:61` — a plain class with ~35 subclasses.
The RPA precedent is `bin/Code/Rpa/Driver.py:29` — `class Driver:` with `QtDriver(Driver)` and
`FakeDriver(Driver)`.

---

## 6. The Characterisation-Test-First Refactor Procedure

When a feature moves behaviour from an upstream module into a pure one, the order is:

1. **Characterise.** Before moving anything, write unit tests that pin the *current* output of the
   code being moved. These tests are written against the old location and must pass before the move.
2. **Move, do not improve.** The extraction is behaviour-preserving. The same tests now import from
   the feature package and must still pass unchanged. Any behaviour change is a separate commit.
3. **Re-run the Classical Invariant.** `tests/test_classical_invariant.py` and
   `workflows/classical_invariant.py` must be green at every step.

Characterisation tests pin current behaviour including current bugs. Fixing those bugs is a separate,
later commit — never bundled into the refactor, because it makes the diff unreadable and the test
diff ambiguous.

---

## 7. The Dependency-Free Types Module

Every feature package MUST have a `Types.py` with:

- Frozen dataclasses only (`@dataclass(frozen=True, slots=True)`)
- Zero third-party imports (asserted by test)
- Reuses geometry types from `Rpa.Types` rather than declaring a second `Rect`

`Types.py` is the shared vocabulary across the whole package. If two modules need to exchange a
value, the type for that value belongs in `Types.py`.

---

## 8. The Error Hierarchy

Every feature package MUST have an `Errors.py` declaring a domain base exception:

```python
from Code.Rpa.Errors import CaissaError

class FritzError(CaissaError):
    ...
```

`CaissaError` lives in `Code.Rpa.Errors` per `docs/standards/error-handling.md` §1.1. Each feature
gets its own domain base, not a shared sibling.

Per-condition subclasses inherit the domain base. Names are `<Condition>Error`, sentence-case.

---

## 9. Executable References

The canonical implementations of all rules in this document:

| Rule | Where to look |
|---|---|
| Purity tiers, allowlist, tier test | `tests/unit/rpa/test_completeness.py` (direct-import version) |
| Transitive import resolution | `tests/unit/fritz/test_completeness.py` (extended version) |
| Dependency-free `Types.py` test | `tests/unit/rpa/test_foundations.py:141` |
| Plain base class pattern | `bin/Code/Rpa/Driver.py:29,131`, `bin/Code/Rpa/Fakes.py` |
| Characterisation table example | `tests/unit/fritz/test_board_fit.py` |
| Error hierarchy | `bin/Code/Rpa/Errors.py` |
