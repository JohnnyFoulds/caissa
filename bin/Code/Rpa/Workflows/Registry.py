"""
bin/Code/Rpa/Workflows/Registry.py — Central workflow registry for the Caissa RPA layer.

Workflow modules register their activity lists here at import time.  The service
calls :func:`get` to look up a workflow by name before starting a run.

Usage::

    # In a workflow module:
    from Code.Rpa.Workflows.Registry import register
    register("smoke_home", [AssertAtHome()])

    # In the service or tests:
    from Code.Rpa.Workflows.Registry import get, all_names
    activities = get("smoke_home")

:spec: FR-10, §13 (feature_spec.md)
"""

from __future__ import annotations

import logging

from Code.Rpa.Errors import WorkflowNotFoundError

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, list] = {}


def register(name: str, activities: list) -> None:
    """Register a workflow by name.

    Replaces any existing registration for *name* (last call wins, enabling
    test overrides).

    :param name: Workflow identifier used in ``rpa_run`` requests.
    :param activities: Flat list of :class:`~Code.Rpa.Activities.Activity` instances.
    """
    _REGISTRY[name] = list(activities)
    logger.debug("Registered workflow %r (%d activities)", name, len(activities))


def get(name: str) -> list:
    """Return a fresh copy of the activity list for *name*.

    :param name: Workflow identifier.
    :returns: Copy of the activity list (safe to mutate for a single run).
    :raises WorkflowNotFoundError: If no workflow is registered under *name*.
    """
    if name not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise WorkflowNotFoundError(
            f"Workflow {name!r} is not registered. "
            f"Available: {available}"
        )
    return list(_REGISTRY[name])


def all_names() -> list[str]:
    """Return the sorted list of registered workflow names.

    :returns: Alphabetically sorted list of names.
    """
    return sorted(_REGISTRY)


def _clear() -> None:
    """Remove all registrations.  For testing only."""
    _REGISTRY.clear()
