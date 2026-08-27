# Docstring Standards

## Purpose

This document defines docstring requirements for all new Python code added to the Caissa repository. It applies to Caissa-owned files (primarily `bin/Code/UIModes/` and new files under `bin/Code/Config/`, `bin/Code/Main/`). It does not require retrofitting the existing Lucas Chess R6 codebase.

---

## 1. Style

Use **RST/Sphinx-style** docstrings for all new modules, classes, and public functions.

```python
def get_active_mode():
    """
    Return the currently active mode configuration dictionary.

    :returns: The parsed JSON dict for the active mode, or an empty dict
              if no mode JSON is found.
    :rtype:   dict
    """
```

For functions that raise exceptions:

```python
def load_overlay(theme_name):
    """
    Load the UI overlay JSON for the given theme name.

    :param theme_name:    The theme stem (e.g. ``"Caissa"``).
    :returns:             Parsed overlay dict, or ``{}`` if no overlay exists.
    :raises ValueError:   If ``theme_name`` is empty.
    """
```

---

## 2. What Requires a Docstring

**Required** for all new code:
- Module-level docstring on every new `.py` file (one line is fine)
- All public functions and methods
- All class definitions

**Optional** (add only if the purpose is non-obvious):
- Private methods (`_name`)
- `__init__` methods when the class docstring already describes construction

---

## 3. Module-Level Docstrings

Every new module must have a one-line module docstring at the top:

```python
"""UI overlay loader for theme-driven dialog customisation."""
```

Multi-line is fine if the module is complex:

```python
"""
OverlayForm proxy that wraps TFormLayout to apply per-theme label
renames and field suppression from Resources/Styles/<name>.ui.json.
"""
```

---

## 4. Format Rules

- First line: short imperative sentence, no trailing period (matches PEP 257)
- Blank line after the summary before `:param:` / `:returns:` / `:raises:` fields
- Align `:param:` field descriptions for readability (optional but preferred)
- Use double backticks for inline code: `` ``session_id`` ``

---

## 5. What NOT to Write

- Do not document what the code obviously does — `"""Return x."""` for `return x` adds nothing
- Do not reference the task, PR, or issue number — those belong in git history
- Do not copy-paste boilerplate docstrings — every docstring must add real information

---

## References

- [PEP 257 — Docstring Conventions](https://peps.python.org/pep-0257/)
- [Sphinx autodoc — RST field lists](https://www.sphinx-doc.org/en/master/usage/domains/python.html)
- Original standard: `aib-genai-standards/coding/docstring-standards.md`
