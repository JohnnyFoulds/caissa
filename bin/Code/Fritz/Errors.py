"""
bin/Code/Fritz/Errors.py — Fritz domain exception hierarchy.

Hierarchy::

    Exception
    └─ CaissaError          (repo-wide root, Code.Rpa.Errors)
       └─ FritzError         (Fritz domain base)
          ├─ RibbonSpecError
          ├─ QssContractError
          └─ PaneNotRegisteredError

:spec: §6 (feature_spec.md), error-handling.md §1.1
"""

from __future__ import annotations

from Code.Rpa.Errors import CaissaError


class FritzError(CaissaError):
    """Base class for all errors raised by the Caissa Fritz layer (``Code.Fritz``).

    Catch this when you want to handle any Fritz failure without caring about the
    specific kind.
    """


class RibbonSpecError(FritzError):
    """Raised when a ribbon JSON file is missing, malformed, or fails schema validation."""


class QssContractError(FritzError):
    """Raised when a ``.qss`` file violates the ``qproperty-`` contract.

    This includes unbalanced braces that prevent selector parsing and any
    structural issue ``QssRules.qproperties`` cannot recover from.
    """


class PaneNotRegisteredError(FritzError):
    """Raised when ``PaneRegistry`` is asked for a key that was never registered."""
