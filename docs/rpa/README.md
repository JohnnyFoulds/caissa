# Caissa RPA Layer — Documentation

This directory contains the product documentation for the Caissa RPA layer — the closed-loop
automation engine built above `RemoteControl`.

**If you've never used the RPA layer before:** start with `quickstart.md` (available after Phase 6).

**If you want to understand how it works:** start with `concepts.md`.

**If you're debugging a failed run:** `troubleshooting.md` (available after Phase 9).

---

## Which Document Do I Want?

| I want to… | Go to |
|---|---|
| Run my first workflow in 5 minutes | `quickstart.md` *(Phase 6)* |
| Understand the core concepts | `concepts.md` |
| See how this maps to UiPath | `uipath-mapping.md` |
| Understand the 5-step closed loop | `concepts.md` → `state-machine.md` |
| Write a workflow | `authoring-workflows.md` *(Phase 8)* |
| Find the right selector for an element | `selectors.md` *(Phase 3)* |
| Look up an activity | `activities.md` *(Phase 5)* |
| Understand the 8 app states | `states.md` |
| Understand the runner sub-states | `state-machine.md` |
| Use CV/OCR | `vision.md` *(Phase 7)* |
| Understand the wire protocol (`rpa_*` verbs) | `wire-protocol.md` *(Phase 6)* |
| Use the CLI (`tools/caissa-rpa`) | `cli.md` *(Phase 6)* |
| Use the RPA layer for testing | `testing.md` *(Phase 8)* |
| Diagnose a failed run | `troubleshooting.md` *(Phase 9)* |
| Find a term | `glossary.md` |
| See architecture decisions | `decisions.md` |
| Add an activity or state | `extending.md` *(Phase 9)* |
| Read journals and diagnose old runs | `operations.md` *(Phase 9)* |
| Read the generated API reference | `api/` — run `make docs` to generate |

---

## Pages

```
docs/rpa/
├─ README.md              ← this file
├─ concepts.md            ← mental model; start here
├─ quickstart.md          ← install + first workflow (Phase 6)
├─ user-guide.md          ← task-oriented guide (Phase 9)
├─ state-machine.md       ← formal runner spec
├─ states.md              ← the 8 app states
├─ uipath-mapping.md      ← ontology mapping
├─ selectors.md           ← targeting reference (Phase 3)
├─ activities.md          ← activity catalogue (Phase 5)
├─ authoring-workflows.md ← writing workflows (Phase 8)
├─ vision.md              ← CV/OCR guide (Phase 7)
├─ wire-protocol.md       ← rpa_* verb reference (Phase 6)
├─ cli.md                 ← tools/caissa-rpa reference (Phase 6)
├─ testing.md             ← using RPA as a test harness (Phase 8)
├─ troubleshooting.md     ← symptom → cause → fix (Phase 9)
├─ extending.md           ← adding activities/states/drivers (Phase 9)
├─ operations.md          ← journals, retention, diagnosis (Phase 9)
├─ glossary.md            ← terms + UiPath synonyms
├─ decisions.md           ← ADR log (D1–D12+)
└─ api/                   ← generated Sphinx autodoc (run make docs; gitignored)
```

Pages marked *(Phase N)* are stubs until that phase ships.

---

## Design-Time vs Phase-Delivered Pages

Pages in this directory fall into two categories:

**Design-time** (shipped in Phase 0 because they are design output, not implementation output):
`concepts.md`, `state-machine.md`, `states.md`, `uipath-mapping.md`, `glossary.md`,
`decisions.md`, this `README.md`.

**Phase-delivered** (written alongside the code that implements them, per Gate H):
all others. A page written before its code is verified will describe an imagined system.
`quickstart.md` must be executed verbatim as its own acceptance test, which is why it lands
at Phase 6 (the first point where an end-to-end run is actually possible).

---

## The SDD Process

The RPA layer was built using Specification-Driven Development. The process artefacts live in
`docs/features/rpa-layer/` (active) or `docs/features/_archive/rpa-layer/` (after completion).
The process itself is documented in `docs/process/sdd-workflow.md`.
