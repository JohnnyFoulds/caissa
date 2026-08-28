"""
bin/Code/Rpa/Service.py — RPA run registry and ``rpa_*`` verb handlers.

``RpaService`` is the only class in this module that imports PySide6 (the
``QTimer``); all verb-handling methods are pure Python so they can be tested
with a :class:`~Code.Rpa.Fakes.FakeDriver` without a live Qt application.

The service is instantiated lazily by :class:`~Code.Debug.RemoteControl` via
its :meth:`~Code.Debug.RemoteControl._rpa` accessor the first time an
``rpa_*`` verb arrives.  Set ``CAISSA_RPA=0`` in the environment to disable
the RPA layer entirely; every ``rpa_*`` verb will return
``{"error": "RPA layer disabled (CAISSA_RPA=0)"}`` and ``Code.Rpa`` is never
imported.

Journals are written to ``<userdata>/RpaRuns/<run_id>/journal.json``.
:func:`_run_base_dir` resolves ``<userdata>`` via ``Code.configuration`` so
it picks up a custom UserData folder if one is configured.

:spec: FR-3, FR-8, FR-9, NFR-2, NFR-4, §10 (feature_spec.md)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workflow registry (populated by Code.Rpa.Workflows modules at import time)
# ---------------------------------------------------------------------------

def register_workflow(name: str, activities: list) -> None:
    """Register a named workflow.

    Delegates to :func:`~Code.Rpa.Workflows.Registry.register`.  Kept for
    backwards compatibility with any code that called ``Service.register_workflow``.

    :param name: Workflow name used in ``rpa_run`` requests.
    :param activities: Top-level activity list.
    :returns: None.
    """
    from Code.Rpa.Workflows.Registry import register as _reg
    _reg(name, activities)
    logger.debug("Workflow registered via Service: %r (%d activities)", name, len(activities))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_base_dir() -> str:
    """Return the absolute path to the run journal directory.

    :returns: ``<userdata>/RpaRuns`` — created on first use.
    """
    try:
        import Code
        base = Code.configuration.userdata_folder if Code.configuration else "UserData"
    except Exception:
        base = "UserData"
    path = os.path.join(base, "RpaRuns")
    os.makedirs(path, exist_ok=True)
    return path


def generate_run_id() -> str:
    """Generate a unique run identifier: ``r-<yyyymmddThhmmss>-<4hex>``.

    :returns: Run ID string matching the scheme ``r-\\d{8}T\\d{6}-[0-9a-f]{4}``.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"r-{ts}-{suffix}"


def _env_snapshot() -> dict[str, Any]:
    """Capture runtime environment for the journal ``env`` block.

    :returns: Dict with dpr, theme, ui_mode, cv_available, ocr_available.
    """
    env: dict[str, Any] = {
        "dpr": 1.0,
        "theme": "unknown",
        "ui_mode": "unknown",
        "cv_available": False,
        "ocr_available": False,
    }
    try:
        import Code
        if Code.configuration:
            env["theme"] = getattr(Code.configuration, "x_style_mode", "unknown") or "unknown"
            env["ui_mode"] = getattr(Code.configuration, "x_ui_mode", "unknown") or "unknown"
    except Exception:
        pass
    try:
        import cv2  # noqa: F401
        env["cv_available"] = True
    except ImportError:
        pass
    try:
        import pytesseract  # noqa: F401
        env["ocr_available"] = True
    except ImportError:
        pass
    return env


def _load_builtin_workflows() -> None:
    """Import all built-in workflow modules so they self-register.

    Called once at RpaService init.  Import errors are logged and swallowed
    so a broken workflow does not prevent the service from starting.
    """
    _modules = [
        "Code.Rpa.Workflows.smoke_home",
        "Code.Rpa.Workflows.classical_invariant",
        "Code.Rpa.Workflows.play_a_game",
        "Code.Rpa.Workflows.config_roundtrip",
    ]
    for mod in _modules:
        try:
            import importlib
            importlib.import_module(mod)
        except Exception as exc:
            logger.warning("Failed to load workflow module %r: %s", mod, exc)


# ---------------------------------------------------------------------------
# RpaService
# ---------------------------------------------------------------------------

class RpaService:
    """Run registry + QTimer pump + ``rpa_*`` verb handlers.

    Only this class in ``Code.Rpa`` may import PySide6; the verb methods are
    pure Python so they are unit-testable with a
    :class:`~Code.Rpa.Fakes.FakeDriver`.

    :param driver: The :class:`~Code.Rpa.Driver.QtDriver` (or
        :class:`~Code.Rpa.Fakes.FakeDriver`) instance.
    :param run_base_dir: Override the journal root directory.  Defaults to
        :func:`_run_base_dir`.
    :param _start_pump: If ``False`` (unit-test mode) the QTimer is not
        created and callers drive the runner via :meth:`pump_once`.
    """

    def __init__(
        self,
        driver,
        run_base_dir: str | None = None,
        _start_pump: bool = True,
    ) -> None:
        """Initialise the service.

        :param driver: Driver instance.
        :param run_base_dir: Optional override for the journal root.
        :param _start_pump: Start the QTimer pump (set False for unit tests).
        """
        self._driver = driver
        self._run_base_dir = run_base_dir  # None → resolved lazily
        self._runs: dict[str, "Runner"] = {}
        self._active_run_id: str | None = None

        if _start_pump:
            from PySide6 import QtCore
            self._timer = QtCore.QTimer()
            self._timer.timeout.connect(self.pump_once)
            self._timer.start(50)
            logger.debug("RpaService pump timer started (50 ms)")
        else:
            self._timer = None

        # Import all workflow modules so they register on first service start
        _load_builtin_workflows()

    # ------------------------------------------------------------------
    # Pump
    # ------------------------------------------------------------------

    def pump_once(self) -> None:
        """Advance the active run by one pump call (called on Qt main thread).

        :returns: None.
        """
        if self._active_run_id is None:
            return
        runner = self._runs.get(self._active_run_id)
        if runner is None:
            self._active_run_id = None
            return
        still_running = runner.pump()
        if not still_running:
            logger.debug("Run %r completed: %s", self._active_run_id, runner.run_status.value)
            self._active_run_id = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolved_run_base_dir(self) -> str:
        """Return the journal root, resolving lazily if needed.

        :returns: Absolute path to the RpaRuns directory.
        """
        if self._run_base_dir is not None:
            os.makedirs(self._run_base_dir, exist_ok=True)
            return self._run_base_dir
        return _run_base_dir()

    def _start_run(self, activities: list, workflow_name: str = "unnamed") -> str:
        """Create a new Runner, register it, and set it as active.

        :param activities: Top-level activity list.
        :param workflow_name: Name stored in the journal.
        :returns: The new run_id.
        :raises RunAlreadyActiveError: If a run is already RUNNING.
        """
        from Code.Rpa.Errors import RunAlreadyActiveError
        from Code.Rpa.Runner import Runner, RunStatus

        if self._active_run_id is not None:
            active_runner = self._runs.get(self._active_run_id)
            if active_runner is not None and active_runner.run_status not in (
                RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT
            ):
                raise RunAlreadyActiveError(
                    self._active_run_id,
                    active_runner._sub_state.value,
                )

        run_id = generate_run_id()
        run_dir = os.path.join(self._resolved_run_base_dir(), run_id)
        runner = Runner(
            driver=self._driver,
            activities=activities,
            run_id=run_id,
            workflow_name=workflow_name,
            run_dir=run_dir,
        )
        self._runs[run_id] = runner
        self._active_run_id = run_id
        # Write env block now so it is available even if the run fails immediately
        runner._run_record.env = _env_snapshot()
        logger.debug("Run %r started: workflow=%r", run_id, workflow_name)
        return run_id

    # ------------------------------------------------------------------
    # rpa_* verb handlers (pure Python — testable without Qt)
    # ------------------------------------------------------------------

    def rpa_capabilities(self, arg: str) -> dict:
        """Return CV/OCR availability flags and install hints.

        :param arg: Ignored.
        :returns: Dict with ``cv_available``, ``ocr_available``, and ``install_hint``.
        """
        cv_available = False
        ocr_available = False
        cv_version = None
        try:
            import cv2  # noqa: F401
            cv_available = True
            cv_version = cv2.__version__
        except ImportError:
            pass
        try:
            import pytesseract  # noqa: F401
            ocr_available = True
        except ImportError:
            pass
        install_hint = None if (cv_available and ocr_available) else (
            "pip install -r requirements-rpa.txt  # then: brew install tesseract"
        )
        return {
            "cv_available": cv_available,
            "ocr_available": ocr_available,
            "cv_version": cv_version,
            "install_hint": install_hint,
        }

    def rpa_state(self, arg: str) -> dict:
        """Return the current app state name and recogniser evidence.

        :param arg: Ignored.
        :returns: Dict with ``state`` and ``widgets`` (abbreviated snapshot).
        """
        from Code.Rpa.AppState import recognise
        snap = self._driver.snapshot()
        state = recognise(snap)
        return {
            "state": state,
            "widgets": snap.widget_tree[:5] if snap.widget_tree else [],
        }

    def rpa_find(self, arg: str) -> dict:
        """Resolve a Target against the current snapshot.

        :param arg: JSON string containing a ``target`` key.
        :returns: Dict with ``elements`` list of matching ElementRef dicts.
        """
        from Code.Rpa.Targets import Target
        from Code.Rpa.Resolve import TargetResolver
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        target_data = data.get("target")
        if not target_data:
            return {"error": "missing 'target' key"}
        try:
            target = Target.from_json(target_data)
        except Exception as exc:
            return {"error": f"invalid target: {exc}"}
        snap = self._driver.snapshot()
        resolver = TargetResolver()
        try:
            elements = resolver.visible_elements(snap)
            # Filter to those matching the selector
            candidates = resolver._object_candidates(target.selector, snap)
            return {
                "elements": [
                    {
                        "object_name": e.object_name,
                        "cls": e.cls,
                        "text": e.text,
                        "rect": list(e.rect) if e.rect else None,
                        "confidence": e.confidence,
                    }
                    for e in (c.element for c in candidates)
                ],
                "count": len(candidates),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def rpa_run(self, arg: str) -> dict:
        """Start a named workflow and return its run_id.

        :param arg: JSON string with ``workflow`` key, optional ``dry_run``.
        :returns: Dict with ``run_id``.
        """
        from Code.Rpa.Errors import RunAlreadyActiveError, WorkflowNotFoundError
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        workflow_name = data.get("workflow", "")
        if not workflow_name:
            return {"error": "missing 'workflow' key"}
        from Code.Rpa.Workflows.Registry import get as _wf_get
        try:
            activities = _wf_get(workflow_name)
        except WorkflowNotFoundError as exc:
            return {"error": str(exc)}
        try:
            activities = list(activities)  # fresh copy
            run_id = self._start_run(activities, workflow_name=workflow_name)
            return {"run_id": run_id}
        except RunAlreadyActiveError as exc:
            return {"error": str(exc), "active_run_id": exc.active_run_id}
        except Exception as exc:
            logger.error("rpa_run failed: %s", exc, exc_info=True)
            return {"error": str(exc)}

    def rpa_status(self, arg: str) -> dict:
        """Return the status of a run by run_id.

        :param arg: JSON string with ``run_id`` key.
        :returns: Dict with ``status``, ``sub_state``, and ``total_pumps``.
        """
        from Code.Rpa.Errors import RunNotFoundError
        from Code.Rpa.Runner import RunStatus
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        run_id = data.get("run_id", "")
        runner = self._runs.get(run_id)
        if runner is None:
            return {"error": str(RunNotFoundError(
                f"Run {run_id!r} not found. "
                f"Known runs: {list(self._runs)[:5]}"
            ))}
        sub_state = getattr(runner, "_sub_state", None)
        return {
            "run_id": run_id,
            "status": runner.run_status.value,
            "sub_state": sub_state.value if sub_state else None,
            "total_pumps": runner._total_pumps,
            "active": run_id == self._active_run_id,
        }

    def rpa_journal(self, arg: str) -> dict:
        """Return the full journal for a completed run.

        :param arg: JSON string with ``run_id`` key.
        :returns: Dict with the serialised :class:`~Code.Rpa.Journal.RunRecord`.
        """
        from Code.Rpa.Errors import JournalError, RunNotFoundError
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        run_id = data.get("run_id", "")
        if not run_id:
            return {"error": "missing 'run_id' key"}
        runner = self._runs.get(run_id)
        if runner is not None:
            return {"journal": runner._run_record.to_dict()}
        # Try to load from disk
        run_dir = os.path.join(self._resolved_run_base_dir(), run_id)
        try:
            from Code.Rpa.Journal import Journal
            record = Journal.load(run_dir)
            return {"journal": record.to_dict()}
        except JournalError as exc:
            return {"error": str(RunNotFoundError(
                f"Run {run_id!r} not found in memory or on disk: {exc}"
            ))}

    def rpa_cancel(self, arg: str) -> dict:
        """Request cooperative cancellation of the active run.

        :param arg: JSON string with optional ``run_id`` key.
        :returns: Dict with ``ok`` and the ``run_id`` cancelled.
        """
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError:
            data = {}
        run_id = data.get("run_id") or self._active_run_id
        if run_id is None:
            return {"ok": True, "message": "no active run to cancel"}
        runner = self._runs.get(run_id)
        if runner is None:
            return {"error": f"run {run_id!r} not found"}
        runner.cancel()
        logger.debug("rpa_cancel: run %r set to CANCELLING", run_id)
        return {"ok": True, "run_id": run_id}

    def rpa_converge(self, arg: str) -> dict:
        """Start a convergence-only run to reach a target app state.

        :param arg: JSON string with ``state`` key.
        :returns: Dict with ``run_id``.
        """
        from Code.Rpa.Errors import RunAlreadyActiveError
        from Code.Rpa.Activities import Activity
        from Code.Rpa.AppState import recognise
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        target_state = data.get("state", "")
        if not target_state:
            return {"error": "missing 'state' key"}

        class _ConvergeActivity(Activity):
            name = "Converge"
            settle_ms = 0
            max_attempts = 1
            required_state = target_state

            def precondition(self_, ctx):
                return recognise(ctx.snapshot) == target_state

            def execute(self_, ctx):
                pass

            def postcondition(self_, ctx):
                return recognise(ctx.refresh_snapshot()) == target_state

        try:
            run_id = self._start_run([_ConvergeActivity()], workflow_name=f"converge:{target_state}")
            return {"run_id": run_id}
        except RunAlreadyActiveError as exc:
            return {"error": str(exc), "active_run_id": exc.active_run_id}

    def rpa_act(self, arg: str) -> dict:
        """Start a single-activity run from an activity description.

        :param arg: JSON string with ``activity`` key containing an activity dict.
        :returns: Dict with ``run_id``.
        """
        from Code.Rpa.Errors import RunAlreadyActiveError
        try:
            data = json.loads(arg) if arg else {}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        activity_data = data.get("activity")
        if not activity_data:
            return {"error": "missing 'activity' key"}
        activity_type = activity_data.get("type", "")
        try:
            activity = _build_activity(activity_type, activity_data)
        except Exception as exc:
            return {"error": f"cannot build activity {activity_type!r}: {exc}"}
        try:
            run_id = self._start_run([activity], workflow_name=f"act:{activity_type}")
            return {"run_id": run_id}
        except RunAlreadyActiveError as exc:
            return {"error": str(exc), "active_run_id": exc.active_run_id}

    def rpa_workflows(self, arg: str) -> dict:
        """List registered workflow names.

        :param arg: Ignored.
        :returns: Dict with ``workflows`` list.
        """
        from Code.Rpa.Workflows.Registry import all_names as _all_names
        return {"workflows": _all_names()}


# ---------------------------------------------------------------------------
# Activity builder for rpa_act
# ---------------------------------------------------------------------------

def _build_activity(activity_type: str, data: dict):
    """Instantiate a concrete Activity from a JSON description.

    :param activity_type: Activity class name (e.g. ``"Click"``, ``"OpenConfig"``).
    :param data: JSON dict including ``type`` and activity-specific fields.
    :returns: :class:`~Code.Rpa.Activities.Activity` instance.
    :raises ValueError: If the type is unknown or required fields are missing.
    """
    from Code.Rpa.Activities import (
        Click, CloseDialog, ElementExists, GetText, OpenConfig,
        SelectItem, SwitchTab, TakeScreenshot, TypeInto,
    )
    from Code.Rpa.Targets import Selector

    _MAP = {
        "Click": Click,
        "TypeInto": TypeInto,
        "SelectItem": SelectItem,
        "GetText": GetText,
        "ElementExists": ElementExists,
        "TakeScreenshot": TakeScreenshot,
        "OpenConfig": OpenConfig,
        "CloseDialog": CloseDialog,
        "SwitchTab": SwitchTab,
    }
    cls = _MAP.get(activity_type)
    if cls is None:
        raise ValueError(f"Unknown activity type {activity_type!r}. Known: {sorted(_MAP)}")

    if cls is TakeScreenshot:
        return cls(filename=data.get("filename", "screenshot.png"))
    if cls is SwitchTab:
        return cls(tab_name=data.get("tab_name", ""))
    if cls is GetText:
        sel = Selector.from_json(data["selector"])
        return cls(selector=sel, output_key=data.get("output_key", "text"))
    if cls in (Click, TypeInto, SelectItem, ElementExists):
        sel = Selector.from_json(data["selector"])
        if cls is TypeInto:
            return cls(selector=sel, text=data.get("text", ""), clear_before=data.get("clear_before", True))
        if cls is SelectItem:
            return cls(selector=sel, value=data.get("value", ""))
        if cls is ElementExists:
            return cls(selector=sel, output_key=data.get("output_key"))
        return cls(selector=sel, settle_ms=data.get("settle_ms", 200))
    return cls()
