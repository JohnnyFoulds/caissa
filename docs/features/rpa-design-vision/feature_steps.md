# RPA Design Vision — Implementation Steps

Living implementation tracker for the Caissa RPA Design Vision feature.
Updated after each phase is completed.

**Spec reference:** [feature_spec.md](feature_spec.md)
**Design record:** [design-record.md](design-record.md)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Complete |

---

## Phase 0a — Land the design record ✅

**Branch:** `feat/rpa-design-vision` (merged PR #77)

**Files:**
- `docs/features/rpa-design-vision/design-record.md` (create — verbatim plan, verbatim)

**What we deliver:**
- The plan committed to the repo before any code or spec, per design-record §Phase 0a.
- All seven corrections, empirical measurements (with font-caveat notes), negative results,
  and P1–P7 prerequisite defects are now reviewable in a PR diff.

---

## Phase 0 — SDD artefacts + P4 fix 🔄

**Branch:** `feat/rpa-design-vision-sdd`

**Files:**
- `docs/features/rpa-design-vision/initial_idea.md` (create)
- `docs/features/rpa-design-vision/feature_spec.md` (create)
- `docs/features/rpa-design-vision/feature_steps.md` (create — this file)
- `docs/features/rpa-design-vision/implementation_plan.md` (create)
- `tests/unit/rpa/test_completeness.py` (edit — fix P4 vacuous gate)

**What we deliver:**
- Gate A: full R/I/P/Q/N spec reviewed before Phase 1 begins.
- P4 fixed: `_planned_test_names` reads both the archived path and this file; uses
  `pytest.fail` (not `pytest.skip`) when a non-archived steps file exists with zero names.
- Each of the seven corrections from `design-record.md` has a corresponding named test below
  so none survives only in the record.

**TDD test cases (Phase 0 — gate enforcement):**

These stubs are `xfail(strict=True)` until their owning phase lands. Their presence here
makes the test-name gate (`test_every_planned_test_name_exists_in_suite`) binding.

The seven corrections each map to a test name:
- Correction 1 (OCR-first is backwards): `test_fill_regions_two_components_not_one_for_adjacent_fills`
- Correction 2 (inverted polarity): `test_glyph_boxes_auto_polarity_inverted_region`
- Correction 3 (three bases insufficient): `test_perceived_gaps_ribbon_six_tab_nonuniform`
- Correction 4 (wrong mechanism asserted): `test_invisible_fill_fires_on_gradient_straddling_background`
- Correction 5 (flagship detector passes query 3): `test_peer_adjacency_spacing_uniformity_silent_same_scene`
- Correction 6 (corners never measured): `test_surface_broken_indeterminate_not_ok_when_corners_not_measured`
- Correction 7 (no invocation surface): `test_format_agent_last_line_starts_next`

---

## Phase 1 — Prerequisites P1–P7 ⬜

**Branch:** `feat/rpa-design-vision-p1`

**Files:**
- `bin/Code/Rpa/Types.py` (edit — add `SubRect`; add `Rect` methods P6)
- `bin/Code/Rpa/Resolve.py` (edit — P5: flatten + repoint; P7: add `resolve_all`)
- `bin/Code/Rpa/Service.py` (edit — P1: fix `_build_activity` kwargs)
- `bin/Code/Rpa/Runner.py` (edit — P2: pass `run_dir` into `Context`)
- `bin/Code/Rpa/Driver.py` (edit — `widget_info` emits `sub_rects` + `paint_overrides`)
- `bin/Code/Rpa/Fakes.py` (edit — fixtures carry `sub_rects` + synthetic screenshot)
- `bin/Code/Rpa/Vision/Region.py` (create — `flatten` lives here, pure tier)
- `bin/Code/Main/WBase.py` (edit — `setObjectName` on board / tb / pgn)
- `bin/Code/Main/MainWindow.py` (edit — `setObjectName` on splitter containers)
- `tests/unit/rpa/test_completeness.py` (edit — close cv2 prune hole; transitive resolution P3)
- `tests/unit/rpa/test_types.py` (edit — new Rect method tests)
- `tests/unit/rpa/test_region.py` (create — `flatten` tests)

**What we deliver:**
- P5: `visible_elements` and `_object_candidates` use `Region.flatten`'s absolute-rect output.
  The Classical Invariant toolbar scan that was broken by this (see design-record) is fixed.
- P6: `Rect` gains `intersects`, `intersection`, `area`, `translate`, `inset`, `contains_point`;
  `Template._iou` delegates to `Rect.iou`, killing the duplicate.
- P1: `_build_activity` passes the correct kwargs for all 9 activity types.
- P2: `Runner` passes `run_dir` into `Context`.
- P3: cv2 import guard is transitive (matching `tests/unit/fritz/test_completeness.py`).
- P7: `resolve_all` returns a list; `AmbiguousMatchError` is not raised for multi-match queries.

**TDD test cases (Phase 1):**

- `test_flatten_produces_absolute_rects_for_deeply_nested_widget`
- `test_resolve_all_returns_list_not_single`
- `test_rect_intersects`
- `test_rect_intersection`
- `test_rect_area`
- `test_rect_translate`
- `test_rect_inset`
- `test_rect_contains_point`

**Gate:** `make test` green; a 4-deep synthetic tree hit-tests to a capture-absolute rect;
`rpa_act` reaches all 9 existing activity types without TypeError; `rpa_state` still <200 ms.

---

## Phase 2 — Pure core: Scene, Measure, Report ⬜

**Branch:** `feat/rpa-design-vision-2`

**Files:**
- `bin/Code/Rpa/Vision/Scene.py` (create — five primitives + eight supporting types)
- `bin/Code/Rpa/Vision/Measure.py` (create — four bases, gaps, peers, seams, surfaces)
- `bin/Code/Rpa/Vision/Report.py` (create — emit, diff, two_sided_pass, write_spec)
- `tests/unit/rpa/test_scene.py` (create)
- `tests/unit/rpa/test_measure.py` (create)

**What we deliver:**
- `Scene.py`: `Fill` (flat + gradient), `Ink`, `Seam`, `Corner`, `Surface`, `SceneNode`,
  `Scene`, `Gap`, `Hypothesis`, `Finding`, `PeerAttr`, `PeerCluster`, `RegionMatch`.
  `MEASURABLE` constant. `Scene.to_dict()`, `Scene.to_ascii()`, `Scene.from_observations()`.
- `Measure.py`: `gaps`, `perceived_gaps`, `gaps_all_bases`, `seams`, `seam_owner`,
  `surfaces`, `surface_breaks`, `peers`, `compare_peers`, `to_logical`, `fill_is_visible`,
  `uniformity`, `owner_of`, `sub_rect_of`, `relative_luminance`, `contrast_ratio`.
- `Report.py`: `emit` (always writes complete `report.json`), `diff` (joins on `node_id`),
  `two_sided_pass`, `write_spec`, `render`.

**TDD test cases (Phase 2):**

- `test_scene_node_measured_field_distinguishes_not_measured_from_absent`
- `test_fill_gradient_visible_uses_max_not_mean`
- `test_fill_visible_false_for_palette_window_match`
- `test_to_ascii_includes_not_measured_line`
- `test_gaps_all_bases_ribbon_six_tab`
- `test_perceived_gaps_ribbon_six_tab_nonuniform`
- `test_widget_gaps_ribbon_six_tab_uniform`
- `test_seam_shows_owner_ancestor_vs_parent`
- `test_surface_breaks_four_breaks_corner_first`
- `test_surface_breaks_zero_when_clean`
- `test_surface_breaks_indeterminate_when_corners_not_measured`
- `test_report_diff_joins_on_node_id`

**Gate:** ≥90% branch; 6-tab literal asserts `perceived=[12,13,24,24,25] non_uniform` AND
`widget=[0,0,0,0,0] uniform`; `not measured:` line appears in `to_ascii` golden; nested
widget hit-tests through `flatten`; `two_sided_pass` requires both conditions.

---

## Phase 2b — Detectors + Region grounding + corpus seed files ⬜

**Branch:** `feat/rpa-design-vision-2b`

**Files:**
- `bin/Code/Rpa/Vision/Region.py` (edit — add LEXICON, named_regions, resolve_phrase, geometric fallback)
- `bin/Code/Rpa/Vision/Detectors.py` (create — five Phase-2b detectors + run_all + xfail stubs)
- `Resources/Rpa/Design/queries/ribbon-tab-spacing.json` (create)
- `Resources/Rpa/Design/queries/side-panel-captions.json` (create)
- `Resources/Rpa/Design/queries/notation-tab-group.json` (create)
- `tests/unit/rpa/test_region.py` (edit — phrase grounding tests)
- `tests/unit/rpa/test_detectors.py` (create)

**What we deliver:**
- Phase-2b detectors: `invisible_fill`, `spacing_uniformity`, `peer_adjacency`,
  `surface_broken`, `orphan_style_rule`. `run_all` with `basis_disagreement`.
- Eight deferred detectors as `xfail(strict=True)` named stubs.
- Three seed query corpus JSON files — the primary acceptance criterion for the feature.
- `Region.LEXICON` covers `side panel`, `the notation panel`, and geometric terms.

**TDD test cases (Phase 2b):**

- `test_invisible_fill_fires_on_flat_palette_window`
- `test_invisible_fill_fires_on_gradient_straddling_background`
- `test_invisible_fill_mean_rule_would_pass_gradient`
- `test_spacing_uniformity_passes_notation_tabs`
- `test_spacing_uniformity_fails_ribbon_perceived`
- `test_peer_adjacency_fires_on_ancestor_seam`
- `test_peer_adjacency_silent_on_parent_seam`
- `test_peer_adjacency_spacing_uniformity_silent_same_scene`
- `test_surface_broken_fires_four_breaks`
- `test_surface_broken_corner_listed_first`
- `test_surface_broken_indeterminate_not_ok_when_corners_not_measured`
- `test_surface_broken_zero_breaks_clean_surface`
- `test_orphan_style_rule_fires_on_qtabwidget_pane`
- `test_orphan_style_rule_silent_on_qtabbar_tab`
- `test_fill_extent_silent_on_full_width_captions`
- `test_contrast_fires`
- `test_missing_child_fires`
- `test_text_duplication_fires`
- `test_peer_divergence_fires`
- `test_edge_alignment_fires`
- `test_containment_fires`
- `test_theme_blindness_fires`

**Gate:** `"the side panel"` → `#WFritzRightCol`; unknown phrase returns `None`; `spacing_uniformity`
reports `uniform` on the notation-tab literal; `invisible_fill` fires on both flat and gradient
fixtures; `peer_adjacency` fires on `shows_owner="ancestor"`, silent on `"parent"`, and
`spacing_uniformity` is `uniform` on the same scene; `fill_extent` is NOT in the three-seed-query
findings; eight deferred stubs are `xfail(strict=True)`.

---

## Phase 2c — StyleSource bridge ⬜

**Branch:** `feat/rpa-design-vision-2c`

**Files:**
- `bin/Code/Fritz/QssRules.py` (edit — generalise `qproperties()` → `parse_rules()`)
- `bin/Code/Rpa/Vision/StyleSource.py` (create)
- `tests/unit/rpa/test_style_source.py` (create)

**What we deliver:**
- `StyleSource.style_sources_for`: for a given widget, returns all matching QSS rules plus
  paint constants, each with `authored`, `resolved`, `effective` (three-valued).
- `effective("QTabWidget::pane", ...)` returns `"loaded_unmatched"` — the single most
  important assertion in this phase, because it is the one my original check would have failed.
- `effective("fritz-widgets.qss::tab:first", ...)` returns `"matched_overridden"`.
- `font_mismatch` detected when QSS `font-size` differs from the widget's `self.font()`.

**TDD test cases (Phase 2c):**

- `test_style_source_wribbon_file_fill_governed_by_paintEvent`
- `test_style_source_fritz_widgets_qss_290_matched_overridden`
- `test_style_source_caissa_qss_214_loaded_unmatched`
- `test_style_source_font_mismatch_detected`

**Gate:** All four tests pass; `test_style_source_caissa_qss_214_loaded_unmatched` is the
go/no-go: if it names either `fritz-widgets.qss` or `Fritz.qss` as effective, the bridge
has reproduced the original mistake and the phase fails.

---

## Phase 2d — Decision gate ⬜

**Branch:** n/a (no code)

**What we deliver:**
- Run the next real UI query you raise against Phases 2–2c with a Python-driven probe.
- Author a fourth `Resources/Rpa/Design/queries/*.json` from that query.
- Decide which of the eight deferred detectors to write next, recording the decision in
  this file under a new section.

**Gate:** Fourth `queries/*.json` exists; decision recorded here. This may legitimately
conclude "write none of the deferred detectors yet."

---

## Phase 3 — CV core ⬜

**Branch:** `feat/rpa-design-vision-3`

**Files:**
- `bin/Code/Rpa/Vision/Segment.py` (create — Tier 2, cv2)
- `bin/Code/Rpa/Vision/Annotate.py` (create — Tier 2, cv2)
- `bin/Code/Rpa/Vision/Ocr.py` (edit — psm/upscale params; add `read_words`)
- `bin/Code/Rpa/Vision/Template.py` (edit — add 0.5/2.0 to `_MULTI_SCALES`)
- `.coveragerc` (edit — omit `Vision/Segment.py`, `Vision/Annotate.py`)
- `tests/unit/rpa/test_segment.py` (create — `rpa_cv` marker)

**What we deliver:**
- `Segment.py`: `fill_regions` (CC, not global bbox), `glyph_boxes` (polarity="auto"),
  `ink_of` (local fill), `fill_of` (flat+gradient classifier), `corner_of`, `seam_of`,
  `row_bands`, `palette`, `dominant_hex`.
- `Annotate.py`: `boxes`, `dimension_line`, `label_nodes`, `highlight_findings`, `crops`.
- All five empirical findings from `design-record.md` are validated by test fixtures drawn
  at test time (no committed screenshots).

**TDD test cases (Phase 3):**

- `test_fill_regions_two_components_not_one_for_adjacent_fills`
- `test_glyph_boxes_auto_polarity_inverted_region`
- `test_glyph_boxes_fixed_threshold_fails_inverted_region`
- `test_ink_of_uses_local_fill_not_global`
- `test_fill_of_classifies_gradient_v`
- `test_fill_of_gradient_visible_false_straddling_background`
- `test_corner_of_measures_radius_from_arc_staircase`

**Gate:** `make test-cv` green with real assertions; no `pytest.skip` placeholders.

---

## Phase 4 — Activities + verbs ⬜

**Branch:** `feat/rpa-design-vision-4`

**Files:**
- `bin/Code/Rpa/Activities.py` (edit — add 6 observer activities)
- `bin/Code/Rpa/Service.py` (edit — add `rpa_describe`, `rpa_inspect`, `rpa_report`; QThreadPool/deque)
- `tests/unit/rpa/test_activities_vision.py` (create)

**TDD test cases (Phase 4):**

- `test_locate_phrase_resolves_side_panel`
- `test_locate_phrase_returns_none_not_guess_on_unknown`
- `test_describe_scene_degrades_gracefully_no_screenshot`
- `test_describe_scene_warnings_when_cv_unavailable`
- `test_rpa_describe_returns_report_id_immediately`
- `test_rpa_report_status_transitions`
- `test_rpa_inspect_under_200ms`

**Gate:** `<200 ms` verb timing asserted; main thread not blocked during OCR (UI-responsiveness check).

---

## Phase 4b — Agent surface ⬜

**Branch:** `feat/rpa-design-vision-4b`

**Files:**
- `tools/caissa-eyes` (create — 0755)
- `.claude/skills/design-eyes/SKILL.md` (create)
- `.claude/commands/design-eyes.md` (create — one-line escape hatch)
- `tools/caissa-rpa` (chmod +x only)
- `tests/unit/rpa/test_eyes_cli.py` (create)

**TDD test cases (Phase 4b):**

- `test_ingest_decodes_base64_image_from_transcript`
- `test_ingest_unknown_phrase_no_socket_dies_naming_missing_thing`
- `test_format_agent_under_2kb`
- `test_format_agent_last_line_starts_next`

**Gate (Phase 4b — tests me, not just code):** A `claude -p` run with a UI complaint verbatim
must show `caissa-eyes shot`/`ingest` AND `caissa-eyes inspect` appearing **before** any
`Read`/`Grep` of a `.qss` or `.py` file. Negative case: a behaviour bug must NOT trigger the
skill. Both transcript excerpts go in the PR body.

---

## Phase 5 — Spec collapse ⬜

**Branch:** `feat/rpa-design-vision-5`

**Files:**
- `Resources/Rpa/Design/ribbon.spec.json` (create)
- `Resources/Rpa/Design/panes.spec.json` (create)
- `tools/design/ribbon_report.py` (edit — read spec, drop `TARGET`)
- `tools/design/elements.py` (edit — read spec, drop per-element targets)
- `tools/design/compare.py` (edit — theme-parameterise `chrome_mask` + `row_ink_profile`)
- `docs/fritz/ribbon.md` (edit — §Measured reference becomes a pointer)
- `tests/unit/rpa/test_design_spec.py` (create)

**TDD test cases (Phase 5):**

- `test_ribbon_spec_json_is_canonical_source_of_truth`
- `test_assert_design_spec_known_deviation_warns_not_fails`
- `test_deviation_stale_fires_when_deviation_starts_passing`

**Gate:** `ribbon_report.py` scorecard output byte-identical to pre-migration; dark-variant
input no longer silently returns garbage from `chrome_mask`.

---

## Phase 6 — Query corpus runner + design_verify workflow ⬜

**Branch:** `feat/rpa-design-vision-6`

**Files:**
- `tests/unit/rpa/test_query_corpus.py` (create — `rpa` marker + per-function `rpa_cv`)
- `bin/Code/Rpa/Workflows/design_verify.py` (create)
- `bin/Code/Rpa/Service.py` (edit — register `design_verify` in `_load_builtin_workflows`)

**TDD test cases (Phase 6):**

- `test_query_corpus_ribbon_tab_spacing`
- `test_query_corpus_side_panel_captions`
- `test_query_corpus_notation_tab_group`
- `test_design_verify_workflow_passes_dry_run`

**Gate:** All three+ corpus queries answered end-to-end from the phrase alone; `expect_absent`
and `expect_verdict` both hold (including `spacing_uniformity=uniform` on the notation-tab
query); `design_verify` passes `dry_run`.

---

## Phase 7a — Diagnose + propose (visual phase — approval required) ⬜

**Branch:** `feat/rpa-design-vision-7a`

**Files:**
- `docs/features/rpa-design-vision/design-approval.md` (create — §5 two-round sign-off)

**What we deliver:**
- Run all corpus queries against the live app; capture before-reports.
- Render the proposed five-change notation-tab fix and the pane-caption fix with
  `tools/design/fritz_mock.py` (through `tests/conftest.py::_bootstrap()`).
- Build the sheet with `tools/design/review.py`; record sign-off.

**Gate:** `design-approval.md` sign-off recorded. No QSS edited in 7a. **This gate blocks 7b.**

---

## Phase 7b — Implement + re-verify (visual phase) ⬜

**Branch:** `feat/rpa-design-vision-7b`

**What we deliver:**
- Apply the five-change notation-tab fix (`design-record.md §The fix is therefore not the four
  QSS lines I proposed`).
- Apply the pane-caption gradient fix.
- Add deferred detectors only as new corpus queries demand them.
- Phase-exit `tools/design/review.py --live` against the running app.

**Gate:**
- Before/after reports in PR body: all four `surface_broken` breaks gone, nothing new.
- **`Caissa.qss:214-218` left untouched** — it matches nothing; touching it would prove the
  bridge is still pointing at dead rules.
- Real-execution evidence (Gate E): `make test-cv` run output, `caissa-eyes verify` output.
