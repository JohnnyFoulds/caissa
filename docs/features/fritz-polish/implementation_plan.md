# Fritz Polish — Implementation Plan

**Spec reference:** [feature_spec.md](feature_spec.md)
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## Current State (as of 2026-08-28)

| What exists | Status |
|---|---|
| `docs/features/fritz-polish/feature_spec.md` | Written — Gate A candidate |
| `docs/features/fritz-polish/initial_idea.md` | Written — FROZEN |
| `docs/features/fritz-polish/feature_steps.md` | Written — all test names declared |
| `docs/features/fritz-polish/implementation_plan.md` | This file — Phase D in progress |
| `bin/Code/Fritz/` | Does not exist yet |
| `docs/fritz/` | Does not exist yet |
| `docs/standards/ui-design-process.md` | Does not exist yet |
| `docs/standards/architecture.md` | Does not exist yet |

One branch = one phase = one PR. **Never commit directly to `main`.**
Work begins at **Session D-B** (the design-time `docs/fritz/` pages and standards).
Session D-A was the four SDD artefacts; those are now written.

---

## How to use this plan

1. Read the session block.
2. Write the tests first (TDD red).
3. Implement until green.
4. **Human diff review (Gate C)** — read every changed line before committing. Check: no accidental reformat of upstream R6, `#region` not banner comments, RST docstrings on public and non-public members, no disallowed imports for the module's purity tier, `exc_info=True` at every catch site.
5. Commit with the suggested message. Update `CHANGELOG.md` in the same commit.
6. Open PR to `JohnnyFoulds/caissa`. Never to `lukasmonk/lucaschessR6`.
7. Mark phase ✅ in `feature_steps.md` when the PR merges.
8. More work in this phase? GOTO 1. Else open PR.

---

## Files to Create / Modify

| File | Action |
| --- | --- |
| `docs/features/fritz-polish/initial_idea.md` | **Create** — Phase D (done) |
| `docs/features/fritz-polish/feature_spec.md` | **Create** — Phase D (done) |
| `docs/features/fritz-polish/feature_steps.md` | **Create** — Phase D (done) |
| `docs/features/fritz-polish/implementation_plan.md` | **Create** — Phase D (this file) |
| `docs/fritz/README.md` | **Create** — Phase D |
| `docs/fritz/concepts.md` | **Create** — Phase D |
| `docs/fritz/glossary.md` | **Create** — Phase D |
| `docs/fritz/decisions.md` | **Create** — Phase D |
| `docs/fritz/design-approval.md` | **Create** — Phase D (stub); **Edit** — design gate |
| `docs/fritz/qss-contract.md` | **Create** — Phase 0; **Edit** — Phases 1, 3, 4 |
| `docs/fritz/theming.md` | **Create** — Phase 6 |
| `docs/fritz/ribbon.md` | **Create** — Phase 7 |
| `docs/fritz/testing.md` | **Create** — Phase 7 |
| `docs/fritz/troubleshooting.md` | **Create** — Phase 7 |
| `docs/standards/ui-design-process.md` | **Create** — Phase D |
| `docs/standards/architecture.md` | **Create** — Phase D |
| `docs/modern-fritz.md` | **Supersede** — Phase D (`git mv` content into `docs/fritz/`) |
| `CLAUDE.md` | **Edit** — Phase D |
| `CHANGELOG.md` | **Edit** — Phase D |
| `bin/Code/Fritz/__init__.py` | **Create** — Phase 0 |
| `bin/Code/Fritz/Types.py` | **Create** — Phase 0 |
| `bin/Code/Fritz/Errors.py` | **Create** — Phase 0 |
| `bin/Code/Fritz/QssRules.py` | **Create** — Phase 0 |
| `bin/Code/Fritz/ModeGateway.py` | **Create** — Phase 0 |
| `bin/Code/Fritz/ThemeGateway.py` | **Create** — Phase 1 |
| `bin/Code/Fritz/ConfigGateway.py` | **Create** — Phase 1 |
| `bin/Code/Fritz/BoardFit.py` | **Create** — Phase 2 |
| `bin/Code/Fritz/GeometryStore.py` | **Create** — Phase 2 |
| `bin/Code/Fritz/PaneRegistry.py` | **Create** — Phase 3 |
| `bin/Code/Fritz/WFritzPane.py` | **Create** — Phase 3 |
| `bin/Code/Fritz/ClockModel.py` | **Create** — Phase 4 |
| `bin/Code/Fritz/EvalModel.py` | **Create** — Phase 4 |
| `bin/Code/Fritz/EngineGateway.py` | **Create** — Phase 4 |
| `bin/Code/Fritz/WFritzLCD.py` | **Create** — Phase 4 |
| `bin/Code/Fritz/NotationRowModel.py` | **Create** — Phase 5 |
| `bin/Code/Fritz/Delegates.py` | **Create** — Phase 5 |
| `bin/Code/Fritz/RibbonModel.py` | **Create** — Phase 7 |
| `bin/Code/Fritz/Ribbon.py` | **Create** — Phase 7 |
| `bin/Code/Fritz/WRibbon.py` | **Create** — Phase 7 |
| `bin/Code/UIModes/UIModes.py` | **Edit** — Phase 0 (delegate to ModeGateway); Phase 6 (optional `"hook"` key) |
| `bin/Code/UIModes/WFritzPlayerHeader.py` | **Edit** — Phase 1 |
| `bin/Code/UIModes/WFritzHome.py` | **Edit** — Phase 1 |
| `bin/Code/UIModes/WFritzEvalGraph.py` | **Edit** — Phase 1 |
| `bin/Code/UIModes/WFritzAnalysisTable.py` | **Edit** — Phase 1 |
| `bin/Code/UIModes/WFritzNewGame.py` | **Edit** — Phase 1 |
| `bin/Code/UIModes/actions/modern_fritz_ui.py` | **Edit** — Phases 2, 3, 4, 5, 7 |
| `bin/Code/Main/MainWindow.py` | **Edit** — Phase 2 |
| `bin/Code/Main/WBase.py` | **Edit** — Phase 2 (`:291`); Phase 7 (ribbon edits) |
| `bin/Code/Main/WInformation.py` | **Edit** — Phase 2 |
| `bin/Code/ManagerBase/ManagerResistance.py` | **Edit** — Phase 2 |
| `bin/Code/QT/LCDialog.py` | **Edit** — Phase 2 |
| `bin/Code/Board/Board.py` | **Edit** — Phase 2 |
| `bin/Code/Rpa/Driver.py` | **Edit** — Phases 2, 7 |
| `bin/Code/Debug/RemoteControl.py` | **Edit** — Phases 2, 7 |
| `bin/Code/Main/InitApp.py` | **Edit** — Phase 0 (§0.2b, optional) |
| `bin/Code/QT/WColors.py` | **Edit** — Phase 0 (§0.2b, optional) |
| `Resources/Modes/modern-fritz.json` | **Edit** — Phase 2 (layout block); Phase 7 (ribbon key) |
| `Resources/Modes/modern-fritz-dark.json` | **Create** — Phase 6 |
| `Resources/Styles/Modern Fritz.qss` | **Edit** — Phases 1, 3, 7 |
| `Resources/Styles/Modern Fritz.colors` | **Edit** — Phase 1 (NAG keys) |
| `Resources/Styles/colors.template` | **Edit** — Phase 1 (NAG keys) |
| `Resources/Styles/*.colors` (all 9 others) | **Edit** — Phase 1 (NAG keys) |
| `Resources/Styles/Fritz.qss` | **Create** — Phase 6; **Edit** — Phase 7 (ribbon blocks) |
| `Resources/Styles/Fritz.colors` | **Create** — Phase 6 |
| `Resources/Ribbons/modern-fritz.json` | **Create** — Phase 7 |
| `tests/unit/fritz/__init__.py` | **Create** — Phase 0 |
| `tests/unit/fritz/test_completeness.py` | **Create** — Phase 0 |
| `tests/unit/fritz/test_qss_rules.py` | **Create** — Phase 0 |
| `tests/unit/fritz/test_qss_parser_snapshot.py` | **Create** — Phase 0 |
| `tests/unit/fritz/test_mode_gateway.py` | **Create** — Phase 0 |
| `tests/test_qproperty_contract.py` | **Create** — Phase 0 |
| `tests/unit/fritz/test_theme_gateway.py` | **Create** — Phase 1 |
| `tests/unit/fritz/test_config_gateway.py` | **Create** — Phase 1 |
| `tests/test_fritz_qproperties.py` | **Create** — Phase 1 |
| `tests/unit/fritz/test_board_fit.py` | **Create** — Phase 2 |
| `tests/unit/fritz/test_geometry_store.py` | **Create** — Phase 2 |
| `tests/ui/test_fixed_window.py` | **Create** — Phase 2 |
| `tests/unit/fritz/test_pane_registry.py` | **Create** — Phase 3 |
| `tests/ui/test_fritz_panes.py` | **Create** — Phase 3 |
| `tests/unit/fritz/test_clock_model.py` | **Create** — Phase 4 |
| `tests/unit/fritz/test_eval_model.py` | **Create** — Phase 4 |
| `tests/ui/test_fritz_clocks.py` | **Create** — Phase 4 |
| `tests/unit/fritz/test_notation_row_model.py` | **Create** — Phase 5 |
| `tests/ui/test_fritz_notation.py` | **Create** — Phase 5 |
| `tests/test_fritz_light_theme.py` | **Create** — Phase 6 |
| `tests/test_ribbon_map.py` | **Create** — Phase 7 |
| `tests/ui/test_fritz_ribbon.py` | **Create** — Phase 7 |
| `tests/ui/rc_contract.json` | **Edit** — Phases 2, 7 |
| `tests/test_sidebar_icon_consistency.py` | **Edit** — Phase 0 (import from `tools/design/compare.py`) |
| `tools/design/__init__.py` | **Create** — Phase 0 |
| `tools/design/fritz_mock.py` | **Create** — Phase 0 |
| `tools/design/compare.py` | **Create** — Phase 0 |
| `tools/design/review.py` | **Create** — Phase 0 |
| `tools/design/README.md` | **Create** — Phase 0 |
| `ruff.toml` | **Edit** — Phase 0 |
| `.coveragerc` / `fritz.coveragerc` | **Edit/Create** — Phase 0 |
| `Makefile` | **Edit** — Phase 0 |
| `docs/conf.py` | **Edit** — Phase 0 |
| `.gitignore` | **Edit** — Phase 0 |
| `docs/features/fritz-polish/production_readiness.md` | **Create** — Phase 9 |

---

## Phase D — Documentation & Process

### Session D-A — SDD artefacts

**Files to create/edit:**

- `docs/features/fritz-polish/initial_idea.md` (create — FROZEN)
- `docs/features/fritz-polish/feature_spec.md` (create — Gate A)
- `docs/features/fritz-polish/feature_steps.md` (create — all test names declared)
- `docs/features/fritz-polish/implementation_plan.md` (create — this file)

**Scope:**

The four Gate A artefacts. `initial_idea.md` is frozen at scope-lock; `feature_spec.md` is the
living specification; `feature_steps.md` records all planned test names up front; this file
coordinates the session blocks.

**What to implement:**

1. `initial_idea.md` — problem, Fritz-vs-Caissa table, confirmed decisions, empty open-questions table
2. `feature_spec.md` — all eleven sections per template; §4 purity-tier table; §7 N-FRITZ-1..12; §8 mode-gated isolation with four arguments and nine-row enforcement table
3. `feature_steps.md` — all phases with test name lists; later phases as `xfail(strict=True)` stubs
4. `implementation_plan.md` — this file with all session blocks

**Tests this session makes green:**

*(documentation only — no new tests)*

**Spec refs:** §9, `docs/process/sdd-workflow.md` Gate A

**Definition of done:**

- [ ] `feature_spec.md` written — all eleven sections, no open decision, §8 argues mode-gated isolation
- [ ] `initial_idea.md` written and marked FROZEN
- [ ] `feature_steps.md` written with all planned test names across all phases
- [ ] `implementation_plan.md` written with all session blocks
- [ ] All target tests green; no other tests broken
- [ ] `make lint` passes

**Suggested commit:** `docs(fritz): Phase D-A — Gate A SDD artefacts`

---

### Session D-B — Design-time docs and standards

**Files to create/edit:**

- `docs/fritz/README.md` (create)
- `docs/fritz/concepts.md` (create)
- `docs/fritz/glossary.md` (create)
- `docs/fritz/decisions.md` (create)
- `docs/fritz/design-approval.md` (create — stub with the checklist structure, unsigned)
- `docs/standards/ui-design-process.md` (create)
- `docs/standards/architecture.md` (create)
- `docs/modern-fritz.md` (supersede — `git mv` still-accurate content to `docs/fritz/`, file deleted)
- `CLAUDE.md` (edit — repo tree, Purity tiers subsection, two new standards, Development Commands section)
- `CHANGELOG.md` (edit — `[Unreleased]` entry for the Fritz Polish feature)

**Scope:**

The design-time product-doc subset and the two new standards. These are the deliverables that every
future mode inherits rather than re-derives.

**What to implement:**

1. `docs/fritz/README.md` — "Which Document Do I Want?" table with `*(Phase N)*` annotations, ASCII tree, design-time vs phase-delivered split, SDD back-pointer
2. `docs/fritz/concepts.md` — mode-gated visual overlay, the `qproperty-` contract concept, fixed window vs fit-board
3. `docs/fritz/glossary.md` — `| Term | Definition | Fritz equivalent |` table, alphabetical, 3-column
4. `docs/fritz/decisions.md` — ADR log D1–D11, no open decisions
5. `docs/fritz/design-approval.md` — stub with the Round 1 / Round 2 checklist structure, dated fields left blank
6. `docs/standards/ui-design-process.md` — ten sections per plan: core principle, why not a design tool, oracle, the loop, approval gate, phase-exit re-review, extending QSS to custom widgets, escalation ladder, what is not a test, reference implementation
7. `docs/standards/architecture.md` — feature-package convention, purity-tier declaration + AST test, strangler-fig scope, plain-base-class rule, characterisation-test-first procedure, pointers to both `test_completeness.py` files
8. `docs/modern-fritz.md` supersession: `git mv` the still-accurate content into `docs/fritz/concepts.md` and `docs/fritz/theming.md` stubs; report the three drifted claims in the PR body; delete the file
9. `CLAUDE.md` edits: repo tree gains `bin/Code/Fritz/`, `docs/features/fritz-polish/`, `docs/fritz/`, `Resources/Ribbons/`; *Key Architecture Concepts* gains *Purity tiers* subsection; Standards summary gains two new standards; add *Development Commands* section with `make` targets and the five pytest markers
10. `CHANGELOG.md`: new entry under `[Unreleased]` → `### Added`

**Tests this session makes green:**

*(documentation only — no new tests)*

**Spec refs:** D.1-D.6, §10 (Out of Scope)

**Definition of done:**

- [ ] All seven `docs/fritz/` design-time pages written
- [ ] Both new standards written
- [ ] `docs/modern-fritz.md` deleted; content migrated; PR body notes three drifted claims
- [ ] `CLAUDE.md` updated with repo tree, purity tiers, standards, development commands
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] All target tests green; no other tests broken
- [ ] `make lint` passes
- [ ] Tracker updated: Phase D marked ✅

**Suggested commit:** `docs(fritz): Phase D — design-time docs, standards, supersede modern-fritz.md`

---

## Phase 0 — Fritz package skeleton, QSS contract, design harness

*(Detailed session breakdowns will be written when Phase 0 is the current phase — once the Phase D
PR is merged. The test names, files and spec refs are declared in `feature_steps.md` §Phase 0.)*

---

## Phases 1–7

*(Detailed session breakdowns will be written when each phase is the current one — once the
preceding phase's PR is merged. Test names, files and spec refs are declared in `feature_steps.md`
for each phase.)*

---

## Final Verification

```bash
make lint        # zero issues
make test        # all green
make cov-fritz   # ≥ 90 % Code.Fritz branch coverage
make docs        # zero warnings
make test-all    # markers vs filesystem cross-check
make test-ui     # out-of-process; the tests launch the app themselves
```

Update `feature_steps.md`: mark all phases ✅.
Move `docs/features/fritz-polish/` to `docs/features/_archive/fritz-polish/` with
`**Status:** Completed 2026-XX-XX` in each file.

---

## Session Summary Table

| Session | Phase | What it delivers | New tests |
|---------|-------|-----------------|-----------|
| D-A | Documentation | Gate A artefacts (spec, steps, plan, initial idea) | 0 |
| D-B | Documentation | docs/fritz/ design-time pages, two standards, supersession | 0 |
| 0-A | Foundations | `bin/Code/Fritz/` skeleton, Types, Errors, QssRules, ModeGateway | ~17 |
| 0-B | Foundations | Design harness, offscreen smoke test, §0.2b optional hardening | ~5 |
| 1-A | Widget QSS | ThemeGateway, ConfigGateway, five widget `qproperty-` contracts | ~20 |
| 2-A | Fixed window | BoardFit (pure), characterisation table | ~8 |
| 2-B | Fixed window | GeometryStore, MainWindow guard, `adjust_size` inert, Board.fit_to | ~12 |
| 2-C | Fixed window | Six QtDriver verbs, splitter persistence fixes, T-FIX suite | ~15 |
| 3-A | Panes | PaneRegistry (pure), WFritzPane, mode-hook wiring | ~11 |
| 4-A | Clocks/Eval | ClockModel, EvalModel (pure), WFritzLCD, EngineGateway | ~13 |
| 5-A | Notation | NotationRowModel, FritzEtiquetaPGN, tab strip, NAG buttons | ~12 |
| 6-A | Light theme | Fritz.qss, Fritz.colors, modern-fritz-dark.json, hook key | ~8 |
| 7-A | Ribbon | RibbonModel (pure), JSON schema, T-RMAP suite | ~8 |
| 7-B | Ribbon | WRibbon, Ribbon.install/sync, WBase edits, QtDriver verbs | ~11 |
| 9-A | Production | production_readiness.md, coverage gate, docs gate, archive | 0 |

**Total: ~15 sessions, ~140 tests.**
