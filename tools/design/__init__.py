"""
tools/design — Fritz visual design harness.

Renders Fritz UI scenes offscreen using PySide6 + the real .qss files,
pairs each with a Fritz 18 reference crop, and builds a side-by-side
HTML review sheet for design approval.

Usage
─────
    # Render all scenes (outputs to CAISSA_DESIGN_OUT or /tmp/caissa-design/)
    QT_QPA_PLATFORM=offscreen python3 tools/design/fritz_mock.py --scene all

    # Build the review sheet (opens in browser)
    QT_QPA_PLATFORM=offscreen python3 tools/design/review.py --scene all

    # Review against the running app instead of a static mockup
    python3 tools/design/review.py --scene all --live

Environment variables
─────────────────────
CAISSA_DESIGN_OUT   Directory for rendered PNGs.  Default: <tempdir>/caissa-design/
CAISSA_FRITZ_REF    Directory containing Fritz 18/19 reference screenshots.
                    Default: ~/Pictures/fritz-reference/
"""
import os
import tempfile
from pathlib import Path

#: Output directory for rendered mockup PNGs.
DESIGN_OUT = Path(os.environ.get("CAISSA_DESIGN_OUT",
                                  Path(tempfile.gettempdir()) / "caissa-design"))

#: Fritz 18/19 reference screenshot directory (kept outside the repo — copyright).
FRITZ_REF = Path(os.environ.get("CAISSA_FRITZ_REF",
                                 Path.home() / "Pictures" / "fritz-reference"))

# Scene names in the order they appear in the review sheet.
SCENES = [
    "pane_titlebar",
    "clocks",
    "eval_line",
    "nag_row",
    "notation_tabs",
    "ribbon_home",
    "full",
]

# Map: scene name → best reference filename inside FRITZ_REF.
# If a file does not exist, the reference column is left blank in review.html.
SCENE_REF = {
    "pane_titlebar":  "pane_titlebar.png",
    "clocks":         "game_clock_02.png",
    "eval_line":      "eval_beside_moves.png",
    "nag_row":        "nag_1tacticalanalysis6.png",
    "notation_tabs":  "notation_tabs_01.png",
    "ribbon_home":    "ribbon_home.png",
    "full":           "fritz_152f18engshot.png",
}
