# Caissa Fritz Layer — Documentation

This directory contains the product documentation for the Fritz layer — the fixed-window, pane,
LCD clock, notation and ribbon system that makes Modern Fritz mode read as Fritz at a glance.

**If you've never used Fritz mode before:** start with `concepts.md`.

**If you want to theme or recolour Fritz:** start with `theming.md` *(Phase 6)*.

**If you're debugging a layout or sizing issue:** `troubleshooting.md` *(Phase 7)*.

---

## Which Document Do I Want?

| I want to… | Go to |
|---|---|
| Understand the fixed-window model and qproperty- contract | `concepts.md` |
| Author a new Fritz colour theme | `theming.md` *(Phase 6)* |
| Understand the ribbon content-map schema | `ribbon.md` *(Phase 7)* |
| See which design decisions were made and why | `decisions.md` |
| Look up a term used in the spec or code | `glossary.md` |
| See the approved mockup sign-off record | `design-approval.md` |
| Understand how Fritz visual assertions work | `testing.md` *(Phase 7)* |
| Diagnose a clock/eval/pane/ribbon symptom | `troubleshooting.md` *(Phase 7)* |
| Read the generated API reference | `api/` — run `make docs-fritz` to generate |

## Pages

```
docs/fritz/
├─ README.md              ← this file
├─ concepts.md            ← mental model: mode-gated overlay, qproperty- contract, fixed window
├─ glossary.md            ← term → definition → Fritz equivalent
├─ decisions.md           ← ADR log (D1–D11+)
├─ design-approval.md     ← dated sign-off checklist (filled at the design gate)
├─ qss-contract.md        ← E1-E4 contract + per-widget property tables (Phase 0)
├─ theming.md             ← authoring a Fritz .colors file; Q1/Q2/Q3 rules (Phase 6)
├─ ribbon.md              ← Resources/Ribbons/ schema; group assignment notes (Phase 7)
├─ testing.md             ← marker discipline; what the design harness is/isn't (Phase 7)
├─ troubleshooting.md     ← symptom → cause → fix table (Phase 7)
└─ api/                   ← generated Sphinx output (run make docs-fritz; not committed)
```

Pages marked *(Phase N)* are stubs until that phase ships.

## Design-Time vs Phase-Delivered Pages

**Design-time** (`concepts.md`, `glossary.md`, `decisions.md`, `design-approval.md`): written in
Phase D before any code. Their content is the output of the design process, not the implementation.

**Phase-delivered** (`qss-contract.md`, `theming.md`, `ribbon.md`, `testing.md`,
`troubleshooting.md`): written as part of the phase that produces the feature they document. Each
phase's `feature_steps.md` block lists its Gate H pages explicitly.

## The SDD Process

This feature was designed following `docs/process/sdd-workflow.md`. The artefacts are at
`docs/features/fritz-polish/` until the feature is complete, then archived to
`docs/features/_archive/fritz-polish/`.
