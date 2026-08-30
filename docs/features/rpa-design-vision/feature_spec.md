# RPA Design Vision — Software Design Document

**Status:** Specified — implementation pending
**Branch:** phases `feat/rpa-design-vision-*` (one per phase; see feature_steps.md)
**Initial idea:** [initial_idea.md](initial_idea.md)
**Design record:** [design-record.md](design-record.md)
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## 1. Problem Statement

`tools/design/` renders mockups offscreen and scores them against hard-coded pixel targets,
but every measurement is widget-specific and the judgement step is a human reading a PNG.
The harness cannot answer compositional questions ("is the gap between File and Home the same
as the others?") because it has no concept of an element — only boxes at fixed coordinates.

There is also no agent-facing surface. When a UI complaint arrives, the agent's default is
to grep the stylesheet, which produced three separate attempts to edit `QTabWidget::pane` — a
rule that matches no widget in the application, because the notation "tab group" is a bare
`QTabBar` + a sibling `QTextEdit`, not a `QTabWidget`.

This feature builds a local measurement loop:

- **Symbolic extraction** — cv2 + tesseract turn a screenshot into a `Scene`: `SceneNode`s
  carrying `Fill`, `Ink`, `Seam`, `Corner` measurements; `Surface` relations across nodes;
  `PeerCluster` groupings; and a ranked `Finding` list.
- **Source resolution** — `StyleSource` maps each finding to the `file:line` that actually
  governs it, with three-valued `effective` (`loaded_unmatched` / `matched_overridden` /
  `effective`) so the agent is never sent to edit dead code.
- **Agent surface** — a `.claude/skills/` trigger fires on UI complaints; `tools/caissa-eyes`
  is the CLI that implements the 7-step measure→read-code→fix→verify loop.

The design record (`design-record.md`) contains the empirical measurements, negative results,
and seven corrections that justify every design decision in this spec. That document is
normative context; this spec governs on conflict.

---

## 2. Requirements

### 2.1 Business Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Enable Claude to diagnose Caissa UI defects locally, without uploading images to a cloud vision model. |
| BR-2 | Cover the Fritz sign-off flow: design-against-a-reference, producing a machine-readable verdict. |
| BR-3 | Cover interactive repair: given a pasted screenshot or verbal description, locate the element, name the governing code, verify the fix. |
| BR-4 | Implement as RPA Activities following the existing RPA standards and 5-step closed loop. |
| BR-5 | Provide a skill + CLI surface so the measurement loop fires automatically on UI complaints. |

### 2.2 Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1 | The system **MUST** produce a `Scene` for any selector or phrase, containing `SceneNode`s with `Fill`, `Ink`, `Seam`, `Corner` measurements and a `SceneNode.measured` inventory. |
| FR-2 | `Fill` **MUST** model flat and gradient fills. For a gradient, `visible` is the **maximum** perceptual distance from the local background across the ramp, not the mean. |
| FR-3 | `SceneNode.measured` **MUST** enumerate which properties were attempted. A property absent from `measured` is NOT measured — it must never render as a property that passed. |
| FR-4 | The system **MUST** implement four gap bases: `widget`, `fill`, `ink`, and `perceived`. `perceived` falls through to the nearest visible boundary, then to ink-to-ink. |
| FR-5 | The system **MUST** implement peer clustering: nodes grouped by `(role, parent_role, index_within_parent, height_bucket, fill_hex_bucket)` signature, with `CONSTANT`/`VARYING` per attribute. |
| FR-6 | The system **MUST** implement phrase grounding (`Region.resolve_phrase`) that resolves human vocabulary to a `Rect` via LEXICON → objectName → className → geometric fallback, returning `None` rather than guessing. |
| FR-7 | The system **MUST** ship five detectors in Phase 2b: `invisible_fill`, `spacing_uniformity`, `peer_adjacency`, `surface_broken`, `orphan_style_rule`. Eight further detectors are deferred to Phase 7. |
| FR-8 | `Finding.verdict` **MUST** be `non_uniform` if **any** basis says non-uniform. Basis disagreement **MUST** be promoted to its own `basis_disagreement` finding by `run_all`. |
| FR-9 | `StyleSource` **MUST** return three-valued `effective`: `loaded_unmatched` (selector in stylesheet, no matching widget), `matched_overridden` (widget matches, `paintEvent` wins), or `effective`. It **MUST** degrade to `unconfirmed` without a live `QApplication`. |
| FR-10 | All CV segmentation **MUST** operate in physical (device-pixel) space; rects are converted to logical after measurement. (`N-RPAV-1`) |
| FR-11 | The system **MUST** provide six read-only observer RPA Activities: `Locate`, `DescribeScene`, `Inspect`, `MeasureSpacing`, `AssertDesignSpec`, `EmitVisionReport`. All are `compensable=False`. |
| FR-12 | The system **MUST** provide three new `rpa_*` verbs: `rpa_describe` (returns `report_id` immediately), `rpa_inspect` (synchronous, <200 ms), `rpa_report` (read-only status/result poll). |
| FR-13 | The system **MUST** provide `tools/caissa-eyes` with eight subcommands: `ingest`, `shot`, `locate`, `inspect`, `explain`, `verify`, `regions`, `doctor`. Each declares `needs_live_app`. |
| FR-14 | The system **MUST** provide `.claude/skills/design-eyes/SKILL.md` with a description matching your actual UI-complaint phrasings and a 7-step loop enforcing measure-before-code. |
| FR-15 | The system **MUST** provide a query corpus (`Resources/Rpa/Design/queries/*.json`) as the primary acceptance criterion: at minimum three seed entries covering the ribbon-spacing, side-panel-caption, and notation-tab-group queries. |

### 2.3 Non-Functional Requirements

Inherits N-RPA-1 through N-RPA-10 from `docs/features/_archive/rpa-layer/feature_spec.md §2.3` unchanged.

New rules for this feature:

| ID | Requirement |
| --- | --- |
| N-RPAV-1 | CV segmentation **MUST** operate in physical pixel space. `fill_regions` and all `Segment.*` functions take an ndarray; callers convert rects to logical with `to_logical(r, dpr)` afterwards. Mixing spaces silently corrupts measurements via resampling blur. |
| N-RPAV-2 | **Measured-field completeness.** `describe` **MUST** attempt every entry in `MEASURABLE` per node and record the result in `SceneNode.measured`. An absent entry means "not attempted" — it **MUST NOT** render as a passing result. `to_ascii()` prints a `not measured:` line for the difference. |
| N-RPAV-3 | **Two-sided verify.** `Report.two_sided_pass` requires (a) the targeted `Finding.kind` is absent from the after-scene AND (b) no new finding at or above `warn` appeared. One condition without the other is not a pass. |
| N-RPAV-4 | **Positional node identity.** `node_id` is derived from position first (`role[index]`), OCR second (alias only, never load-bearing). `node_id` **MUST** be stable across window widths and across runs with OCR disabled. |
| N-RPAV-5 | **StyleSource graceful degradation.** Without a live `QApplication`, `effective` degrades to `"unconfirmed"`. `loaded_unmatched` requires the flattened widget-type set from `Region.flatten`. Without it, the call must return `"unconfirmed"`, never guess. |

### 2.4 Constraints & Assumptions

- Placement: `bin/Code/Rpa/Vision/` for the eight new modules; `bin/Code/Rpa/Activities.py` extended with six activities; `bin/Code/Rpa/Service.py` extended with three verbs.
- `Vision/__init__.py` stays 0 bytes — zero import cost (N-RPA-9 runtime rule).
- `Segment.py` and `Annotate.py` are Tier 2 (cv2/tesseract); the other six Vision modules are Tier 1 (stdlib-only). `Scene.py` is at the root of the dependency graph; all other modules import it and nothing else.
- No `abc.ABC`, no `typing.Protocol` — plain base classes raising `NotImplementedError` (`architecture.md §5`).
- All new frozen dataclasses use `@dataclass(frozen=True, slots=True)` (`architecture.md §7`).
- All new callables have RST/Sphinx docstrings with a `:spec:` tag (N-RPA-6).
- `cv2` and `numpy` must not appear in `sys.modules` after a plain app start — lazy import inside `rpa_describe`, matching the house pattern (N-RPA-9).
- Optional dependencies: `cv2` and `pytesseract` from `requirements-rpa.txt`; the feature degrades gracefully when absent (see `DescribeScene` degradation matrix).

---

## 3. Terminology

| Term | Definition |
| --- | --- |
| **Scene** | A point-in-time symbolic description of a region: a tree of `SceneNode`s, plus `Seam`s, `Surface`s, `PeerCluster`s, `Finding`s and `warnings`. |
| **SceneNode** | One element: a rect, role, fill, ink, corners, borders, measured inventory, and style sources. |
| **Fill** | A node's background: flat (`hex_color`) or gradient (`hex_start`/`hex_end`), with `visible` (bool) and `visible_delta` (int) measured against the local `background_hex`. |
| **Ink** | The bounding box of non-background pixels inside a node's fill, with `coverage` and `hex_dominant`. |
| **Seam** | The shared boundary between two adjacent nodes: `px`, `shows_hex`, `shows_owner` (`"parent"` / `"ancestor"`), `closed`, `border_hex`. |
| **Corner** | One corner of a node's border: `which` (`tl`/`tr`/`bl`/`br`), `radius_px`, `shows_hex`, `shows_owner`. |
| **Surface** | A spec-supplied multi-node plane: nodes a design convention says should render as one continuous surface (e.g. a tab and its content pane). Carries a `breaks` tuple. |
| **Detector** | A pure function `(Scene, spec) -> list[Finding]`, registered by name in `Detectors.DETECTORS`. |
| **Finding** | A detector's output: `kind`, `verdict`, `summary` (measurement only, no mechanism), `severity`, `measurements`, `hypotheses` (ranked, never asserted), `confirmed_by` (empty until StyleSource resolves it). |
| **PeerCluster** | A set of nodes grouped by structural signature; `compare_peers` reports each attribute as `CONSTANT` or `VARYING`. |
| **RegionMatch** | The result of `resolve_phrase`: `rect`, `source` (how it was resolved), `confidence`. |
| **StyleSource** | The bridge from a pixel measurement to the `file:line` that governs it, with three-valued `effective`. |
| **Design spec** | A `*.spec.json` in `Resources/Rpa/Design/` declaring geometry invariants, palette roles, and `known_deviations`. |
| **Query corpus** | `Resources/Rpa/Design/queries/*.json` — the acceptance criterion; one entry per real query you have actually asked, paired with `expect_*` assertions. |

---

## 4. Architecture

### 4.1 Purity tiers

| Tier | Modules | Coverage |
| --- | --- | --- |
| Tier 1 — stdlib-only | `Vision/Scene.py`, `Vision/Region.py`, `Vision/Measure.py`, `Vision/Detectors.py`, `Vision/StyleSource.py`, `Vision/Report.py` | In the ≥90% branch gate |
| Tier 2 — cv2/tesseract | `Vision/Segment.py`, `Vision/Annotate.py` | Omitted from coverage (precedent: `Template.py`, `Ocr.py`) |
| Tier 3 — Qt-touching | `Service.py` extensions, `Driver.py` extensions | Omitted (existing) |

### 4.2 Dependency graph

`Scene.py` is the root. All other modules import it and nothing else within the feature.
The rule is one-directional: `Measure`, `Region`, `Detectors`, `StyleSource`, `Report` →
`Scene`; `Segment`, `Annotate` → `Scene`. No module outside `Vision/` imports cv2. No
module in the pure tier imports cv2 — enforced by the cv2-allowlist test (P3).

### 4.3 Dataclass placement rule

Every frozen dataclass in this feature (`Fill`, `Ink`, `Seam`, `Corner`, `Surface`,
`SceneNode`, `Scene`, `Gap`, `Hypothesis`, `Finding`, `PeerAttr`, `PeerCluster`,
`RegionMatch`) is defined in `Vision/Scene.py` and nowhere else. Function-only modules
cannot form circular imports against a data-only root. `SubRect` is driver wire data and
goes in `Types.py` (N-RPA-1).

---

## 5. Data Model

Full field lists are in `design-record.md §Data model`. This section states the load-bearing
invariants that tests must enforce.

**`Fill`**
- `kind`: `"flat"` | `"gradient_v"` | `"gradient_h"` | `"textured"`
- `visible`: `True` iff the fill presents a perceptually distinct edge. For a gradient, this
  is the **maximum** distance from `background_hex` across the ramp — not the mean. A band
  that straddles its background has a visible top/bottom edge and must not read the same as a
  uniformly invisible flat fill.
- `None` fill means not measured. `Fill(visible=False)` means measured, invisible. These must
  never be conflated.

**`SceneNode.measured`**
- A `frozenset[str]` drawn from `MEASURABLE = ("fill", "ink", "borders", "corners", "seams")`.
- `describe` attempts every entry per node and records the result. A property absent from
  `measured` renders as `not measured:` in `to_ascii()`. A detector may only conclude about
  a property present in `measured`.

**`Seam.shows_owner`**
- `"parent"` = the gap shows the direct parent's colour — a legitimate margin.
- `"ancestor"` = the gap shows a grandparent's colour — a hole through the widget hierarchy.
- These are opposite verdicts from identical pixel values; only `Region.flatten`'s accumulated-
  offset tree can distinguish them.

**`Finding`**
- `summary`: measurement only, no causal language.
- `hypotheses`: ranked candidate mechanisms, never asserted.
- `confirmed_by`: empty string until StyleSource resolves it; renders as `(pending)`.
- A finding with hypotheses and no `confirmed_by` is not actionable and must not read as though it is.

---

## 6. Activities

All six are read-only observers. All are `compensable=False`. All store into `ctx.extra[self.key]`; `postcondition` returns `self.key in ctx.extra` (idempotent).

| Activity | Key parameters | execute | postcondition |
| --- | --- | --- | --- |
| `Locate` | `phrase`, `fragment_path`, `text`, `region`, `key`, `threshold` | Resolves one of the four inputs to a `Rect` via the priority ladder; stores `RegionMatch` | `key in ctx.extra` |
| `DescribeScene` | `target`, `key`, `with_pixels`, `with_ocr`, `with_style` | Captures (synchronously), submits worker (if with_pixels); polls on subsequent pumps | `key in ctx.extra and ctx.extra[key].status == "ready"` |
| `Inspect` | `scene_key`, `key`, `detectors`, `spec_name` | Runs `Detectors.run_all` over the stored Scene — pure, <200 ms | `key in ctx.extra` |
| `MeasureSpacing` | `scene_key`, `key`, `axis`, `tolerance_px` | Runs gap measurement on all four bases | `key in ctx.extra` |
| `AssertDesignSpec` | `spec_name`, `key`, `scene_key`, `strict` | Compares scene against spec invariants; `strict=False` stores mismatches without raising | `key in ctx.extra` |
| `EmitVisionReport` | `scene_key`, `out_dir`, `key`, `annotate` | Calls `Report.emit`; `out_dir=""` uses `ctx.run_dir` | `key in ctx.extra` |

`DescribeScene.postcondition` calls `ctx.refresh_snapshot()` each pump (matching the `config_roundtrip.py:67` pattern). OCR at 300–3000 ms cannot run in `postcondition`; `execute` kicks the worker, `postcondition` polls the report registry. `max_attempts=2` gives a 10 s budget with `VERIFY_TIMEOUT_MS=5000`.

---

## 7. CLI — `tools/caissa-eyes`

A new entry point (not new subcommands on `tools/caissa-rpa`) because static-image commands must not require a running app. `tools/caissa-rpa` dies on a missing socket before dispatch; `caissa-eyes` per-command `needs_live_app` flag controls when the socket is checked.

| Subcommand | needs_live_app | Summary |
| --- | --- | --- |
| `ingest` | No | Decode newest pasted image from session transcript to PNG |
| `shot` | Yes | Capture, cropped to resolved region when `--phrase` given |
| `locate` | No* | Ground words or a crop to Rect + object_name + sub_rect |
| `inspect` | No* | Ground → describe → cluster → detect; ranked findings |
| `explain` | No | StyleSource bridge: `file:line` per finding with `effective` state |
| `verify` | No* | Re-run and diff; exit 0 only on two-sided pass |
| `regions` | Yes | List resolvable region names |
| `doctor` | No | cv2 / pytesseract / socket / transcript availability |

\* Live preferred; `--image PATH` accepted as fallback.

Default output format `--format agent`: findings only, ranked, ≤2 KB, last line starts `NEXT:`.

---

## 8. Skill — `.claude/skills/design-eyes/SKILL.md`

Trigger `description` enumerates your actual phrasings: "does not look right", "looks wrong",
"looks off", "spacing/padding/alignment uneven", "disconnected components", "doesn't look like
a group/tab group/page", "reads as a chip or tag", "title bar/caption/tab/panel/ribbon looks
wrong", "pasted screenshot + complaint", and "before/after changing a .qss file or paintEvent".

The body is the 7-step loop: (1) GET PIXELS before reasoning; (2) GROUND phrase to Rect or fail
loudly; (3) MEASURE; (4) READ FINDINGS — no source file yet; (5) RESOLVE to code via `explain`;
(6) FIX with Edit; (7) VERIFY two-sided pass. Hard rules: `(pending)` is not actionable;
never edit a `loaded_unmatched` or `matched_overridden` rule; an absent `measured` property
is not measured, not passing.

---

## 9. Classical Invariant Impact

Every new activity is read-only (`compensable=False`, no actuation). `classical` mode is
unaffected. The only additions that touch the running app are six `setObjectName` calls in
Phase 1 (prerequisite P5): `WBase.board`, `WBase.tb`, `WBase.pgn`, `MainWindow.pgn_information`,
and the splitter containers. These carry no behaviour change.

---

## 10. Phases

| Phase | Deliverable | Gate |
| --- | --- | --- |
| **0a** | `design-record.md` committed — DONE (PR #77) | File on main |
| **0** | Four SDD artefacts + P4 fix | Spec reviewed; P4 gate binding; seven corrections each have a named test in `feature_steps.md` |
| **1** | Prerequisites P1–P7; six `setObjectName` calls; `sub_rects`+`paint_overrides` in `QtDriver` | `make test` green; `visible_elements` on a 4-deep widget returns capture-absolute rect |
| **2** | `Scene.py` five primitives + `Measure.py` + `Report.py` | 6-tab literal: `perceived=[12,13,24,24,25] non_uniform`, `widget=[0,0,0,0,0] uniform`; `not measured:` line in `to_ascii` |
| **2b** | `Region.py` + five detectors + three seed corpus JSON files | `spacing_uniformity` passes notation tabs; `peer_adjacency` fires on ancestor seam; `fill_extent` silent on full-width captions |
| **2c** | `StyleSource.py` + generalise `QssRules.parse_rules` | `Caissa.qss:214` returns `loaded_unmatched`; `fritz-widgets.qss:290` returns `matched_overridden` |
| **2d** | DECISION GATE — run a real query, author 4th corpus JSON | Fourth `queries/*.json` exists; decision about deferred detectors recorded |
| **3** | `Segment.py` + `Annotate.py` + cv2 tests | `make test-cv` green with real assertions |
| **4** | Six activities + `rpa_describe`/`inspect`/`report` verbs + `QThreadPool` | `<200 ms` verb timing; main thread not blocked during OCR |
| **4b** | `tools/caissa-eyes` + `ingest` + `SKILL.md` + Phase 4b transcript gate | `--format agent` ≤2 KB; `NEXT:` line present; skill fires before any `.qss` grep |
| **5** | `ribbon.spec.json` + `panes.spec.json` + collapse six copies of design truth | Scorecard output byte-identical to pre-migration |
| **6** | `test_query_corpus.py` + `design_verify.py` workflow | All three+ corpus queries answered end-to-end from phrase alone |
| **7a** | Diagnose all corpus queries live; two-round design approval for notation-tab and pane-caption fixes | `design-approval.md` sign-off recorded — gates 7b |
| **7b** | Apply fixes + `caissa-eyes verify` + phase-exit `review.py --live` | Before/after reports in PR; `Caissa.qss:214` left untouched (it matches nothing) |

---

## 11. Constraints

Inherits N-RPA-1 through N-RPA-10 (see §2.3). Additional constraints N-RPAV-1 through
N-RPAV-5 are stated in §2.3. The normative N-RPA table is at
`docs/features/_archive/rpa-layer/feature_spec.md:53-64`; the corrected reading of N-RPA-9
("runtime `sys.modules`", not a source-location rule) is recorded in `design-record.md
§Standards conformance — The two mis-citations`.
