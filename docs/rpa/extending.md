# Extending the RPA Layer

This page documents how to add capabilities to the Caissa RPA layer without breaking
the seam invariants that make it testable.

---

## The Driver Contract

`bin/Code/Rpa/Driver.py` defines the seam between the pure engine (Runner, Activities,
AppState, Journal) and the Qt world.  It has exactly two implementations:

| Class | Where | When used |
|---|---|---|
| `QtDriver` | `Driver.py` (same file) | Live app — the only class in `Code.Rpa` permitted to import PySide6 |
| `FakeDriver` | `Fakes.py` | Unit tests and `dry_run=True` workflows |

The eight abstract methods are the contract:

| Method | Signature | Purpose |
|---|---|---|
| `snapshot` | `(depth=3) → Snapshot` | Observe the current UI state; must be fast and non-mutating |
| `click` | `(selector, target_type="widget") → dict` | Synthetic click |
| `set_text` | `(selector, value) → dict` | Set text on a `QLineEdit` / `QTextEdit` |
| `select_combo` | `(selector, value) → dict` | Set a `QComboBox` item |
| `trigger_action` | `(key) → dict` | Invoke a named Qt action |
| `now` | `() → float` | Current time in milliseconds (wall-clock for `QtDriver`, fake for `FakeDriver`) |
| `defer` | `(ms, callback) → None` | Schedule a zero-argument callback after `ms` milliseconds |
| `capture` | `(path) → str` | Save a screenshot to `path`; returns `path` |

### Invariants you must not break

- **N-RPA-2**: Only `Driver.py`, `Vision/Capture.py`, and `Service.py` may contain
  `import PySide6`.  Every other module in `Code.Rpa` is pure Python.  A test
  AST-parses all files to enforce this; adding a PySide6 import elsewhere will fail CI.

- **Timing through the driver**: All deadlines, settle windows, and backoff calculations
  in `Runner` are expressed in `driver.now()` terms.  Never call `time.time()`,
  `time.monotonic()`, or `datetime.now()` directly in engine code; always use
  `driver.now()`.  This is what lets `FakeClock` make the entire retry/timeout logic
  deterministic at zero wall-clock cost in tests.

- **ElementRef, not Qt pointers**: Driver methods receive selector strings and return
  plain dicts or dataclasses.  They never return live Qt pointers.  `QtDriver`
  re-resolves the selector at actuation time and validates with `shiboken6.isValid`.
  This eliminates the largest class of Qt use-after-free bugs.

- **Responses are dicts**: All actuation methods return `{"ok": True, ...}` on success
  or `{"error": "..."}` on failure.  Never raise from an actuation method — return the
  error dict so the Runner can classify and journal it.

---

## Adding a Method to the Driver

1. Add the method to the `Driver` base class in `Driver.py` with `raise NotImplementedError`.
   Give it an RST docstring (`:param`, `:returns:`, `:raises:`).

2. Implement it in `QtDriver` in the same file.

3. Add a matching stub to `FakeDriver` in `Fakes.py` that records the call in
   `self.calls` and returns a sensible fake response.

4. Update `test_driver_base_raises_not_implemented_for_all_methods` in
   `tests/unit/rpa/test_driver.py` to call the new method.

5. The structural tests `test_fake_driver_overrides_all_driver_methods` and
   `test_qt_driver_overrides_all_driver_methods` reflect over `Driver.__dict__`
   automatically — they will fail if you forget step 2 or 3.

---

## Adding a QtDriver Helper

`QtDriver` exposes many more methods than the eight contract methods — these are
Qt-touching helpers that `RemoteControl` delegates to directly.  They are not part of
the `Driver` contract and should not be added to the base class.

To add a new `QtDriver` helper:

1. Add the method to `QtDriver` with an RST docstring.
2. Call it from `RemoteControl._dispatch()` for the corresponding verb.
3. Add a `test_rc_contract.json` entry (or update it) if the verb is new — record the
   response key set before any code change, then add a parametrised assertion.

---

## Adding an Activity

Activities live in `bin/Code/Rpa/Activities.py`.  Each activity is a class that inherits
from `Activity` and implements:

- `precondition(ctx) → bool` — is the app in the right state to perform this action?
- `execute(ctx) → None` — perform the action via `ctx.driver.*`; must be fast and
  non-blocking (no `time.sleep()`; use `driver.defer()` for delayed work)
- `postcondition(ctx) → bool` — did the action succeed?
- `compensate(ctx) → None` — undo the action (optional; default raises `NotImplementedError`)

See `docs/rpa/activities.md` for the full activity catalogue and the `(actor, operation,
preconditions, postconditions, error semantics, NFR)` tuple format each entry must follow.

---

## Adding a State

App states are defined in `bin/Code/Rpa/AppState.py`.  The state model and its
transition table are the normative record in `docs/rpa/states.md` — update the doc
first (Gate H), then the code.

Any new `force_cancel` edge **must** declare `min_settle_ms >= 600`.  This is load-bearing:
`force_cancel` defers `proc.start()` by 300 ms to avoid a race with in-flight
`action.trigger()` singleShots (see the comments in `QtDriver.force_cancel()` for the
crash history that makes this non-negotiable), and the settle window must exceed that
deferral.  The test `test_every_force_cancel_edge_declares_min_settle_at_least_600` pins
this invariant.

---

## Keeping the Fakes Honest

`FakeDriver.snapshot()` returns a `Snapshot` built from the `World` fixture.  Unit tests
construct `World` by hand; `dry_run` loads `Resources/Rpa/Fixtures/world.json`, which is
generated from the real app by `tools/caissa-rpa capture-world`.

When you add a new state, regenerate `world.json` and commit it as a reviewable diff that
shows exactly how the UI changed.  A `dry_run` pass validates selector syntax and
state-graph reachability, but does not exercise real widgets — its response says so.
