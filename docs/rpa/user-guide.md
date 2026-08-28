# RPA Layer — User Guide

**Status:** Finalised against Phase 9 (`chore/rpa-production-readiness`).  
**See also:** `docs/rpa/quickstart.md` (first steps), `docs/rpa/concepts.md` (mental model)

This guide covers how to use the Caissa RPA layer for day-to-day tasks: running
workflows, inspecting runs, diagnosing failures, and writing your own automations.

---

## 1. Starting the app

```bash
nohup tools/caissa > /tmp/caissa.log 2>&1 &
```

The RPA layer is active whenever Caissa is running.  Verify it is alive:

```bash
echo 'ping' | nc -U /tmp/caissa-control.sock
# {"ok": true}
```

---

## 2. Checking what is available

```bash
tools/caissa-rpa doctor
```

Output:

```
cv_available   : False
ocr_available  : False

install_hint: pip install -r requirements-rpa.txt  # then: brew install tesseract
```

The full object-tier RPA layer works without CV/OCR.  Image and OCR tiers are
optional and controlled by the `rpa_cv` test marker.

---

## 3. Inspecting the current app state

```bash
tools/caissa-rpa state
# HOME
```

The eight states are: `HOME`, `PLAYING`, `ENGINE_THINKING`, `GAME_OVER`,
`DIALOG_CONFIG`, `DIALOG_OTHER`, `MANAGER_OTHER`, `UNKNOWN`.

---

## 4. Running a workflow

```bash
tools/caissa-rpa run smoke_home --wait
# SUCCEEDED

tools/caissa-rpa run classical_invariant --wait
# SUCCEEDED
```

Without `--wait`, the command returns immediately with the `run_id`:

```bash
RUN=$(tools/caissa-rpa run smoke_home)
tools/caissa-rpa status $RUN
# {"status": "SUCCEEDED", ...}
```

Available workflows:

```bash
tools/caissa-rpa workflows
```

---

## 5. Reading the journal

```bash
tools/caissa-rpa journal $RUN
```

The journal shows:

- `env` block: DPR, theme, ui_mode, cv/ocr availability at run start
- Per-step trace: entry state, sub-state progression, convergence transitions
- Confidence and tier for every resolved element
- Error type on failure

---

## 6. Finding widgets

```bash
tools/caissa-rpa find '{"cls": "QToolBar"}'
tools/caissa-rpa find '{"object_name": "TB_OPTIONS"}'
```

---

## 7. Cancelling a run

```bash
tools/caissa-rpa cancel $RUN
# {"ok": true}
```

`cancel` is always accepted — even while a run is active.  The run unwinds
compensations before terminating with status `CANCELLED`.

---

## 8. The Classical Invariant check

Run this after any change to toolbar, config, or mode logic:

```bash
tools/caissa-rpa run classical_invariant --wait
```

A `SUCCEEDED` result means the Classical Invariant holds: the standard toolbar
entries (`TB_OPTIONS`, `TB_HELP`) are present and the Configuration dialog
opens and closes correctly.

---

## 9. Using the Python client

```python
from tests.ui.rpa_client import CaissaRpaClient, CaissaRpaError

rpa = CaissaRpaClient()

# Single-shot
stat = rpa.run_and_wait("smoke_home", timeout=30.0)
print(stat["status"])  # SUCCEEDED

# Step-by-step
run_id = rpa.start("classical_invariant")
stat = rpa.wait(run_id, timeout=30.0)
journal = rpa.journal(run_id)
```

---

## 10. Kill switch

To disable the RPA layer entirely (zero import cost, no timers):

```bash
CAISSA_RPA=0 tools/caissa
```

All 25 original `RemoteControl` verbs still work.  Every `rpa_*` verb returns
`{"error": "RPA layer disabled"}`.

---

## 11. When to use CV vs object tier

| Situation | Use |
|---|---|
| Widget has an `objectName` | Object tier (`object_name=TB_OPTIONS`) |
| Custom-painted widget (board) | Image tier + template |
| Verifying rendered text | OCR tier |
| Default | Object tier — CV is fallback only |

See `docs/rpa/vision.md` for capturing templates and working with the manifest.

---

## 12. Authoring a new workflow

See `docs/rpa/authoring-workflows.md` for the full guide.  The short version:

1. Create `bin/Code/Rpa/Workflows/my_workflow.py`
2. Define one or more `Activity` subclasses with `precondition`, `execute`, `postcondition`
3. Call `register("my_workflow", [activity1, activity2])` at module level
4. Add the module path to `_load_builtin_workflows()` in `Service.py`
5. Write a test in `tests/ui/test_rpa_workflows.py` (`rpa_ui` marker)
