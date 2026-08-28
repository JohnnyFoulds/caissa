# Error Handling Standard

## Purpose

This document defines how errors should be raised, caught, and logged in new Caissa code. It adapts the AIBooster+ error handling standard for a desktop PySide6 application (no HTTP layer, no FastAPI).

---

## 1. Exception Hierarchy

### 1.1 Caissa-Specific Exceptions (and where they live)

New Caissa code that can fail in structured ways should define specific exception classes
rather than raising raw `RuntimeError` or `Exception`. Keep hierarchies shallow — a base
class plus one level of specific exceptions is enough.

**Module location:** `CaissaError` lives in `bin/Code/Rpa/Errors.py` — the first Caissa
module that needed it. This file also hosts `RpaError` and the 15 RPA-specific exceptions.
Domain-specific code in other Caissa areas may define their own base that inherits
`CaissaError`, keeping `RpaError` as the pattern to follow.

```python
# bin/Code/Rpa/Errors.py
class CaissaError(Exception):
    """Base class for all errors raised by Caissa-specific code."""

class RpaError(CaissaError):
    """Base class for all errors raised by the RPA layer."""

class ModeLoadError(CaissaError):
    """Raised when a mode JSON file cannot be parsed or loaded."""

class OverlayLoadError(CaissaError):
    """Raised when a theme overlay JSON file is malformed."""
```

The hierarchy is: `CaissaError` (repo-wide root) → domain base (`RpaError`, etc.) → specific
exceptions. This is "base + one level" within each domain, with `CaissaError` as the
cross-domain root the catch-all `except CaissaError` can use.

### 1.2 When to Use Built-in Exceptions

Use `ValueError` for true argument validation (empty string where one is required, wrong type). Use `FileNotFoundError` when a required resource file is missing and the caller needs to distinguish it.

---

## 2. Raising Errors

Every raised exception must include a message identifying:
- What failed
- Which value or resource was involved (include names, paths, keys)
- Why it failed if not obvious from the type

```python
# Good
raise ModeLoadError(f"Mode JSON not found: Resources/Modes/{mode_name}.json")

# Bad — caller can't identify the problem
raise ModeLoadError("Mode not found")
```

Use `raise ... from exc` when wrapping a lower-level exception:

```python
try:
    with open(path) as f:
        data = json.load(f)
except json.JSONDecodeError as exc:
    raise OverlayLoadError(f"Malformed overlay JSON: {path}") from exc
```

---

## 3. Catching Errors

### 3.1 Catch the Most Specific Type

Always catch the most specific exception type available. Never use `except BaseException` — it swallows `KeyboardInterrupt` and `SystemExit`, which must propagate.

### 3.2 Never Swallow Errors Silently

Do not catch exceptions and do nothing. The minimum at any catch site is a log at `ERROR` level. If a failure is intentionally non-critical (e.g. a missing optional overlay file), document why:

```python
try:
    overlay = load_overlay(theme_name)
except OverlayLoadError:
    # Non-critical: overlay is optional; fall back to base form labels.
    logging.getLogger(__name__).error(
        "Failed to load overlay for theme %s", theme_name, exc_info=True
    )
    overlay = {}
```

### 3.3 Lucas Chess R6 Error Patterns

When modifying existing Lucas Chess R6 code, follow the error handling style already present in the file. Do not introduce Caissa exception classes into base-game files.

---

## 4. Logging at Catch Sites

Every `logger.error()` at an exception catch site must include `exc_info=True` to capture the traceback:

```python
logger.error("Failed to load mode JSON for %s", mode_name, exc_info=True)
```

---

## References

- [Python Built-in Exceptions](https://docs.python.org/3/library/exceptions.html)
- [PEP 3134 — Exception Chaining](https://peps.python.org/pep-3134/)
- Original standard: `aib-genai-standards/coding/error-handling.md`
