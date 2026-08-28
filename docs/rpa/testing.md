# Using the RPA Layer as a Test Harness

**Status:** Finalised against Phase 8 (`feat/rpa-workflows`).  
**See also:** `docs/rpa/authoring-workflows.md`, `docs/rpa/wire-protocol.md`

The Caissa RPA layer doubles as an automated regression harness.  This page
explains how to run the test suites and write new RPA-based tests.

---

## Test suites at a glance

| Suite | Marker | Command | Requires |
|---|---|---|---|
| Unit (engine) | `rpa` | `make test` | Python only, no display |
| Integration | `rpa_ui` | `make test-ui` | Running Caissa + `CAISSA_TEST=1` |
| CV/OCR | `rpa_cv` | `make test-cv` | Real display + cv2 + tesseract |
| All | — | `make test-all` | By path, cross-check |

```bash
make test      # QT_QPA_PLATFORM=offscreen pytest -m "unit or rpa" -v
make test-ui   # pytest -m "ui or rpa_ui" -v
make test-cv   # CAISSA_RPA_CV=1 pytest -m rpa_cv -v
make cov       # --cov=Code.Rpa --cov-fail-under=90
```

---

## Marker rules

Every test must carry exactly one suite marker (`unit`, `ui`, `rpa`, `rpa_ui`,
or `rpa_cv`).  `test_every_collected_test_has_exactly_one_suite_marker` in
`tests/unit/rpa/test_foundations.py` enforces this at collection time so a
future unmarked test becomes a hard failure rather than silently dropping out
of the selected suite.

---

## Running a workflow as a test

Use `CaissaRpaClient.run_and_wait()`:

```python
from tests.ui.rpa_client import CaissaRpaClient

rpa = CaissaRpaClient()
stat = rpa.run_and_wait("smoke_home", timeout=30.0)
assert stat["status"] == "SUCCEEDED"
```

Or use `tools/caissa-rpa` from the shell:

```bash
tools/caissa-rpa run smoke_home --wait
```

---

## Built-in regression workflows

| Workflow | What it checks |
|---|---|
| `smoke_home` | App starts; converges to HOME |
| `classical_invariant` | Classical toolbar layout is unchanged |
| `play_a_game` | Game start and PLAYING state transition |
| `config_roundtrip` | Config form reads/writes player name correctly |

Run all four:

```bash
tools/caissa-rpa run smoke_home --wait
tools/caissa-rpa run classical_invariant --wait
tools/caissa-rpa run play_a_game --wait
tools/caissa-rpa run config_roundtrip --wait
```

---

## Classical Invariant

The `classical_invariant` workflow is the primary guard for the Classical Invariant
constraint: *`classical` mode + no theme overlay = upstream Lucas Chess R6 exactly*.

It verifies:

1. The standard toolbar items (`TB_OPTIONS`, `TB_HELP`) are visible at HOME.
2. The Configuration dialog opens successfully.
3. The dialog closes cleanly.

This workflow must pass in CI on every PR that touches toolbar, config, or mode
logic.  A failure means the Classical Invariant has been broken.

---

## The dry_run flag

`rpa_run {"workflow": "my_wf", "dry_run": true}` validates a workflow's structure
without executing any Qt actions:

- Selector syntax is valid
- Every template reference is in the manifest
- The state graph has a path from UNKNOWN to each `required_state`
- No precondition is structurally unsatisfiable

A dry_run pass is a **lint**, not a green test.  It does not exercise real widgets.

```bash
tools/caissa-rpa run my_wf --dry-run
```

---

## Diagnosing a failed run

```bash
tools/caissa-rpa journal <run_id>
```

The journal shows:

- `env` block: DPR, theme, ui_mode, cv/ocr availability at run start
- Per-step trace: entry state, sub-state progression, convergence transitions
- Confidence and tier for every resolved element
- Error type on failure

A `failure-<step>.png` capture is written alongside the journal when a step's
final attempt fails.

See `docs/rpa/operations.md` for retention policy and long-term diagnostics.

---

## Writing new regression tests

**Prefer `rpa_ui` integration tests over unit mocks** for end-to-end regression
coverage.  Use unit tests (`rpa` marker, `FakeDriver + FakeWorld`) to validate
activity logic in isolation without Qt.

```python
# tests/ui/test_rpa_my_feature.py
import pytest
from tests.ui.rpa_client import CaissaRpaClient

pytestmark = pytest.mark.rpa_ui

def test_my_feature_succeeds(client):
    rpa = CaissaRpaClient()
    stat = rpa.run_and_wait("my_workflow", timeout=30.0)
    assert stat["status"] == "SUCCEEDED"
```

**CV assertions must be paired with object-tier assertions** where possible.
CV-only tests carry `rpa_cv` and are excluded from the default run (see
`docs/rpa/vision.md`).
