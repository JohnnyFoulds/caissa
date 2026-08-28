"""
bin/Code/Rpa/Journal.py — Run and step record dataclasses with JSON persistence.

Every completed run writes a ``RunRecord`` to
``UserData/RpaRuns/<run_id>/journal.json``.  The ``env`` block captures the runtime
environment at run start (theme, mode, cv availability, DPR) so a failed run is
diagnosable weeks later without requiring the exact app state to be reproduced.

Sub-state traces are bounded to 500 entries to prevent a runaway convergence loop
from producing an unreadably large journal.

:spec: FR-6, §6.4 (feature_spec.md)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Maximum sub-state trace entries per step record
_MAX_TRACE = 500


@dataclasses.dataclass
class StepRecord:
    """Journal entry for a single activity step.

    :param index: 0-based step index within the run.
    :param activity_name: ``Activity.name`` of the step's activity.
    :param entry_state: App state recognised when the step was entered.
    :param exit_state: App state recognised when the step exited (or ``None`` if failed).
    :param attempts: Number of ``CHECK_PRE → ACT → VERIFY`` cycles attempted.
    :param pumps: Total pump calls consumed by this step.
    :param result: ``"ok"``, ``"compensated"``, or ``"failed"``.
    :param error: Exception message if the step failed; ``None`` otherwise.
    :param sub_state_trace: Ordered list of sub-state names visited (bounded to
        :data:`_MAX_TRACE` entries).
    :param duration_ms: Wall-clock duration in milliseconds (``driver.now()`` delta).
    """

    index: int
    activity_name: str
    entry_state: str
    exit_state: str | None = None
    attempts: int = 0
    pumps: int = 0
    result: str = "pending"
    error: str | None = None
    sub_state_trace: list[str] = dataclasses.field(default_factory=list)
    duration_ms: float = 0.0

    def record_sub_state(self, sub_state_name: str) -> None:
        """Append *sub_state_name* to the trace if under the limit.

        :param sub_state_name: Sub-state enum member name.
        """
        if len(self.sub_state_trace) < _MAX_TRACE:
            self.sub_state_trace.append(sub_state_name)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict.

        :returns: Dict suitable for ``json.dumps``.
        """
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepRecord":
        """Deserialise from a dict.

        :param data: Dict as produced by :meth:`to_dict`.
        :returns: :class:`StepRecord` instance.
        """
        return cls(**{k: v for k, v in data.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass
class RunRecord:
    """Journal entry for a complete workflow run.

    :param run_id: Unique run identifier — ``r-<yyyymmddThhmmss>-<4hex>``.
    :param workflow_name: Name of the workflow that was executed.
    :param status: Run-level status — one of ``PENDING``, ``RUNNING``,
        ``CANCELLING``, ``SUCCEEDED``, ``FAILED``, ``CANCELLED``, ``TIMED_OUT``.
    :param created_at_ms: ``driver.now()`` when the run was created.
    :param completed_at_ms: ``driver.now()`` when the run reached a terminal state;
        ``None`` while still running.
    :param total_pumps: Total pump calls across the run's lifetime.
    :param steps: Ordered list of step records (one per activity executed).
    :param error: Exception message if the run failed; ``None`` otherwise.
    :param env: Runtime environment snapshot — ``{dpr, theme, ui_mode, translator,
        cv_available, ocr_available, python_version}``.
    """

    run_id: str
    workflow_name: str
    status: str = "PENDING"
    created_at_ms: float = 0.0
    completed_at_ms: float | None = None
    total_pumps: int = 0
    steps: list[StepRecord] = dataclasses.field(default_factory=list)
    error: str | None = None
    env: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict.

        :returns: Nested dict suitable for ``json.dumps``.
        """
        d = dataclasses.asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        """Deserialise from a dict.

        :param data: Dict as produced by :meth:`to_dict`.
        :returns: :class:`RunRecord` instance.
        """
        steps_raw = data.pop("steps", [])
        env = data.pop("env", {})
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        record = cls(**filtered, env=env)
        record.steps = [StepRecord.from_dict(s) for s in steps_raw]
        return record


class Journal:
    """Namespace for run journal persistence operations.

    Journals are written to ``UserData/RpaRuns/<run_id>/journal.json``.
    A directory per run keeps failure captures alongside the journal that explains them.
    """

    @staticmethod
    def persist(record: RunRecord, run_dir: str) -> None:
        """Write *record* to ``<run_dir>/journal.json``, creating the directory if needed.

        :param record: The run record to write.
        :param run_dir: Directory for this run (e.g. ``UserData/RpaRuns/r-20260828T142233-9f1c``).
        :raises JournalError: If the file cannot be written.
        """
        from Code.Rpa.Errors import JournalError
        try:
            os.makedirs(run_dir, exist_ok=True)
            path = os.path.join(run_dir, "journal.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(record.to_dict(), fh, indent=2)
            logger.debug("Journal written: %s", path)
        except OSError as exc:
            raise JournalError(f"Could not write journal to {run_dir!r}: {exc}") from exc

    @staticmethod
    def load(run_dir: str) -> RunRecord:
        """Read the journal from ``<run_dir>/journal.json``.

        :param run_dir: Directory for the run.
        :returns: :class:`RunRecord` instance.
        :raises JournalError: If the file cannot be read or parsed.
        """
        from Code.Rpa.Errors import JournalError
        path = os.path.join(run_dir, "journal.json")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            return RunRecord.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
            raise JournalError(f"Could not load journal from {path!r}: {exc}") from exc
