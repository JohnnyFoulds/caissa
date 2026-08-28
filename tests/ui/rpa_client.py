"""
CaissaRpaClient — polling client for the Caissa RPA layer.

Wraps :class:`~tests.ui.client.CaissaClient` to provide RPA-specific helpers,
most notably :meth:`run_and_wait` which starts a workflow and polls
``rpa_status`` every 250 ms until the run reaches a terminal state.

This is the UiPath Orchestrator job+status model: there is no blocking
``rpa_await`` server-side verb; waiting is always client-side.

:spec: FR-9, §10 (feature_spec.md)
"""

import json
import time

from tests.ui.client import CaissaClient, CaissaClientError

SOCKET_PATH = "/tmp/caissa-control.sock"
_POLL_INTERVAL = 0.25  # seconds

_TERMINAL_STATUSES = frozenset(
    {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
)


class CaissaRpaError(CaissaClientError):
    """Raised when an rpa_* verb returns an error response."""


class CaissaRpaClient:
    """Polling RPA client for Caissa.

    :param socket_path: Path to the Unix domain socket.
    :param poll_interval: Poll interval for :meth:`run_and_wait` in seconds.
    :param default_timeout: Per-command socket timeout in seconds.
    """

    def __init__(
        self,
        socket_path: str = SOCKET_PATH,
        poll_interval: float = _POLL_INTERVAL,
        default_timeout: float = 10.0,
    ) -> None:
        """Initialise the client.

        :param socket_path: Path to the Unix domain socket.
        :param poll_interval: Polling interval for run_and_wait in seconds.
        :param default_timeout: Per-request socket timeout in seconds.
        """
        self._client = CaissaClient(socket_path=socket_path, default_timeout=default_timeout)
        self.poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Low-level rpa_* verb helpers
    # ------------------------------------------------------------------

    def capabilities(self) -> dict:
        """Return CV/OCR availability flags.

        :returns: Response dict from ``rpa_capabilities``.
        :raises CaissaRpaError: On error response.
        """
        return self._rpa("rpa_capabilities", {})

    def state(self) -> dict:
        """Return the current app state.

        :returns: Response dict from ``rpa_state``.
        :raises CaissaRpaError: On error response.
        """
        return self._rpa("rpa_state", {})

    def find(self, target: dict) -> dict:
        """Resolve a Target against the current snapshot.

        :param target: Target dict with ``selector`` key (and optional anchor).
        :returns: Response dict from ``rpa_find`` with ``elements`` list.
        :raises CaissaRpaError: On error response.
        """
        return self._rpa("rpa_find", {"target": target})

    def start(self, workflow: str) -> str:
        """Start a named workflow and return its run_id.

        :param workflow: Workflow name as registered in the server's registry.
        :returns: The run_id string.
        :raises CaissaRpaError: If the workflow is unknown or a run is already active.
        """
        resp = self._rpa("rpa_run", {"workflow": workflow})
        return resp["run_id"]

    def status(self, run_id: str) -> dict:
        """Return the current status of a run.

        :param run_id: Run identifier returned by :meth:`start`.
        :returns: Response dict from ``rpa_status``.
        :raises CaissaRpaError: If the run is unknown.
        """
        return self._rpa("rpa_status", {"run_id": run_id})

    def journal(self, run_id: str) -> dict:
        """Return the full journal for a (completed) run.

        :param run_id: Run identifier.
        :returns: The ``journal`` dict from ``rpa_journal``.
        :raises CaissaRpaError: If the run or its journal is not found.
        """
        resp = self._rpa("rpa_journal", {"run_id": run_id})
        return resp["journal"]

    def cancel(self, run_id: str | None = None) -> dict:
        """Request cooperative cancellation of the active (or named) run.

        :param run_id: Run to cancel; defaults to the active run.
        :returns: Response dict from ``rpa_cancel``.
        :raises CaissaRpaError: On error response.
        """
        payload: dict = {}
        if run_id is not None:
            payload["run_id"] = run_id
        return self._rpa("rpa_cancel", payload)

    def workflows(self) -> list[str]:
        """Return the list of registered workflow names.

        :returns: Sorted list of workflow name strings.
        :raises CaissaRpaError: On error response.
        """
        resp = self._rpa("rpa_workflows", {})
        return resp.get("workflows", [])

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def run_and_wait(
        self,
        workflow: str,
        timeout: float = 120.0,
    ) -> dict:
        """Start a workflow and poll until it reaches a terminal state.

        :param workflow: Workflow name.
        :param timeout: Maximum seconds to wait (defaults to 120 s).
        :returns: Final status dict from ``rpa_status``.
        :raises CaissaRpaError: If the workflow fails to start or times out.
        :raises TimeoutError: If the run does not complete within *timeout*.
        """
        run_id = self.start(workflow)
        deadline = time.monotonic() + timeout
        while True:
            stat = self.status(run_id)
            if stat.get("status") in _TERMINAL_STATUSES:
                return stat
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Run {run_id!r} did not complete within {timeout} s "
                    f"(last status: {stat.get('status')})"
                )
            time.sleep(min(self.poll_interval, remaining))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rpa(self, verb: str, payload: dict) -> dict:
        """Send a single rpa_* verb and return the response.

        :param verb: Verb name (e.g. ``"rpa_run"``).
        :param payload: JSON-serialisable payload dict.
        :returns: Response dict.
        :raises CaissaRpaError: If the response contains an ``"error"`` key.
        """
        arg = json.dumps(payload) if payload else ""
        cmd = f"{verb} {arg}" if arg else verb
        resp = self._client.send(cmd)
        if "error" in resp:
            raise CaissaRpaError(f"{verb}: {resp['error']}")
        return resp
