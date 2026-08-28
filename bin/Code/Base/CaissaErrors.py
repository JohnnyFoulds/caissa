"""
bin/Code/Base/CaissaErrors.py — Repo-wide Caissa exception root.

``CaissaError`` is the base class for all errors raised by Caissa-specific code.
It lives here in ``Code.Base`` so that independent Caissa domains (``Code.Rpa``,
``Code.Retro``, etc.) can inherit from it without coupling to each other's packages.

``Code.Rpa.Errors`` re-exports ``CaissaError`` for backward compatibility.

:spec: decisions.md D1
"""


class CaissaError(Exception):
    """Base class for all errors raised by Caissa-specific code.

    Downstream code should catch ``CaissaError`` when it wants to handle any
    Caissa-specific failure without caring about the domain.  Domain code should
    catch the most specific type available.
    """
