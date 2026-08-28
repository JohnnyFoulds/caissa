# Troubleshooting

**Status:** Finalised against Phase 9 (`chore/rpa-production-readiness`).

---

## Socket problems

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` / `No such file or directory` | Caissa not running | `tools/caissa &` |
| `Connection timed out` | Socket exists but app is frozen | Kill and restart Caissa |
| `{"error": "RPA layer disabled"}` | `CAISSA_RPA=0` in environment | `unset CAISSA_RPA` |

---

## Run errors

| Symptom | Cause | Fix |
|---|---|---|
| `RunAlreadyActiveError` — includes `active_run_id` | Previous run still in progress | `tools/caissa-rpa cancel <run_id>` |
| `WorkflowNotFoundError` | Workflow not registered | Check `tools/caissa-rpa workflows`; load workflow module |
| Status `TIMED_OUT` | Run exceeded 90 s | Read journal; check for stuck convergence |
| Status `FAILED` | Postcondition not satisfied | Read journal; check `failure-<step>.png` captures |
| Status `CANCELLED` | `rpa_cancel` was called | Intentional; re-run if needed |

---

## Convergence problems

| Symptom | Cause | Fix |
|---|---|---|
| `CONVERGE_BUDGET_EXCEEDED` in journal | App stuck mid-transition | Check `failure-<step>.png`; verify state graph has a path |
| Run loops in CONVERGE without advancing | All transitions fail | Check that `force_cancel` settle times are respected (≥600 ms) |
| State always `UNKNOWN` | Recogniser can't identify the screen | `tools/caissa-rpa state` + inspect widget tree |

---

## Widget resolution failures

| Symptom | Cause | Fix |
|---|---|---|
| `TargetNotFoundError` | Widget not in tree or wrong selector | `tools/caissa-rpa find` to inspect; use `object_name` over `text` |
| `AmbiguousMatchError` | Multiple widgets match | Add `object_name`, `text_exact=True`, or `index` |
| CV win emits warning | Object selector is broken | Fix the object selector; CV is a fallback not a primary |
| `VisionUnavailableError: cv2 not installed` | cv2 absent | `pip install -r requirements-rpa.txt` |
| `VisionUnavailableError: tesseract binary not found` | Tesseract absent | `brew install tesseract` (macOS) / `apt install tesseract-ocr` |

---

## Manifest / template problems

| Symptom | Cause | Fix |
|---|---|---|
| `ManifestError: template not found` | Workflow references unregistered template | Add entry to `manifest.json` |
| `ManifestError: SHA-256 mismatch` | Template file changed since manifest was written | Re-capture template; update manifest |
| `logger.warning: stale template` | Template matched at non-unit scale | Re-capture at DPR-1 |

---

## Test suite problems

| Symptom | Cause | Fix |
|---|---|---|
| `rpa_cv` tests run and fail | cv2 is installed but display is offscreen | Add `QT_QPA_PLATFORM=offscreen` or run `make test` not `make test-cv` |
| `test_every_collected_test_has_exactly_one_suite_marker` fails | New test missing a marker | Add `pytestmark = pytest.mark.rpa` (or correct marker) |
| `make cov` under 90% | New code not covered by default suite | Add tests or add to omit list with justification |
| `make lint` fails | Ruff misconfigured | Ensure `--config ruff.toml` is in the lint command |

---

## Known crash history

These issues are documented in `RemoteControl.py` comments and are handled by the
existing `force_cancel` guard:

- **Qt use-after-free** — `_force_cancel()` defers `proc.start()` by 300 ms to
  avoid a race with any in-flight `action.trigger()` singleShot.  Every
  `force_cancel` state-graph edge declares `min_settle_ms >= 600`.
- **`shiboken6.isValid`** — `ElementRef` re-resolves its selector at actuation time
  and calls `isValid` before use.

---

## Logging

Enable verbose RPA logging:

```bash
CAISSA_LOG_LEVEL=DEBUG tools/caissa 2>&1 | grep "Code.Rpa"
```

The default level is `WARNING` so normal Caissa use is unaffected.

To enable fault handler (C-level crash traceback):

```bash
CAISSA_RPA_FAULTHANDLER=1 tools/caissa
```
