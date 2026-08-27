# Specification-Driven Development Standard

## Purpose

This document defines the specification-driven development (SDD) approach for Caissa. It adapts the AIBooster+ SDD standard for a desktop chess application built on an existing codebase, with particular emphasis on AI-assisted development using Claude Code.

---

## 1. Core Principle

The **specification** is the primary engineering artefact. Code is derived from it, not the reverse.

An implementation is acceptable only when it fully conforms to its specification. When spec and code conflict, the spec governs — either the code is wrong, or the spec must be updated via a deliberate decision.

---

## 2. Why Specification-Driven Development

### 2.1 The Cost of Skipping Specs

A vague prompt fed to a coding agent no longer produces a partial implementation — it produces an entire system built faithfully against the wrong contract, at AI speed. The cost-of-change curve now bends at the specification, not the implementation:

- Code costs near zero to regenerate. A wrong implementation can be replaced in minutes.
- A wrong specification, fed to an AI agent, propagates incorrectness across a codebase at generation speed.

### 2.2 Failure Modes Without a Spec

Ad hoc development produces:
- Ambiguity about intended behaviour
- Scope creep (boundaries never stated)
- Tests that verify implementation detail rather than specified behaviour
- Inconsistency across sessions (each prompt reconstructs assumptions from scratch)

For Caissa specifically: the existing Lucas Chess R6 codebase is large and underdocumented. Without a spec, Caissa additions risk producing code that looks right but conflicts with base-game invariants in subtle ways.

---

## 3. Specification Structure

Every non-trivial Caissa feature MUST include a spec before implementation begins. The spec MUST include:

| Component | Description |
| --- | --- |
| **R** — Functional requirements | What the feature does; observable behaviours it must exhibit |
| **I** — Interface | Entry points, function signatures, config keys, JSON schemas |
| **P** — Preconditions | What must be true before the feature activates |
| **Q** — Postconditions / invariants | What must be true after the feature runs |
| **N** — Non-functional constraints | Startup cost, memory, classical invariant compliance |

Use RFC 2119 vocabulary: **MUST** (mandatory), **SHOULD** (recommended), **MAY** (optional).

### 3.1 The Classical Invariant as a Non-Functional Constraint

Every Caissa feature spec MUST state how it preserves the classical invariant:

> `classical` mode + no theme overlay = upstream Lucas Chess R6 exactly.

If a feature cannot preserve this invariant, it requires explicit justification and approval.

---

## 4. Development Pipeline

```
Problem Statement
      ↓
Normative Specification   (R, I, P, Q, N)
      ↓
Schemas / Contracts       (JSON schemas, config keys, function signatures)
      ↓
Test Oracles              (unit tests, integration tests)
      ↓
Implementation
```

**Rules:**
- Implementation MUST NOT begin before the specification is written and reviewed
- Changes to behaviour MUST be reflected in the specification before the code is updated
- If implementation reveals the spec is wrong: stop, update the spec, then resume

---

## 5. Specification Artefacts and Location

| Artefact | Location |
| --- | --- |
| Feature specification (SDD) | `docs/<feature-name>.md` |
| Mode JSON schema | `Resources/Modes/<name>.json` |
| Theme overlay schema | `Resources/Styles/<name>.ui.json` |
| Standards documents | `docs/standards/` |

An existing example: `docs/theme-mode-system.md` — the SDD for the Theme/Mode overlay system.

---

## 6. Specifications for AI-Assisted Development

When using Claude Code to implement a feature:

1. **Spec before prompt** — the spec MUST exist as a written artefact before implementation is requested
2. **Spec as context** — include the relevant spec sections in the Claude Code session when beginning implementation
3. **Validate after generation** — verify the implementation conforms to the spec before accepting it:
   - Interface conformance (function signatures match spec)
   - Precondition enforcement
   - Postcondition satisfaction
   - Classical invariant preserved
4. **Exploratory work** — if the full spec can't be known in advance, explore first, then extract a spec from the working result, then implement cleanly against the spec. Exploratory code is throwaway.

---

## 7. Spec Completeness Checklist

Before implementation begins:

- [ ] Functional requirements stated in MUST/SHOULD/MAY language
- [ ] Interface defined (config keys, function signatures, JSON schemas)
- [ ] Preconditions enumerated
- [ ] Postconditions and invariants enumerated
- [ ] Classical invariant impact stated
- [ ] Non-functional constraints stated (startup cost, memory, UI responsiveness)

---

## References

- `docs/theme-mode-system.md` — example SDD for the Theme/Mode overlay system
- [RFC 2119 — Requirement Level Keywords](https://www.rfc-editor.org/rfc/rfc2119)
- Original standard: `aib-genai-standards/process/spec-driven-development.md`
