# RPA Design Vision — Implementation Plan

**Spec reference:** [feature_spec.md](feature_spec.md)
**Phase tracker:** [feature_steps.md](feature_steps.md)
**Design record:** [design-record.md](design-record.md)

---

## Current State (as of 2026-08-30)

| What exists | Status |
|---|---|
| `docs/features/rpa-design-vision/design-record.md` | Committed on main (PR #77) |
| `docs/features/rpa-design-vision/` SDD artefacts | Phase 0 in progress — this PR |
| `bin/Code/Rpa/Vision/` | Existing: Capture, Template, Ocr, Availability, Manifest. New Vision modules do not exist yet. |
| `tests/unit/rpa/test_completeness.py` P4 gate | Vacuous (reads archived path, skips on missing) — fixed in this PR |

Work begins at **Session 1-A** once Phase 0 PR is merged.

---

## How to use this plan

Each session maps to a small, coherent set of changes. The workflow for every session:

1. Run `make test` — confirm the session's target tests are **red** (failing or `xfail`).
2. Write the production code.
3. **Human diff review (Gate C)** — read every changed line before committing.
4. Run `make test` — all tests **green**, no regressions.
5. Run `make lint` — zero new issues.
6. Update living docs if implementation revealed corrections.
7. Commit with the suggested message. More sessions in this phase? GOTO 1. Else open PR.

**One branch = one phase = one PR.** Never stack phases on one branch.

---

## Files to Create / Modify

| File | Action | Session |
| --- | --- | --- |
| `docs/features/rpa-design-vision/initial_idea.md` | **Create** | 0 |
| `docs/features/rpa-design-vision/feature_spec.md` | **Create** | 0 |
| `docs/features/rpa-design-vision/feature_steps.md` | **Create** | 0 |
| `docs/features/rpa-design-vision/implementation_plan.md` | **Create** | 0 |
| `tests/unit/rpa/test_completeness.py` | **Edit** — P4 fix | 0 |
| `bin/Code/Rpa/Types.py` | **Edit** — SubRect; Rect P6 methods | 1-A |
| `bin/Code/Rpa/Vision/Region.py` | **Create** — flatten (pure) | 1-A |
| `bin/Code/Rpa/Driver.py` | **Edit** — sub_rects + paint_overrides | 1-A |
| `bin/Code/Rpa/Fakes.py` | **Edit** — fixtures with sub_rects | 1-A |
| `bin/Code/Main/WBase.py` | **Edit** — 3 setObjectName | 1-A |
| `bin/Code/Main/MainWindow.py` | **Edit** — 3 setObjectName | 1-A |
| `bin/Code/Rpa/Resolve.py` | **Edit** — P5, P7 | 1-B |
| `bin/Code/Rpa/Service.py` | **Edit** — P1 (_build_activity) | 1-B |
| `bin/Code/Rpa/Runner.py` | **Edit** — P2 (run_dir → Context) | 1-B |
| `tests/unit/rpa/test_completeness.py` | **Edit** — P3 (transitive cv2 guard) | 1-B |
| `bin/Code/Rpa/Vision/Scene.py` | **Create** | 2-A |
| `bin/Code/Rpa/Vision/Measure.py` | **Create** | 2-B |
| `bin/Code/Rpa/Vision/Report.py` | **Create** | 2-C |
| `bin/Code/Rpa/Vision/Region.py` | **Edit** — LEXICON, phrase grounding | 2b-A |
| `bin/Code/Rpa/Vision/Detectors.py` | **Create** | 2b-B, 2b-C |
| `Resources/Rpa/Design/queries/` (3 files) | **Create** | 2b-C |
| `bin/Code/Fritz/QssRules.py` | **Edit** — generalise to parse_rules | 2c |
| `bin/Code/Rpa/Vision/StyleSource.py` | **Create** | 2c |
| `bin/Code/Rpa/Vision/Segment.py` | **Create** — Tier 2 | 3-A |
| `bin/Code/Rpa/Vision/Annotate.py` | **Create** — Tier 2 | 3-B |
| `bin/Code/Rpa/Vision/Ocr.py` | **Edit** — psm/upscale/read_words | 3-B |
| `bin/Code/Rpa/Vision/Template.py` | **Edit** — scale 0.5/2.0 | 3-B |
| `.coveragerc` | **Edit** — omit Segment, Annotate | 3-B |
| `bin/Code/Rpa/Activities.py` | **Edit** — 6 new activities | 4-A |
| `bin/Code/Rpa/Service.py` | **Edit** — rpa_describe/inspect/report + QThreadPool | 4-A |
| `tools/caissa-eyes` | **Create** — 0755 | 4-B |
| `.claude/skills/design-eyes/SKILL.md` | **Create** | 4-B |
| `.claude/commands/design-eyes.md` | **Create** | 4-B |
| `tools/caissa-rpa` | **chmod +x** only | 4-B |
| `Resources/Rpa/Design/ribbon.spec.json` | **Create** | 5 |
| `Resources/Rpa/Design/panes.spec.json` | **Create** | 5 |
| `tools/design/ribbon_report.py` | **Edit** — read spec | 5 |
| `tools/design/elements.py` | **Edit** — read spec | 5 |
| `tools/design/compare.py` | **Edit** — theme-parameterise | 5 |
| `tests/unit/rpa/test_query_corpus.py` | **Create** | 6 |
| `bin/Code/Rpa/Workflows/design_verify.py` | **Create** | 6 |
| `docs/features/rpa-design-vision/design-approval.md` | **Create** | 7a |

---

## Session breakdown

### Session 0 — SDD artefacts + P4 fix (current)

**Branch:** `feat/rpa-design-vision-sdd`

- Create four SDD artefacts derived from `design-record.md`
- Fix `_planned_test_names` in `test_completeness.py`: read both paths, `pytest.fail` not skip

**Suggested commit message:** `docs(rpa): add SDD artefacts for rpa-design-vision feature`

---

### Session 1-A — P5, P6, setObjectName, sub_rects

**Branch:** `feat/rpa-design-vision-p1`

P5 is the most critical: `Resolve.visible_elements` iterates `widget_tree` flatly and therefore
only ever sees top-level windows. The Classical Invariant toolbar scan is already broken by
this (design-record §P5). Fix: `Region.flatten(widget_tree) -> list[dict]` in the pure tier,
recursively accumulating parent offsets; `Resolve.visible_elements` and `_object_candidates`
repointed at its output.

**Tests green after session:** `test_flatten_produces_absolute_rects_for_deeply_nested_widget`
and the existing classical invariant tests.

---

### Session 1-B — P7, P1, P2, P3

**Branch:** `feat/rpa-design-vision-p1` (continued or separate)

P1 (`_build_activity` TypeError on 5 of 9 activity types) and P2 (Context missing `run_dir`)
are one-liners. P7 (`resolve_all`) is a new method. P3 closes the cv2 allowlist hole and
upgrades to transitive resolution.

---

### Session 2-A — Scene.py

**Branch:** `feat/rpa-design-vision-2`

Write `Scene.py` with the five primitives and eight supporting types. Key invariants:
- `Fill.visible` for a gradient is the **maximum** perceptual distance across the ramp
- `SceneNode.measured` is the completeness inventory; `()` ≠ "not measured"
- `corners=()` means not measured, not "square" — these are not the same

Tests confirm the max-vs-mean distinction directly: a `gradient_v` fixture with `#252526 →
#363636` over `#2d2d2d` must return `visible=False` and `visible_delta ≤ 9`; the mean-based
rule must return `True` on the same fixture (companion assertion pins the decision).

---

### Session 2-B — Measure.py

Four bases, gaps, `perceived_gaps`, seams, surfaces, surface_breaks, peers.

The 6-tab literal is the core regression guard:
```python
perceived = [12, 13, 24, 24, 25]   # non_uniform — 2.08× spread
widget    = [0,  0,  0,  0,  0 ]   # uniform — all tabs abut
```
Both must be asserted in the same test. The companion assertion that the widget basis
reports uniform is what protects against a future "simplification" that merges bases.

---

### Session 2-C — Report.py

`emit` always writes the complete `report.json`; verbosity only governs `scene.txt`.
`two_sided_pass` requires both: finding gone AND no new warn. Test with a fixture that
removes the targeted finding but adds a new one — must return False.

---

### Session 2b-A — Region.py phrase grounding

LEXICON covers: `side panel/right panel/panel column → #WFritzRightCol`,
`the notation panel/notation/move list → pgn PaneSpec`, `main area → Layouts.PRESETS["main"]`,
plus geometric terms. Six missing objectNames added in Phase 1 are what make the board/toolbar
entries work by name.

`resolve_phrase` returns `None` rather than guessing. Test must assert `None` on an unknown
phrase, not a geometric fallback that silently answers a different question.

---

### Session 2b-B — Detectors: invisible_fill and spacing_uniformity

Write these two first because they are the two with the most evidence (all three queries for
`invisible_fill`; query 1 for `spacing_uniformity`). Each gets a true-positive test AND a
no-false-positive test:

- `invisible_fill`: fires on flat `palette().window()` match AND on gradient straddling
  background; mean rule would have passed the gradient (companion assertion)
- `spacing_uniformity`: fails ribbon `perceived` (12,13,24,24,25) AND passes the notation
  tab literal (2,2,2,2) — the second is the wrong-predicate regression guard

---

### Session 2b-C — Detectors: peer_adjacency, surface_broken, orphan_style_rule + xfail stubs

`peer_adjacency` gets the paired test: fires on `shows_owner="ancestor"` AND `spacing_uniformity`
reports `uniform` on the same scene. That paired assertion is the single most important test in
the suite — it documents the lesson of correction 5.

`surface_broken` gets the `corners=()` + `measured` not containing `"corners"` → `indeterminate`
test. This is correction 6 pinned as a regression guard.

`orphan_style_rule` needs no Scene at all: literal selector list vs literal widget class set.

Eight deferred stubs as `xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")`.

Author all three seed corpus JSON files here, not in Phase 6. They are declarations of
expected output, written against what the detectors must produce.

---

### Session 2c — StyleSource.py

The go/no-go test: `test_style_source_caissa_qss_214_loaded_unmatched`. If it passes, the
bridge is correct. If it names `fritz-widgets.qss:290` or `Fritz.qss:1015` as effective, it
has reproduced my original mistake and the phase fails.

Generalise `QssRules.qproperties()` → `parse_rules()` and reimplment `qproperties()` as a
filter — one parser, two callers, no second QSS parser in the repo.

---

### Session 2d — Decision gate (no code)

Run the next real UI complaint you raise as a Python-driven probe against the built modules.
Author a fourth corpus JSON. Record the decision about deferred detectors here.

This gate cannot be skipped or automated. The detectors list grew on every query; guessing
which ones to build next has a documented failure rate of 100%.

---

### Session 3-A — Segment.py

Five empirical findings become five test fixtures drawn at test time:
1. Adjacent `#ffffff` fills — two CC components, not one
2. Inverted-polarity region — `glyph_boxes(polarity="auto")` finds glyphs; fixed threshold 150 finds none
3. `ink_of` with local fill, not global background
4. `fill_of` classifying a ramp as `gradient_v`
5. `corner_of` reading radius from anti-aliased arc staircase

All fixtures are synthetic PNGs drawn with `cv2.rectangle`/`putText`/`circle` at test time.
Nothing committed.

---

### Session 3-B — Annotate.py + Ocr.py + Template.py

`Annotate` is the thinnest module: evidence for the user, never an assertion. `node_id` not
`alias` as the default label (readable against `report.json`).

`Template._MULTI_SCALES` gains `0.5` and `2.0`. The staleness warning fires only for scales
that are NOT a known DPR factor, so a Retina crop matching at `2.0` is not false-stale.

---

### Session 4-A — Activities + verbs

`DescribeScene.execute` captures synchronously (main thread, cheap) and submits the cv2/OCR
work to `QThreadPool`. `postcondition` calls `ctx.refresh_snapshot()` and polls the report
registry. With `QApplication` absent (tests), work runs inline and `rpa_describe` returns
`{..., "status": "ready"}` in one call.

`rpa_inspect` is synchronous, always <200 ms: it runs `Detectors.run_all` over an existing
`Scene` in the report registry. The timing test must assert this.

---

### Session 4-B — Agent surface

`tools/caissa-eyes` copies the idiom from `tools/caissa-rpa` (module docstring, `_SOCK`,
`_die`, `_json_out`, `_COMMANDS` dict) with the per-command `needs_live_app` flag as the
only structural addition.

`ingest` reads the session `.jsonl` from `~/.claude/projects/<cwd-slug>/`. The cwd-slug is
`/Users/johannes/code/lucaschess` → `-Users-johannes-code-lucaschess`. Confirmed present.
Handles missing transcript gracefully: skips non-JSON lines, dies naming the missing thing.

The `SKILL.md` trigger description must enumerate your actual phrasings — not a tidy category.
The negative case (behaviour bug does not trigger the skill) is as important as the positive.

---

### Session 5 — Spec collapse

Migration order matters to avoid breaking the scorecard mid-way:
1. Write `ribbon.spec.json` matching today's `TARGET` exactly
2. Repoint `ribbon_report.py` at the spec; verify scorecard byte-identical
3. Repoint `elements.py`; verify
4. **Only then** resolve the two genuine contradictions (file-tab fill `#005b99` vs `#007acc`)
   as a visible decision in `docs/fritz/decisions.md`
5. Add dark palette to the spec (your crop proved dark input is real and currently garbage)

---

### Session 6 — Corpus runner + design_verify workflow

`test_query_corpus.py` module-level `pytestmark = pytest.mark.rpa` + per-function
`@pytest.mark.rpa_cv` — matching `test_vision.py:22,110`. Runs under `make test-cv` only
(never `make test`).

`design_verify.py` follows `classical_invariant.py` exactly: private `_Activity` subclasses,
`register(name, callable_factory)` not `register(name, result)` (avoids the frozen uuid bug).

Re-measure every absolute pixel value in the corpus through `tests/conftest.py::_bootstrap()`
or the live app before committing them to spec fixtures. The 6-tab probe values in
`design-record.md` were measured with wrong fonts and will move.

---

### Session 7a — Diagnose + propose

Run `caissa-eyes inspect` over each corpus query against the live app. Capture before-reports.
Render the proposed fixes with `fritz_mock.py` (must reuse `_bootstrap()`; must write to
`CAISSA_DESIGN_OUT` not a hardcoded `/tmp/`). Build the review sheet with `review.py`
(opens via `webbrowser.open`, never `subprocess`). Record sign-off.

This is not automatable. It requires your eyes and your sign-off.

---

### Session 7b — Implement + re-verify

The five-change notation-tab fix (design-record §The fix is therefore not the four QSS lines
I proposed). The pane-caption gradient fix. Then `caissa-eyes verify --baseline <report_id>`.

PR body must include: before report, fix diff, after report showing all four `surface_broken`
breaks gone. And the note that `Caissa.qss:214-218` was left untouched — that is the
evidence the bridge stopped pointing at rules that match nothing.

---

## Risk notes

- **P5 is bigger than it looks.** The fix is small (one recursive function), but it is a
  prerequisite for four of the eight new modules, so it must land and be green before 2-A.
- **Phase 2d is a real gate.** The detector list has grown on every query. Skipping the pause
  and writing all eight deferred detectors based on prior queries would reproduce the failure
  of the original plan.
- **Session 7a requires your time.** The design approval gate is not a test; it is a meeting.
  Plan for it when scheduling 7b.
- **Re-measure before committing corpus fixtures.** The `design-record.md` pixel values were
  measured with wrong fonts. They are directionally correct but will move through `_bootstrap()`.
