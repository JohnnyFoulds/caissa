# Logging Standard

## Purpose

This document defines logging requirements for all new Caissa code. It adapts the AIBooster+ logging standard for a desktop PySide6 application (no OpenTelemetry, no structured log backend).

---

## 1. Log Levels

Use standard Python `logging` levels:

| Level | When to Use |
| --- | --- |
| `ERROR` | Unexpected failures, unhandled exceptions, file I/O failures |
| `WARNING` | Expected-but-notable conditions: fallback paths, missing optional resources |
| `INFO` | Lifecycle events, mode switches, configuration changes |
| `DEBUG` | Internal state, intermediate values, verbose diagnostic output |

Rules:
- `ERROR` must always be used at exception catch sites (with `exc_info=True`)
- Do not use `INFO` for high-frequency per-move or per-frame events — use `DEBUG`
- Do not use `WARNING` for errors that require action — use `ERROR`

---

## 2. Logger Naming

Use `logging.getLogger(__name__)` at module level. Do not create named loggers with hard-coded strings:

```python
import logging

logger = logging.getLogger(__name__)
```

---

## 3. Message Format

### 3.1 Include Relevant Context

Include the relevant resource names or identifiers in the log message:

```python
# Good
logger.info("Activated mode %s", mode_name)

# Bad — no context
logger.info("Mode activated")
```

### 3.2 Use `%s` Formatting, Not f-strings

Use `%`-style lazy formatting. The logging module skips string interpolation when the message won't be emitted; f-strings always evaluate:

```python
# Good
logger.debug("Processing toolbar action %s for mode %s", action_key, mode_name)

# Bad
logger.debug(f"Processing toolbar action {action_key} for mode {mode_name}")
```

### 3.3 `exc_info=True` at ERROR Level

Every `logger.error()` at a catch site must include `exc_info=True`:

```python
try:
    data = json.load(f)
except json.JSONDecodeError:
    logger.error("Malformed mode JSON: %s", path, exc_info=True)
```

---

## 4. Library vs Application Code

New Caissa modules that act as libraries (e.g. `UIModes.py`, `FormOverlay.py`) must never configure logging. Configuration belongs to the application entry point only.

---

## References

- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- Original standard: `aib-genai-standards/logging/logging-standard.md`
