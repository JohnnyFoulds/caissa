# Coding Standards

## Purpose

This document defines coding conventions, commit message format, and branching strategy for the Caissa repository (a fork of Lucas Chess R6). It adapts the AIBooster+ GenAI coding standards for a desktop PySide6 application built on an existing codebase with its own conventions.

---

## 1. Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `type(scope): subject`

Standard types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`

Common scopes: `modes`, `toolbar`, `config`, `coach`, `ui`, `engine`, `theme`

Non-trivial commits must include a body — a blank line after the subject, followed by bullet points:

```text
feat(modes): add TB_OPTIONS to all focused mode toolbars

- Add TB_OPTIONS to analyse.json, train.json, compete.json, just-play.json
- Allows users to reach Configuration dialog (and switch modes) from any mode
- Coach already had TB_OPTIONS; this makes all modes consistent
```

- One bullet per logical change; present-tense imperative ("Add", "Remove", "Fix", "Update")
- Omit the body only for genuinely single-action commits (e.g. fixing a typo)

---

## 2. Branching Strategy

- `main` — stable branch; source of truth for the JohnnyFoulds/caissa fork
- Short-lived branches off `main`: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, `chore/<topic>`

**IMPORTANT:** Never push to `lukasmonk/lucaschessR6`. All pushes go to `JohnnyFoulds/caissa` only.

---

## 3. Code Style

### 3.1 Existing Code Conventions

The Lucas Chess R6 codebase has its own conventions. When modifying existing files, follow the style of the file being edited. Do not reformat code that is not being changed.

### 3.2 New Code (Caissa additions)

For new files added under `bin/Code/UIModes/` and other Caissa-owned directories:

- Python 3.13 features are acceptable in new code
- PySide6 patterns match the existing codebase (`QDialog`, `QWidget`, `TFormLayout`, etc.)
- Do not introduce ABCs (abstract base classes) — the codebase doesn't use them and the desktop app doesn't need the protocol enforcement they provide

### 3.3 Section Dividers

Never use banner-style section dividers in Python (no `####...####` comment blocks). Use `#region` / `#endregion` instead:

```python
#region Section Name
# code here
#endregion
```

### 3.4 Comments

Default to writing no comments. Only add one when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific external behaviour. Do not write comments that describe what the code does (well-named identifiers do that).

---

## 4. Pull Request Requirements

- Keep PRs small and focused on a single purpose
- Every PR description must include:
  - Summary of the change and its intent
  - What was tested and the outcome

---

## 5. Tool Configuration

New Python files added to the Caissa codebase use `ruff` for linting where applicable. Target Python version: 3.13.

For linting Caissa-specific code only (not the Lucas Chess R6 base):
```toml
[tool.ruff]
src = ["bin/Code/UIModes"]
target-version = "py313"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP"]
```

---

## References

- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- Original standard: `aib-genai-standards/coding/coding-standards.md`
