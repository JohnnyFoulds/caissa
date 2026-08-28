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

- `main` — stable, protected; never commit directly to `main`
- All work happens on short-lived branches off `main`: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, `chore/<topic>`
- Merge to `main` only via a Pull Request on `JohnnyFoulds/caissa`

**Workflow:**
1. `git checkout -b feat/<topic>` from latest `main`
2. One or more commits on the branch
3. `gh pr create` with summary and test plan
4. Merge immediately (see note below)
5. `git checkout main && git pull && git branch -d feat/<topic>`

**Auto-merge policy (current):** When a feature is complete and work is moving to the next task,
Claude Code merges the PR automatically without waiting for manual review.
Note: GitHub does not allow self-approval, so skip the approve step:
```bash
gh pr merge --repo JohnnyFoulds/caissa <PR-number> --squash --delete-branch
git checkout main && git pull
```
This policy is temporary. It will be changed to require manual review once the codebase stabilises.

**IMPORTANT:** Never push to `lukasmonk/lucaschessR6`. All pushes go to `JohnnyFoulds/caissa` only.

---

## 3. Code Style

### 3.1 Existing Code Conventions

The Lucas Chess R6 codebase has its own conventions. When modifying existing files, follow the style of the file being edited. Do not reformat code that is not being changed.

### 3.2 New Code (Caissa additions)

For new files added under `bin/Code/UIModes/`, `bin/Code/Rpa/`, and other Caissa-owned directories:

- Python 3.13 features are acceptable in new code
- PySide6 patterns match the existing codebase (`QDialog`, `QWidget`, `TFormLayout`, etc.)
- Do not introduce ABCs (abstract base classes) or `typing.Protocol` — the codebase doesn't
  use them and the desktop app doesn't need the protocol enforcement they provide.
  `typing.Protocol` is built on `ABCMeta`, so this prohibition covers both.
  Use plain base classes raising `NotImplementedError` instead — matching the pattern
  established by `bin/Code/ManagerBase/Manager.py:61` (plain class, ~35 subclasses).

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

New Python files added to the Caissa codebase use `ruff` for linting where applicable. Target
Python version: 3.13.

The effective lint configuration lives in `ruff.toml` at the repository root, scoped by
`include` to Caissa paths only (so the Lucas Chess R6 base is never linted):

```toml
# ruff.toml — scoped to Caissa-owned paths
include = ["bin/Code/Rpa/**", "bin/Code/Main/LogSetup.py", "tests/unit/rpa/**", "tools/caissa-rpa"]
target-version = "py313"

[lint]
select = ["E", "W", "F", "I", "UP"]
# E722 is NOT suppressed here — new code must not use bare except:
```

**`make lint` passes `--config ruff.toml` explicitly.** Ruff resolves config by walking up
from each file, so without `--config`, Caissa files find `bin/pyproject.toml` first and
inherit its `lint.ignore = ["E722"]` with no `select` — the new config would appear installed
while doing nothing. `test_ruff_config_enforces_e722` asserts this cannot silently regress.

The `bin/pyproject.toml` is left unchanged to avoid reformatting the upstream codebase.

---

## References

- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- Original standard: `aib-genai-standards/coding/coding-standards.md`
