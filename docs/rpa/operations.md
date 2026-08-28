# Operations

**Status:** Finalised against Phase 9 (`chore/rpa-production-readiness`).

---

## Journal storage

Run journals are written to:

```
UserData/RpaRuns/<run_id>/
├── journal.json          RunRecord — full sub-state trace + env block
└── failure-<step>.png    Widget capture on a step's final failed attempt
```

**`run_id` format:** `r-<yyyymmddThhmmss>-<4hex>` (UTC timestamp + random suffix).

The timestamp prefix makes retention a plain `ls -t` sort with no index file.
Two runs starting within the same second get different 4-hex suffixes.

---

## Retention

Keep the newest **50** run directories; delete the rest:

```bash
cd UserData/RpaRuns
ls -t | tail -n +51 | xargs rm -rf
```

There is no automatic pruning — run this periodically or add it to your
post-test cleanup script.

---

## Reading a journal

```bash
tools/caissa-rpa journal r-20260828T142233-9f1c | python3 -m json.tool
```

Key fields:

| Field | Meaning |
|---|---|
| `run_id` | Unique run identifier |
| `workflow_name` | Registered workflow name |
| `run_status` | `SUCCEEDED`, `FAILED`, `CANCELLED`, `TIMED_OUT` |
| `total_pumps` | Total runner pump count |
| `env.dpr` | Device pixel ratio at run start |
| `env.theme` | Active theme at run start |
| `env.ui_mode` | Active UI mode at run start |
| `env.cv_available` | Whether OpenCV was available |
| `steps[]` | Per-step records (see below) |

Per-step record fields:

| Field | Meaning |
|---|---|
| `activity_name` | Activity class name |
| `entry_state` | App state when the step started |
| `attempts` | Number of ACT→VERIFY cycles |
| `pumps` | Pumps consumed by this step |
| `sub_state_trace` | Bounded (500-entry) sequence of sub-state transitions |
| `converge_transitions` | State transitions used during CONVERGE |
| `error_type` | Exception type on failure |
| `confidence` | Winning element confidence (object/image/ocr tier) |

---

## Diagnosing a failure six weeks later

1. Find the run directory: `ls -t UserData/RpaRuns/ | head -20`
2. Read the journal: `tools/caissa-rpa journal <run_id>`
3. Open `failure-<step>.png` to see what the screen looked like at failure
4. Check `env.theme` and `env.ui_mode` — a theme or mode change can break
   object selectors that depended on widget text
5. Check `env.cv_available` — if True, a template match may have been used;
   check `confidence` and `tier` in the step record
6. Check `env.dpr` — a display change (connecting/disconnecting a Retina screen)
   can invalidate templates captured at a different DPR

---

## Headless / CI considerations

The RPA layer runs headlessly with `QT_QPA_PLATFORM=offscreen` for the
`rpa` (unit) test suite.  The `rpa_ui` integration suite requires a real display
and a running Caissa process.

In CI (`CAISSA_TEST=1`), the conftest in `tests/ui/` launches Caissa as a
subprocess and waits for its socket to become ready before running tests.

`rpa_cv` tests are excluded in CI unless `CAISSA_RPA_CV=1` is explicitly set.
They also require a real display (they skip under `QT_QPA_PLATFORM=offscreen`).

---

## CAISSA_LOG_LEVEL

| Value | Effect |
|---|---|
| `WARNING` (default) | Only warnings and errors from Code.Rpa |
| `INFO` | Workflow registration, pump counts, state transitions |
| `DEBUG` | Full widget-tree dumps, selector scores, OCR data |

```bash
CAISSA_LOG_LEVEL=DEBUG tools/caissa 2>&1 | grep "Code.Rpa" | head -100
```
