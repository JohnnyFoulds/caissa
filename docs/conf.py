"""
docs/conf.py — Sphinx configuration for the Caissa RPA layer API reference.

Generates ``docs/rpa/api/`` from RST docstrings in ``bin/Code/Rpa/``.

Build with::

    make docs
    # or: python -m sphinx -W docs docs/rpa/api

:notes: The generated ``docs/rpa/api/`` tree is gitignored.  Commit the docstrings
        in the source files; the HTML is always regenerated from them.
"""

import os
import sys

# Make the Caissa package importable during Sphinx autodoc.
sys.path.insert(0, os.path.abspath("../bin"))

# ---------------------------------------------------------------------------
# Project information
# ---------------------------------------------------------------------------

project = "Caissa RPA Layer"
author = "Caissa contributors"
release = "0.1.0"

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",    # Google/NumPy-style docstrings in addition to RST
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

# ---------------------------------------------------------------------------
# Autodoc settings
# ---------------------------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": False,
    "show-inheritance": True,
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

templates_path = []
html_theme = "sphinx_rtd_theme"
html_static_path = []

# Treat all warnings as errors (matches ``make docs`` -W flag).
nitpicky = True
