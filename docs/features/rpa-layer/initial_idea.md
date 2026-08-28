# RPA Layer — Initial Idea

**Status:** FROZEN — scope locked 2026-08-28  
**Frozen by:** Johannes Foulds  
**Next artefact:** [feature_spec.md](feature_spec.md)

---

## Problem Statement

Caissa has `bin/Code/Debug/RemoteControl.py` — a Unix-socket command server embedded in the
Qt process with 25 verbs. It is effectively a hand-rolled RPA *driver*, but there is no
*engine*: no state model, no pre/postcondition contract, no retry, no compensation, no
workflow composition. Every automation is an unguarded fire-and-forget socket command.

Johannes spent time as an RPA developer using UiPath. The recurring problem there was that
UIs misbehave — timing, connectivity, updates, unexpected state. The mitigation was a
**closed loop with guard preconditions and compensating recovery**:

1. Before an action, check the app is in the expected state.
2. If not, drive the app to the expected state, then GOTO 1.
3. Perform the action.
4. Verify the action performed and the expected state holds; if not, decide whether to undo
   (compensate) or repair, to return to a known state.
5. Prepare for the next action, GOTO 1.

We want to formalise this into an RPA layer built above RemoteControl, using UiPath's
vocabulary for the user-facing Activity API so it is immediately legible to someone with that
background. Procedural, not agentic — no LLM reasoning. CV/OCR is a location and
verification tier, exactly as UiPath's `CV *` activities are.

---

## Business Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Provide a closed-loop automation layer above RemoteControl that encodes the 5-step guard pattern as first-class machinery. |
| BR-2 | Enable automated regression testing of Caissa UI behaviour, especially the Classical Invariant. |
| BR-3 | Enable reliable interactive driving of the app for dev/debug purposes (ad hoc activities, not only fixed workflows). |
| BR-4 | Use UiPath ontology for the user-facing API so the concepts are immediately recognisable. |

---

## Confirmed Decisions (at scope-lock)

| Decision | Choice |
| --- | --- |
| Placement | In-process — `bin/Code/Rpa/`; RemoteControl modified to serve it |
| Computer Vision | Full OpenCV + Tesseract in v1, including whole-screen baseline checks |
| Purpose | Both equally — pytest regression suite *and* interactive dev tooling |
| Ontology | Hybrid — UiPath names for Activities; plain domain names for engine internals |
| Workflow format | Python DSL only |
| `CaissaError` base | `bin/Code/Rpa/Errors.py` (first module to create it) |
| Phasing | Full phased plan; documentation phase first, no code before spec |

---

## Open Questions (to be resolved in feature_spec.md)

These are explicitly open at scope-lock; resolutions are recorded as `D-n` in
`docs/rpa/decisions.md` and in the spec.

| # | Question |
| --- | --- |
| D5 | i18n-sensitive selectors — how to handle `_dialog_button`'s English+Spanish hardcoding |
| D7 | CI (GitHub Actions) — whether to propose it at Phase 9 |
| D8 | Python floor — `requires-python = ">=3.12"` vs py313 in practice |

All other decisions were resolved before spec-writing began and are recorded in
`docs/rpa/decisions.md` as D1–D12.
