"""
bin/Code/Fritz/ClockModel.py — Pure clock parsing and formatting.

Accepts every clock-string form the app produces:

* ``MM:SS``           — ``"05:00"``
* ``H:MM:SS``         — ``"1:30:00"``
* HTML two-line form  — ``"05:00<br><FONT SIZE=\\"-4\\">0.0"``

:spec: §5.3 (ClockModel), FR-29
"""

from __future__ import annotations

import re

# Matches the first ``H:MM:SS`` or ``MM:SS`` token in a string
# (handles embedded HTML tags as produced by ``WBase.set_clock_*``).
_TIME_RE = re.compile(r"(\d+:\d{2}(?::\d{2})?)")

# Show tenths only when time is below this threshold (seconds).
_TENTHS_THRESHOLD: float = 20.0


def parse(text: str) -> float | None:
    """Parse a clock string into seconds.

    :param text: Any of ``MM:SS``, ``H:MM:SS``, or the HTML two-line form.
    :returns: Seconds as a non-negative float, or ``None`` if parsing fails.
    :spec: FR-29
    """
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    parts = m.group(1).split(":")
    try:
        if len(parts) == 2:
            return float(int(parts[0]) * 60 + int(parts[1]))
        if len(parts) == 3:
            return float(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
    except ValueError:
        return None
    return None


def format(seconds: float, show_tenths: bool = False) -> str:  # noqa: A001
    """Format seconds as a clock string.

    :param seconds:    Time in seconds; clamped to 0 if negative.
    :param show_tenths: When ``True`` and ``seconds < 20``, append ``.d``.
    :returns: Formatted string such as ``"05:00"`` or ``"00:19.3"``.
    :spec: FR-29
    """
    s = max(0.0, seconds)
    total = int(s)
    h = total // 3600
    m = (total % 3600) // 60
    sec = total % 60
    base = f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
    if show_tenths and s < _TENTHS_THRESHOLD:
        tenths = int((s - total) * 10)
        return f"{base}.{tenths}"
    return base


def digits(seconds: float) -> str:
    """Return the digit string painted by ``WFritzLCD``.

    Always ``MM:SS`` (minutes can exceed 59 for long time-controls).

    :param seconds: Time in seconds.
    :returns: Display string such as ``"05:00"``.
    :spec: FR-29
    """
    s = max(0.0, seconds)
    total = int(s)
    m = total // 60
    sec = total % 60
    return f"{m:02d}:{sec:02d}"
