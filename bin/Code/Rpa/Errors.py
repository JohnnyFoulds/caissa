"""
bin/Code/Rpa/Errors.py — Caissa exception hierarchy root and RPA domain exceptions.

This module is the canonical home of ``CaissaError`` — the repo-wide base class for all
errors raised by Caissa-specific code, as mandated by
``docs/standards/error-handling.md §1.1``.  It also hosts ``RpaError`` and all 15
RPA-specific exception classes.

Other Caissa domains may define their own base that inherits ``CaissaError``,
following the ``RpaError`` pattern here.

Hierarchy::

    Exception
    └─ CaissaError          (repo-wide root)
       └─ RpaError           (RPA domain base)
          ├─ DriverError
          ├─ SelectorError
          ├─ AmbiguousMatchError
          ├─ TargetNotFoundError
          ├─ PreconditionError
          ├─ PostconditionError
          ├─ ConvergeError
          ├─ RunAlreadyActiveError
          ├─ RunNotFoundError
          ├─ WorkflowNotFoundError
          ├─ VisionUnavailableError
          ├─ ManifestError
          ├─ JournalError
          ├─ StateError
          └─ RpaConfigError

:spec: §11 (feature_spec.md), error-handling.md §1.1
"""


class CaissaError(Exception):
    """Base class for all errors raised by Caissa-specific code.

    Downstream code should catch ``CaissaError`` when it wants to handle any
    Caissa-specific failure without caring about the domain.  Domain code should
    catch the most specific type available.
    """


class RpaError(CaissaError):
    """Base class for all errors raised by the Caissa RPA layer (``Code.Rpa``).

    Catch this when you want to handle any RPA failure without caring about the
    specific kind.
    """


class DriverError(RpaError):
    """Raised when a driver operation (Qt actuation or observation) fails."""


class SelectorError(RpaError):
    """Raised when a Selector is malformed or lacks a discriminating field."""


class AmbiguousMatchError(RpaError):
    """Raised when a resolve call returns more than one candidate at equal confidence."""


class TargetNotFoundError(RpaError):
    """Raised when no element matching the Target can be found within the timeout."""


class PreconditionError(RpaError):
    """Raised when an Activity's precondition cannot be satisfied after convergence."""


class PostconditionError(RpaError):
    """Raised when an Activity's postcondition is not satisfied within the verify deadline."""


class ConvergeError(RpaError):
    """Raised when the state graph cannot find a path to the required state."""


class RunAlreadyActiveError(RpaError):
    """Raised when a second run is requested while one is already RUNNING.

    :attr active_run_id: The ``run_id`` of the currently active run.
    :attr current_sub_state: The sub-state the active run is in when rejected.
    """

    def __init__(self, active_run_id: str, current_sub_state: str) -> None:
        """Initialise with the blocking run's identity for operator diagnostics.

        :param active_run_id: run_id of the active run.
        :param current_sub_state: current sub-state of the active run.
        """
        super().__init__(
            f"Run {active_run_id!r} is already active (sub-state: {current_sub_state}). "
            f"Call rpa_status or rpa_cancel before starting a new run."
        )
        self.active_run_id = active_run_id
        self.current_sub_state = current_sub_state


class RunNotFoundError(RpaError):
    """Raised when rpa_status / rpa_journal is called with an unknown run_id."""


class WorkflowNotFoundError(RpaError):
    """Raised when the workflow registry is asked for an unregistered name."""


class VisionUnavailableError(RpaError):
    """Raised when a CV/OCR tier is explicitly requested but the library is absent.

    :attr reason: Human-readable message that includes the exact install command.
    """

    def __init__(self, reason: str) -> None:
        """Initialise with an actionable fix message.

        :param reason: Exact install command or dependency hint (e.g.
            ``pip install -r requirements-rpa.txt``).
        """
        super().__init__(reason)
        self.reason = reason


class ManifestError(RpaError):
    """Raised when the template manifest is missing, malformed, or a sha256 check fails."""


class JournalError(RpaError):
    """Raised when a run journal cannot be written or read."""


class StateError(RpaError):
    """Raised when the app state recogniser returns an unexpected or invalid value."""


class RpaConfigError(RpaError):
    """Raised when the RPA layer is misconfigured (e.g. invalid timeout value)."""
