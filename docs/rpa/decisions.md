# Architecture Decision Log — RPA Layer

Each decision records what was decided, why, and when. Decisions are appended; never deleted.
Open questions from `initial_idea.md` are noted as OPEN until resolved.

---

## D1 — `FakeDriver` placement

**Resolved:** 2026-08-28  
**Decision:** `bin/Code/Rpa/Fakes.py` (shipped, not test-only)  
**Rationale:** Enables `rpa_run {"dry_run": true}` — validating a workflow's selectors and
state graph with no GUI — which is a first-class dev-tooling deliverable. Co-locates the
contract with its reference implementation. A shipped test double is honest about what it is.  
**Alternative considered:** `tests/` only — rejected because `dry_run` is a production verb.

---

## D2 — Where `CaissaError` lives

**Resolved:** 2026-08-28  
**Decision:** `bin/Code/Rpa/Errors.py`  
**Rationale:** `bin/Code/Base/` is pure upstream Lucas Chess R6 (`Constantes`, `Game`, `Move`,
`Position`). Placing a Caissa file there weakens the Classical-Invariant boundary.
`docs/standards/error-handling.md` §1.1 mandates `CaissaError` but never located it — this
feature sets the precedent. The standard is amended to record this location.  
**Alternative considered:** `bin/Code/Base/CaissaErrors.py` — rejected (boundary violation).

---

## D3 — Dependency file layout

**Resolved:** 2026-08-28  
**Decision:** New `requirements-rpa.txt` + `requirements-dev.txt`; `requirements.txt` untouched  
**Rationale:** Forcing every end user to install ~90 MB of OpenCV for a debug/test facility is
the wrong trade. Expressed as optional extras. `requirements.txt` is for the chess app; the
RPA dependencies are opt-in.

---

## D4 — `opencv-python` vs headless

**Resolved:** 2026-08-28  
**Decision:** `opencv-python-headless`  
**Rationale:** The full wheel bundles its own Qt plugins. Loading it alongside PySide6 on macOS
can produce a duplicate-Qt/`libqcocoa` clash that presents as a hard crash, not a warning.
Headless ships no Qt at all.

---

## D5 — i18n-sensitive selectors

**Status:** OPEN (deferred to v2)  
**Decision:** v1 workflows prefer `object_name`/`cls`/`role` over `text`; workflows that use
`text`-based selectors declare a required translator in their precondition.  
**Deferred because:** `_dialog_button` already hardcodes English+Spanish keywords. A
translation-aware `Selector.text_key` resolved through `_()` is deferred to v2 and recorded
as an open question in `initial_idea.md`.

---

## D6 — App-wide logging config

**Resolved:** 2026-08-28  
**Decision:** `LogSetup.configure()` in `bin/Code/Main/LogSetup.py`, called once from the entry
point, delivered in Phase 1 as its own commit.  
**Rationale:** No logging is configured anywhere in the app today. Without it, RPA logs are
silent — a prerequisite, not RPA scope, so it gets its own reviewable commit.

---

## D7 — CI (GitHub Actions)

**Status:** OPEN (deferred to Phase 9)  
**Decision:** Proposed at Phase 9; not added without explicit approval.  
**Rationale:** There is no CI today, and adding a workflow that runs on push to
`JohnnyFoulds/caissa` is outward-facing. It will be presented as a Phase 9 recommendation.

---

## D8 — Python floor

**Resolved:** 2026-08-28  
**Decision:** Leave `requires-python = ">=3.12"` alone; document the discrepancy.  
**Rationale:** `bin/pyproject.toml` says `>=3.12` and `[tool.uv] python = "3.12"`, while
`[tool.black] target-version` and the standards say py313. Narrowing a declared support floor
is an outward-facing change. The new Caissa-scoped ruff config sets `target-version = "py313"`
for new code only; the mismatch is noted here.

---

## D9 — API-doc tooling

**Resolved:** 2026-08-28  
**Decision:** Sphinx autodoc, added to `requirements-dev.txt`; `make docs` renders `docs/rpa/api/`  
**Rationale:** `docs/standards/docstring-standards.md` mandates RST/Sphinx field lists for
every callable — the docstrings *are* the API doc. Hand-maintaining a parallel reference
guarantees drift. Sphinx is dev-only. `docs/rpa/api/` is gitignored — generated HTML in
version control creates unreviewable diffs.

---

## D10 — Where `Screenshot` and `Match` live

**Resolved:** 2026-08-28  
**Decision:** `Screenshot` → `Vision/Capture.py`; `Match` → `Vision/Template.py`; `Types.py`
contains only `Rect`, `ElementRef`, `Snapshot`.  
**Rationale:** `Screenshot.rgb` is an `ndarray` and `.logical()` calls `cv2.resize`, so
putting it in `Types.py` would either force a top-level numpy import (violating N-RPA-1) or
leave a dataclass whose only method can't run. `Types.py` must be genuinely dependency-free.

---

## D11 — How ruff actually picks up the new config

**Resolved:** 2026-08-28  
**Decision:** `make lint` passes `--config ruff.toml` explicitly.  
**Rationale:** Ruff resolves config by walking *up* from each file, so `bin/Code/Rpa/**` finds
`bin/pyproject.toml` first and silently inherits `lint.ignore = ["E722"]` with no `select`.
A root `ruff.toml` alone does **not** work. Explicit `--config` is the only reliable form.
`test_ruff_config_enforces_e722` asserts this cannot silently regress.

---

## D12 — Run timeout vs pytest timeout

**Resolved:** 2026-08-28  
**Decision:** Run deadline 90 000 ms; pytest timeout 120 000 ms (30 s headroom).  
**Rationale:** Zero headroom would mean the pytest process kills the runner mid-unwind, before
the journal is persisted — destroying the diagnostic evidence for exactly the failures you
most want to read. 30 s of headroom guarantees the journal is written. The constraint is
asserted by `test_rpa_timeout_below_pytest_timeout`.
