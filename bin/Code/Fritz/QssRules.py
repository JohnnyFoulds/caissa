"""
bin/Code/Fritz/QssRules.py — Pure QSS rule checking for the Fritz layer.

Exposes three functions:

- ``scan_qss`` — detect Q1 and Q3 authoring violations in a ``.qss`` string.
- ``template_gaps`` — detect Q2 violations: keys in ``colors.template`` that are
  absent from a given ``.colors`` file.
- ``qproperties`` — parse every ``qproperty-<name>: <value>`` line from a ``.qss``
  string and return a ``{selector: {name: value}}`` mapping.

**No Qt imports.  No I/O.**  Callers are responsible for reading files.

The three QSS authoring rules (Q1/Q2/Q3):

- **Q1** — no ``#RRGGBB`` on a line with more than one colon.  Violation is a
  silent skip by both ``.qss`` pre-parsers; the colour cannot be themed.
- **Q2** — every key in ``colors.template`` must exist in the active ``.colors``
  file.  A missing key causes a ``KeyError`` crash in *Options → Colours*.
- **Q3** — selector on its own line, ``{`` on the **next** line.  A same-line ``{``
  corrupts the key derivation in the pre-parser (``"QWidget {|key"``), so the
  colour override silently never applies.

:spec: §4, §5.2 (feature_spec.md), N-FRITZ-4
"""

from __future__ import annotations

import re
from typing import NamedTuple

from Code.Fritz.Errors import QssContractError


# ---------------------------------------------------------------------------
# Q1 / Q3 violation scanning
# ---------------------------------------------------------------------------

class _Violation(NamedTuple):
    """A single Q1 or Q3 rule violation."""

    line_no: int
    rule: str
    line: str


_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}")


def scan_qss(text: str) -> list[tuple[int, str, str]]:
    """Return a list of Q1 and Q3 violations found in *text*.

    Each entry is ``(line_no, rule, line)`` where *line_no* is 1-based,
    *rule* is ``"Q1"`` or ``"Q3"``, and *line* is the stripped source line.

    :param text: Full contents of a ``.qss`` file.
    :return: List of ``(line_no, rule, line)`` tuples; empty when the file is clean.

    :spec: §5.2
    """
    violations: list[tuple[int, str, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("/*"):
            continue
        # Q3: selector and '{' on the same line (not a line that is only '{')
        if "{" in stripped and not stripped.startswith("{"):
            violations.append((i, "Q3", stripped))
            continue
        # Q1: a hex colour on a line that contains more than one colon
        if _HEX_RE.search(stripped) and stripped.count(":") > 1:
            violations.append((i, "Q1", stripped))
    return violations


# ---------------------------------------------------------------------------
# Q2 gap detection
# ---------------------------------------------------------------------------

def template_gaps(template_keys: list[str], colors_keys: list[str]) -> list[str]:
    """Return keys present in *template_keys* but absent from *colors_keys*.

    A non-empty result means the ``.colors`` file is missing template rows, which
    causes a ``KeyError`` crash in *Options → Colours* (Q2).

    :param template_keys: Keys parsed from ``colors.template`` (e.g. via
        ``[line.split("=")[0] for line in text.splitlines() if "=" in line]``).
    :param colors_keys: Keys parsed from the active ``.colors`` file in the same way.
    :return: Sorted list of missing keys; empty when the file is complete.

    :spec: §5.2
    """
    missing = sorted(set(template_keys) - set(colors_keys))
    return missing


# ---------------------------------------------------------------------------
# qproperty- contract parsing
# ---------------------------------------------------------------------------

# Matches a CSS property line like:  qproperty-litColor: #30ff70;
_QPROP_RE = re.compile(r"^qproperty-(\w+)\s*:\s*(.+?)\s*;?\s*$")


def qproperties(text: str) -> dict[str, dict[str, str]]:
    """Parse every ``qproperty-`` line in *text* and return a selector→property map.

    The return value is ``{selector: {property_name: value}}``.  Only lines that
    start with ``qproperty-`` inside a selector block are included.

    Raises ``QssContractError`` on unbalanced braces (a structural parse failure
    that would silently corrupt the contract).

    :param text: Full contents of a ``.qss`` file.
    :return: Nested dict; empty when no ``qproperty-`` lines are found.
    :raises QssContractError: When brace depth goes negative or file ends inside a block.

    :spec: §5.2
    """
    result: dict[str, dict[str, str]] = {}
    current_selector: str | None = None
    depth = 0

    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("/*"):
            continue

        opens = stripped.count("{")
        closes = stripped.count("}")

        # A line that is only '{' opens a block; the selector was the previous line.
        if stripped == "{":
            depth += 1
            continue

        # Closing brace(s)
        if "}" in stripped and not "{" in stripped:
            depth -= closes
            if depth < 0:
                raise QssContractError(
                    f"Unbalanced '}}' at line {i} — cannot parse qproperty- contract."
                )
            if depth == 0:
                current_selector = None
            continue

        # Selector candidate: no braces, depth == 0
        if depth == 0 and not stripped.startswith("qproperty-") and ":" not in stripped:
            current_selector = stripped
            continue

        # Opening brace on the same line as a selector (Q3 violation, but still parse)
        if "{" in stripped and depth == 0:
            depth += opens
            # Extract selector part before '{'
            current_selector = stripped.split("{")[0].strip() or current_selector
            continue

        # qproperty- line inside a block
        if depth > 0 and stripped.startswith("qproperty-"):
            m = _QPROP_RE.match(stripped)
            if m and current_selector:
                prop_name = m.group(1)
                value = m.group(2)
                result.setdefault(current_selector, {})[prop_name] = value

    if depth != 0:
        raise QssContractError(
            f"Unbalanced braces — file ends with depth {depth}. "
            "Cannot reliably parse qproperty- contract."
        )

    return result
