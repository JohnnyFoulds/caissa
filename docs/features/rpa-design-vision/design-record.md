<!--
  THIS IS A DESIGN RECORD, NOT A LIVE SPEC.
  It is committed verbatim as the first artefact of the rpa-design-vision feature,
  before any spec is written, because it contains empirical measurements, negative
  results, and the seven corrections (with the wrong answer next to the right one)
  that make the architecture make sense.

  Where this document and feature_spec.md disagree, feature_spec.md governs
  (sdd-workflow.md:32-34).  This document is intentionally first-person — the
  voice is what makes "my flagship detector passes query 3" carry its weight.

  Branch: feat/rpa-design-vision
  PR target: JohnnyFoulds/caissa  (NEVER lukasmonk/lucaschessR6)
-->

# Design Eyes — Local Machine-Readable UI Vision as RPA Activities

> **First step, before any code or any spec:** this document is committed to the repo verbatim as
> `docs/features/rpa-design-vision/design-record.md`. See [*Phase 0a*](#phase-0a--this-document-lands-in-the-repo-before-anything-else).

## Context

`docs/standards/ui-design-process.md` §2 already names this problem, as a reason Figma was rejected:

> *"An AI agent cannot reliably view its own exports from cloud-based design tools. The feedback loop becomes 'read JSON and reason about pixels I cannot see', which defeats the purpose of a visual review."*

The harness built to solve it (`tools/design/`) only half-solves it. It renders mockups in the shipping medium and produces side-by-side evidence, but the **judgement step is still a human looking at a picture**. Every measurement it makes is hard-coded to one widget at one width: `ribbon_report.py:187` scans `range(10, 80)` for the rule row, `:235` assumes the File tab lives in `x ∈ [2, 70)`, `:290` crops the reference at a literal `(0, 5, 820, 148)`. It cannot answer "is the gap between File and Home the same as the others" because it has no concept of an element, only of hard-coded boxes.

The goal is to close that loop **locally**: tesseract + OpenCV extract a symbolic description of what is on screen, and that description is complete enough that I reason about the UI without a cloud call to interpret the image. Annotated PNGs, crops and the HTML sheet remain — but as evidence for you, not as my input channel.

Two use cases drive it:

- **(a) Designing against a reference image** — the Fritz sign-off flow. Today the reference's measurements are transcribed by hand into prose and then hand-copied into two scripts.
- **(b) Interactive repair** — you paste a crop or describe a component in words; I locate it in the real UI, name the widget and QSS rule behind it, and cut my own reference crop.

### What I verified empirically before designing this

I ran the candidate techniques against the exact crop you pasted (105×28, dark variant). This materially changed the design:

| Technique | Result | Consequence |
|---|---|---|
| Colour-fill mask on `#007acc` | File tab fill = `Rect(4, 5, 43, 21)`, 811 px, exact | **Geometry comes from colour masking.** Deterministic, no tuning. |
| Connected components @ thr 150, on the File tab | Exactly 4 glyph blobs — `F`(17,11,5,8) `i`(23,11,2,8) `l`(26,11,1,8) `e`(29,13,5,6); ink span x=17–34 | Left padding 13 px, right padding 12 px — matches `padding: 4px 13px` (`fritz-widgets.qss:282`). **CC isolation works.** |
| `pytesseract` default PSM 3 — *what `Vision/Ocr.py` uses today* | **Found nothing at all** | Existing `find_phrase()` is unusable on small UI crops. |
| PSM 11 (sparse text) | `File` @ conf 95 | PSM must be configurable. |
| Any PSM, for `Home` | conf 0, or missed entirely | `find_phrase`'s default `confidence_threshold=50.0` rejects it outright. See the polarity note below. |
| Global colour bbox for `#ffffff` | **Wrong** — x=18…99, merging Home's white *fill* with File's white *glyphs* | `fill_regions` MUST use `connectedComponentsWithStats` + `min_px`, never a global bbox. |
| Same, with CC + `min_px=32` | Exactly one component: `Rect(48, 6, 52, 20)` | Contamination gone. Correct. |

**Why `Home` resisted detection, and the lesson in it.** My first reading was "low-contrast dark-on-dark text". Colour sampling disproved it: `Home` is the *selected* tab — `#005b99` text on a `#ffffff` fill. A CC threshold of 150 therefore made the white fill *foreground* and the dark text *background*, i.e. **inverted polarity**, so the glyphs vanished. `glyph_boxes` must detect polarity per region (compare glyph-candidate luminance against that region's dominant fill) rather than assume dark-on-light. A single global threshold silently fails on every selected or inverted element.

**The load-bearing conclusion: geometry from colour + connected components (deterministic); identity from OCR (best-effort, must degrade gracefully).** My first instinct was to anchor measurements on OCR-located text. That is backwards — OCR failed on one of the two elements here while colour segmentation nailed both to the pixel. An OCR-first layer would silently fail on exactly the dark-theme, inverted-state cases where you most need it.

### The finding that broke my first design: three bases are not enough

Your crop has two tabs, so it has exactly **one** gap. A uniformity check over one sample is meaningless, and I did not notice that. A second probe rendered the full 6-tab bar (`File Home Board Analysis Engine View`, `currentIndex=1`, real `fritz-widgets.qss`) and the result invalidates the design I had written:

```
idx  label     tabRect              fill                      ink span
 0   File      (  0,0, 46,25)       #007acc          VISIBLE    13.. 32
 1   Home [*]  ( 46,0, 60,25)       #ffffff +border  VISIBLE    58.. 93
 2   Board     (106,0, 59,25)       palette(Window)  INVISIBLE 118..151
 3   Analysis  (165,0, 72,25)       palette(Window)  INVISIBLE 175..225
 4   Engine    (237,0, 64,25)       palette(Window)  INVISIBLE 249..288
 5   View      (301,0, 53,25)       palette(Window)  INVISIBLE 313..341
```

| pair | widget gap | fill gap | ink gap |
|---|---|---|---|
| File→Home | 0 | 0 | 25 |
| Home→Board | 0 | *undefined* | 24 |
| Board→Analysis | 0 | *undefined* | 23 |
| Analysis→Engine | 0 | *undefined* | 23 |
| Engine→View | 0 | *undefined* | 24 |

`QTabBar` tabs abut, so **every widget gap is 0 — perfectly uniform**. Ink gaps are 23–25 — also uniform. And `fill` yields one defined gap out of five, which my `is_uniform` would have called uniform on a single sample. **All three of my bases report "nothing wrong."** My plan would have contradicted your eye and told you the spacing was fine.

What reproduces your complaint is a **fourth, derived basis — perceived separation**: the distance from a label's ink edge to the nearest *visible* boundary on that side, falling through to the neighbour's ink when no fill or border edge exists there.

| label | nearest visible boundary to its left | perceived |
|---|---|---|
| Home | File's `#007acc` fill edge / own `#9daab8` border @ 46 | 58−46 = **12** |
| Board | Home's `#9daab8` border @ 105 | 118−105 = **13** |
| Analysis | none (Board's fill invisible) → Board's ink @ 151 | 175−151 = **24** |
| Engine | none → Analysis ink @ 225 | 249−225 = **24** |
| View | none → Engine ink @ 288 | 313−288 = **25** |

**12, 13, 24, 24, 25 — a 2.08× spread.** That is exactly the unevenness you reported, and it is invisible to all three of my original bases. The mechanism: only the two *painted* tabs present hard edges, so their neighbours read as half as far away, while transparent tabs offer nothing for the eye to measure from until the next glyph.

So `Fill` gains a **`visible`** boolean (fill hex vs the local background hex, not a global constant), and `Measure` gains `perceived_gaps()`. This is now the binding basis; the other three are corroboration. Two consequences for the rest of the plan:

- **`Finding.verdict` is `non_uniform` if *any* basis says non-uniform**, and basis disagreement is itself promoted to a finding. Averaging the bases, or picking one, reproduces the original failure.
- My earlier `"adjacent-filled-tabs"` finding was correct but **partial** — it explains `File│Home` and nothing else. The real statement covers all five boundaries.

These absolute pixel values come from an offscreen clone that did **not** go through `tests/conftest.py::_bootstrap()` and emitted `missing font family "Sans Serif"` warnings, so fonts differ from the real app. **Every number above must be re-measured through `_bootstrap()` or the live app before it is committed to a spec or a fixture.** The relative finding — a ~2× spread driven by fill visibility — is font-independent and will hold; the exact pixels will move.

### A fourth real bug, found on the way past

Measured tab widths equal `advance(text, 8pt) + 26` (File 19+26≈46, Analysis 46+26=72, View 26+26≈53). That is because `tabSizeHint` is computed by the stylesheet style using `font-size: 8pt` from `fritz-widgets.qss:285`, while `_FlatTabBar.paintEvent` draws with `self.font()` — set to **10pt** at `WRibbon.py:703`. Glyphs are 3–5 px wider than the width budgeted for them, so effective side padding shrinks from the authored 13 px to roughly 10.5–12 px, **and does so by a different amount per label**. That is an independent second contributor to the unevenness, and it is precisely the class of defect only a multi-basis report surfaces.

Three further defects this surfaced:

- `tools/design/compare.py:115` `chrome_mask` and `ribbon_report.py:49` `TARGET` hard-code the **light** palette (`#efeff2`, `#cccedb`). Your crop is the dark variant (`#252526`). Both silently return garbage on dark input. The palette must be theme-parameterised.
- Copies of the ribbon design truth exist and **disagree**: `docs/fritz/ribbon.md` prose, `ribbon_report.py:49` `TARGET`, `tools/design/elements.py:52` per-element targets. File-tab fill is `#005b99` in one and `#007acc` in another; caption is `#444444` vs `#1e1e1e`. A measurement layer aimed at a contradictory spec is worthless, so collapsing these is in scope.
- **The QSS colour rules for the ribbon tabs are dead code — and I initially blamed the wrong file.** `_FlatTabBar` (`WRibbon.py:110`) takes full `paintEvent` ownership and fills every tab from seven hardcoded Python constants at `WRibbon.py:118-124` (`_BG_FIRST = #007acc`, `_FG_SEL = #005b99`, `_BORDER_SEL = #9daab8`, …). So the `::tab:first` / `::tab:selected` / `::tab:hover` colour rules never render anything. It is an E1 violation of `ui-design-process.md` §7 (*"a `#RRGGBB` literal in a widget module is permitted only as a `QtCore.Property` default"*), and it explains the `#005b99`/`#007acc` doc contradiction: those are two different things (`_BG_FIRST` fill vs `_FG_SEL` selected-text) that the prose conflated.

  My first draft named `Fritz.qss:1015` as the dead rule. **That is not the live rule.** For any mode with a `ribbon` key, `InitApp._apply_fritz_overlay` (`InitApp.py:130-144`) reads `Resources/Styles/fritz-widgets.qss`, substitutes every `{KEY}` from `Code.dic_colors`, and **appends** it to `app.styleSheet()`. `fritz-widgets.qss:288-321` carries its own `::tab:first` / `::tab:selected` / `::tab:hover` block, arriving *last* and therefore winning on equal specificity. So there are two authored QSS copies, the appended one governs, and **both are then defeated by `paintEvent` anyway.**

  `paintEvent` does **not** override `tabSizeHint`, so tab *widths* still come from `padding: 4px 13px` (`fritz-widgets.qss:282`) via the style — which is why my measured 13/12 px padding matched. Geometry from QSS is effective; colour from QSS is not.

  This is the whole justification for the feature, stated sharply: my own first attempt at the pixels→code bridge sent you to **the wrong line in the wrong file for a rule that does nothing.** If I get that wrong reasoning by hand, I will get it wrong every time. The bridge must resolve to whichever source actually governs, name the overriding `paintEvent`, and mark inert QSS as inert.

### The second query, which broke the plan again: *"the title bars in the side panel do not look right to me"*

You gave me a full-window screenshot and that sentence. My plan could not have answered it, and the reasons are structural rather than missing detail. Here is what I actually concluded from the pixels, then what the plan lacked to get there.

**The diagnosis I reached from pixels only.** Four panes — Players, Engine analysis, Eval profile, Notation — each with a caption at its top-left. Left edges align, so alignment is fine. What looked wrong: **each caption's fill appeared sized to its text rather than to its pane** — "Players" a ~40 px chip, "Engine analysis" ~95 px — so they read as small tags rather than title *bars*; caption/body contrast was low; and "Notation" appeared twice in ~25 px of vertical space, once as the caption and once as the first tab beneath it.

**Then I read the code, and my mechanism was wrong.** This is the single most instructive thing in this plan, so it goes in rather than getting quietly fixed:

`_PaneTitleBar` (`WFritzPane.py:163`) is a `QWidget` added to a zero-margin `QVBoxLayout` (`:116-120`), and its `paintEvent` (`:257-272`) fills **`self.rect()`** — the entire width — with a vertical gradient from `qproperty-titleTop` to `qproperty-titleBottom`. **The title bar already spans the pane.** It is full-width, exactly as designed.

The reason it does not look like it: with `x_style_mode='Caissa'`, `fritz-widgets.qss:197-214` resolves through `Caissa.colors` to `titleTop = #252526`, `titleBottom = #363636`, over a pane `background-color` of `#2d2d2d`. **The gradient ramps from below the pane colour to above it, crossing it in the middle.** Mean band colour ≈ `#2d2d2e`; pane body `#2d2d2d`. The band is one unit away from its own background. It is painted, full-width, and invisible — so the only thing that reads as a header is the bold text, and I inferred a text-shaped fill from a text-shaped visible area.

Two more things fall out of the same read, neither of which I saw at all:

- **The ▾ menu and ✕ close buttons are missing from the screenshot.** They exist in code (`:184`, `:193`, `setFixedSize(16, 16)`) and in the approved design (`design-approval.md:86`). `Caissa.qss:83-92` gives every `QToolButton` `padding: 8px; min-width: 32px; min-height: 32px`, fighting a 16 px fixed size inside a 20 px band.
- **The shipped widget diverges from the signed-off mockup.** `fritz_mock.py:225-317` — the artefact you approved — uses `TITLE_H = 22`, `PAD_X = 8`, dark gradient `#3a3a3c → #2d2d2f`. Shipped: `titleHeight: 20`, `titlePadX: 6`, and a gradient that runs **light-downward instead of dark-downward**. The mockup also puts `objectName="WFritzPaneTitle"` on the *label*; the shipped code puts it on the *container* and names the label `WFritzPaneTitleLabel`, **for which no QSS rule exists anywhere in the repo.**

#### Why being wrong here is the most useful result in this document

My symptom was right, my mechanism was wrong, and **pixels alone cannot distinguish the two hypotheses** — "the fill is text-width" and "the fill is full-width but matches its background" produce an identical screenshot. Three consequences, all of which change the plan:

**1. Both of your queries are the same bug.** The ribbon tabs are painted with `palette().window()`, which equals the surrounding background, so they present no visible edge. The pane captions are painted with a gradient whose midpoint equals the pane background, so they present no visible edge. `Fill.visible` — the field I added for the ribbon — is the detector for both. That convergence is strong evidence the concept is right, and it means the highest-value detector is not `fill_extent` at all but **`invisible_fill`: an element is painted, its fill differs from its declared background by less than a perceptual threshold.** I had this as a *field* supporting a spacing check; it should be a *detector* in its own right, and on this evidence the most productive one in the set.

**2. `Segment` assumes flat fills, and the Fritz design is gradient-based.** `fill_regions(img, hex_colour, tol=10)` looks for a single colour. A vertical ramp `#252526 → #363636` spans ~17 levels across 20 rows and matches no single hex, so `fill_of` on that band returns garbage or nothing — and the report would say "no fill measured", which reads as *absent* rather than *invisible*. Since `qproperty-titleTop`/`titleBottom` is the documented E1 contract for panes (`docs/fritz/qss-contract.md:30-67`), gradients are not an edge case in this codebase, they are the house style. **`Fill` must therefore model gradients as a first-class kind**, carrying `kind` (`flat` | `gradient_v` | `gradient_h` | `textured`), `hex_start`/`hex_end` endpoints sampled at the band's extremes instead of a single `hex_color`, and a `visible` boolean derived from the ramp — the full field list is in *Data model* below.

The decision hiding in that last field: `visible` for a gradient is the **maximum** distance from the background over the ramp, not the mean — a band that starts darker and ends lighter than its background has a visible top and bottom edge but no visible middle, which is a different defect from a uniformly invisible band and must not read the same.

**3. A pixel-only report must state its mechanism as a hypothesis.** Had my report asserted "the fill is sized to its text", it would have sent me to add `setSizePolicy`/stretch to a widget that already spans the pane — a wrong fix that would have changed nothing and cost an hour. So `Finding` needs the measurement and the explanation kept apart: `summary` states what was measured, `hypotheses` lists candidate mechanisms ranked, and `confirmed_by` records what resolved it. The `StyleSource` bridge is what promotes a hypothesis to a cause, which means **step 5 of the trace is not optional garnish — it is what makes steps 1–4 safe to act on.**

**Now the structural problem.** Compare the shape of that query with the ribbon query the plan was built around:

| | Ribbon query | Side-panel query |
|---|---|---|
| Input | a 105×28 crop you cut for me | the **whole window**, 1352×956 |
| Region reference | implicit — the crop *is* the region | **verbal: "the side panel"** |
| Elements | adjacent siblings in **one** parent | one element each in **four different** parents |
| Comparison | gaps between neighbours along x | **peer attributes** across a class |
| Defect class | spacing uniformity | fill-width-vs-container, contrast, duplication |
| Detector needed | `reconcile()` (spacing) | none of the above |

Every column differs. The plan's `Locate(text=...)` cannot resolve "the side panel" (it is not a label on screen). Its `MeasureSpacing(selector, axis="x")` measures the wrong thing — the captions are not adjacent and the defect is not spacing. And `reconcile()`, which I called "the highest-value function in the feature", would return **no findings at all** on this scene, because the only detector it implements is gap uniformity.

So the honest statement is: **I designed a ribbon-tab-spacing analyser and called it eyes.** It generalises along the axis I happened to be looking at and not along any other. Three capabilities are missing, and they are the difference between the two use cases working and only one working.

#### Missing capability 1 — spatial grounding: turning *"the side panel"* into a `Rect`

There is no on-screen text reading "side panel", so no OCR path reaches it. It has to come from structure. Two sources, tried in order, neither of which the plan has:

- **From the widget tree.** The main window is split into containers; their `objectName`s and geometry identify them. A phrase lexicon maps human vocabulary onto them: `side panel | right panel | panel column → the right-hand splitter child`; `board → the board widget`; `ribbon | toolbar → the ribbon`; plus purely geometric terms `top | bottom | left | right | top-right` resolving to window fractions.
- **From pixels, when the tree is unhelpful.** Long straight border runs and large uniform fills decompose the capture into rectangular regions; the phrase then selects among them positionally. This is the fallback for custom-painted containers, and it is the same class of operation as `row_bands` generalised to two dimensions.

This is `Vision/Region.py`, and it is the inverse of the `owner_of` bridge the plan already has. `owner_of` goes *pixels → widget*; this goes *phrase → region → nodes*. I had only built the direction that starts from a crop, which is why a verbal query had nowhere to enter.

#### Missing capability 2 — peer clustering: turning *"the title bars"* (plural) into a comparable set

The four captions are not siblings. They live in four different parents, and what makes them a set is that they are **the same kind of thing in the same structural position** — first child, top of a pane, short text, a distinct fill. Reasoning about "the title bars" means finding that class and then asking what varies across it.

`Measure.peers(scene)` clusters nodes by a signature — `(role, parent role, index within parent, height bucket, fill hex bucket, font size)` — and `compare_peers(cluster)` reports each attribute as *constant across the cluster* or *varying*, with the values. The finding writes itself from that table:

```
peer cluster "pane_caption"  n=4  parents=[Players, Engine analysis, Eval profile, Notation]
  left_edge      CONSTANT  755
  height         CONSTANT  14
  fill_hex       CONSTANT  #3c3c3c
  fg_hex         CONSTANT  #a0a0a0
  width          VARYING   40, 95, 68, 52        <- tracks label text length
  width/parent_w VARYING   0.07, 0.17, 0.12, 0.09  <- and not the container
```

That is the whole diagnosis, and note it needed **no reference image and no code** — it is an internal-consistency argument, the same trick that made the ribbon finding work. The generalisation I missed: *the strongest signal available locally is that things which should match, don't.* The plan applied that idea to gaps only.

Peer clustering is also what makes a whole-window scan produce something readable. I had claimed a `findings`-verbosity whole-window mode without saying how it would find anything; clustering is the answer, because a class of 40 buttons collapses to one row and one finding rather than 40 nodes of text.

#### Missing capability 3 — a detector registry, because spacing is one defect class out of many

`reconcile()` must stop being the top-level entry point. It becomes *one* detector. The top level is a registry of pure predicates over a `Scene`, each emitting `Finding`s, each independently unit-testable from literals:

The five with evidence behind them, which are the only ones Phase 2b ships (the canonical registry, including the four findings that non-detector layers emit, is in *Public API* below):

| Detector | Question | Evidence |
|---|---|---|
| **`invisible_fill`** | is an element painted with a fill perceptually indistinguishable from what it sits on? | **all three queries** — `palette().window()` tabs, gradient captions, ΔE=2 tab selection |
| **`peer_adjacency`** | do group members whose role implies contiguity actually touch, and what shows through if not? | **query 3**, which `spacing_uniformity` passes |
| **`surface_broken`** | enumerate every way a spec'd `Surface` (tab + its content) fails to be one continuous plane — corners, seam, fill | **query 3 + 3b** — 4 breaks in one widget; was `group_continuity` |
| **`orphan_style_rule`** | does a QSS selector name a widget type present nowhere in the tree? | **query 3b** — `QTabWidget::pane` across 8 theme files |
| `spacing_uniformity` | are gaps between peers even, on all four bases? | **query 1** |

And the eight speculative ones, deferred to Phase 7 and written only when a real query needs them:

| Detector | Question | Status |
|---|---|---|
| `contrast` | fg vs its *local* fill, as a luminance ratio | fired on query 2, for an unexpected reason |
| `missing_child` | does a spec'd child element have no measurable node? | fired on query 2 (the absent ▾ ✕ buttons) |
| `text_duplication` | does the same string appear twice within one region? | fired on query 2 as `[info]` |
| `fill_extent` | does a fill span its container where its role implies it should? | **wrong on query 2**, minor on query 3 |
| `peer_divergence` | which attributes vary across a peer cluster that should be constant? | silent on 2 and 3 |
| `edge_alignment` | do peers share left/top/right/baseline edges? | never fired |
| `containment` | does content cross its container's border? | never fired |
| `theme_blindness` | do fills track the active palette, or are they literals? | **fired on query 1** — the 7 `QColor` constants at `WRibbon.py:118-124`. Deferred anyway: it is a static source check that needs no `Scene`, so it is independent of the primitives and can land any time |

**`invisible_fill` fires on all three queries, in three unrelated widgets, via three different paint paths** — `_FlatTabBar.paintEvent` using `palette().window()`, `_PaneTitleBar.paintEvent` using a background-straddling gradient, and a QSS rule declaring `:selected` identical to the base. That is the one concept in this feature I am now confident about.

The split is deliberate and it is the main structural lesson of the three queries: **three of my eight speculative detectors have never fired on any query, and the one I ranked first was wrong on the query it was built for.** Guessing detector sets from a single example does not work. Building the primitives and letting real queries pull detectors out does.

`missing_child` is the ninth, added because the ▾ ✕ buttons are absent from your screenshot and **no detector in my list would have noticed.** Every other detector reasons about nodes that exist. Detecting an element that *should* be there and isn't requires the spec side — `panes.spec.json` declaring `children: ["menu_button", "close_button"]` — and it is a cheap, high-value check precisely because absence is invisible to every pixel measurement.

The architecture survives all of this, which is the reassuring part: detectors are pure functions over `Scene`, so adding one costs a function and a test, and the `Scene`/`Fill`/`Ink`/four-basis model underneath does not change.

`fill_extent` needs one thing the data model lacks: a **role expectation**. Knowing that a caption *ought* to span its pane is not derivable from pixels — it is a design rule. It comes from the spec (`"role": "caption", "fill_extent": "container"`), which is exactly what `ribbon.spec.json` and its `invariants` list are for, generalised beyond the ribbon. Without that, `fill_extent` can only report the fact ("width tracks text, not container") and leave the judgement to you — which is still useful, and is the honest default when no spec entry exists.

#### What this changes about how the feature is judged

You said: *"you will need multiple tests like this."* Agreed, and it should be the acceptance criterion rather than a nice-to-have. The feature is not measured by unit coverage; it is measured by **whether it answers real queries you have actually asked**. So a query corpus becomes a first-class artefact — our own renders (no §9 copyright issue), each paired with the verbal query and the finding that must come out on top. The two you have given me are the first two entries, and both are cases my plan failed: the first because I had too few bases, the second because I had one detector and no way in from a sentence.

And the loop you described — *see → understand → read code → fix → re-measure → confirm* — becomes a named workflow with a stored baseline, whose pass condition is that the targeted finding is **gone** and no new finding has appeared. That is the part that turns this from a reporting tool into something that can close a design defect.

### The third query, which broke the flagship detector: *"the tabs in the notation panel look like disconnected components"*

This time I captured the screenshot myself — `screenshot /tmp/q3-notation.png` over the existing control socket, which worked first try and is worth noting as evidence that the *capture* half of this feature already exists. Then I measured, **without reading any code**, and this is what came out:

```
tab strip  y=485..516   five tabs, x: 717..796  800..876  880..980  984..1103  1107..1196
                                            └─2─┘    └─2─┘    └─2─┘     └─2─┘
gap columns  x=797,798 / 877,878 / 981,982 / 1104,1105  →  ALL #1e1e1e
past last tab  x=1197..1275 (79 px)                     →  #1e1e1e
```

Three measurements settle it:

- **Every tab is a closed 1 px `#363636` rectangle.** Vertical scan through the selected tab at x=750: border at y=485, body, border at y=516. Same at x=840. All four sides, every tab.
- **The 2 px gaps show `#1e1e1e`** — and `#1e1e1e` is the *window* background, not the tab strip's `#252526`. The strip has no fill of its own, so the gaps are holes through to the grandparent. Confirmed by the 79 px past the last tab also reading `#1e1e1e`.
- **The selected tab is closed off from its own pane.** At x=750 the accent `#228df2` sits at y=514–515, and then `#363636` at y=516 — *inside* its own closed bottom border. Its fill is `#272728` against unselected `#252526`: ΔE = 2.

So: five identically-bordered closed boxes, floating on the window background with 2 px of nothing between them, one carrying a blue underline. **That is a segmented button row, not a tab group.** The word "disconnected" is literally accurate — nothing connects to anything.

**Then I read the code, and this time the mechanism was right — because I checked before asserting it.** `Resources/Styles/Caissa.qss:220-236`:

```qss
QTabWidget::pane      { border: 1px solid #363636; top: -1px; }
QTabBar::tab          { background-color: #252526; border: 1px solid #363636;
                        padding: 6px 14px; margin-right: 2px; ... }
QTabBar::tab:selected { background-color: #252526; color: #d6d6dd;
                        border-bottom: 2px solid #228df2; }
```

Every measurement maps to one declaration: `margin-right: 2px` (`:226`) is the gap; `border: 1px solid #363636` (`:224`) is the closed box; `border-bottom: 2px solid #228df2` (`:235`) replaces the selected tab's bottom border with a *different* closed border instead of opening it; and `:233` declares the selected background **identical to `:222`**, so selection carries no fill signal at all. `QTabWidget::pane { top: -1px }` (`:217`) is the correct Qt idiom for merging pane and tab bar, and it cannot work while the selected tab keeps an explicit bottom border. `QTabBar` itself has no `background-color` rule, which is why the gaps show the window through.

#### Why this one matters most: my flagship detector passes it

`spacing_uniformity` — the detector I called "the one to write first", built from query 1, carrying the four-basis model that was the centrepiece of the whole plan — **measures gaps of 2, 2, 2, 2 and reports `uniform`. It passes.** Every basis passes: widget 2,2,2,2; fill 2,2,2,2; ink uniform; perceived uniform.

That is the sharpest lesson in the three queries, and it is not a missing detector, it is a **wrong predicate**. I built the feature around *uniformity* because query 1 happened to be an unevenness complaint. But the defect here is that a perfectly uniform gap **should be zero**. Uniformity cannot express "should be zero" — a set of identical wrong values is maximally uniform. Of my ten detectors, `invisible_fill` fires (on the ΔE=2 selected fill) and `fill_extent` fires (on the strip not spanning its container), and **both are real but minor**; neither says "the tabs don't touch." The top-ranked finding would have been about the wrong thing.

#### The missing primitive: a seam is not a gap

The structural reason is that every one of my ten detectors measures either *a property of a node* or *a comparison between nodes*. Both facts that matter here are properties of the **boundary between** two nodes:

- "these should be touching" — about the gap itself, not either tab;
- "this border should be open" — about the shared edge between the selected tab and its pane.

`Gap` carries only `basis`, `px` and `undefined_reason`. It cannot say *what is visible in the gap*, which is the whole point: a 2 px gap showing the parent's own background is a legitimate design choice, and a 2 px gap showing the **grandparent's** background is a hole. Same number, opposite verdicts. So `Scene` gains a third primitive alongside `Fill` and `Ink`:

```python
@dataclass(frozen=True, slots=True)
class Seam:
    """The shared boundary between two adjacent nodes, or a node and its container."""
    before_id: str
    after_id: str
    axis: str                     # "x" | "y"
    px: int                       # 0 = the nodes touch
    shows_hex: str = ""           # what is actually visible in the gap
    shows_owner: str = ""         # "parent" | "ancestor" | "unknown" — the verdict-changing field
    closed: bool = False          # is there a continuous border run across the seam
    border_hex: str = ""
```

`shows_owner` is the field that does the work, and it is only computable because `Region.flatten` (P5) gives every node a capture-absolute rect and a parent chain: compare `shows_hex` against the parent's measured fill, then walk up. **A 2 px gap in the parent's own colour is a margin; a 2 px gap in an ancestor's colour is a hole.** No per-node measurement can tell those apart.

Two new detectors follow, taking the running count from ten to twelve:

| Detector | Question | Catches |
|---|---|---|
| `peer_adjacency` | do group members whose role implies contiguity actually touch — and if not, what shows through? | **this bug**; `spacing_uniformity` passes it |
| `surface_broken` | does the selected member of a group share an *open* edge with its content pane, and match its fill? | **this bug**; the closed `border-bottom` and the ΔE=2 selection |

(I first drafted the second one as `group_continuity`. Two sections below, the corner finding forces it to generalise from "is this edge open" to "enumerate every way this surface fails to be one plane", and `surface_broken` is the name it keeps. It is one detector under two names, not two detectors — the tally stays at twelve here and reaches thirteen when `orphan_style_rule` arrives.)

`surface_broken` is the one that needs the container's role from the spec (`"role": "tab_group"`), because "the selected tab should open into its pane" is a design convention, not a pixel fact. That is the same role-expectation mechanism `fill_extent` already needed, so it costs no new machinery — which is mildly reassuring about the shape of the model even as its detector list grows.

#### What I missed entirely: corner geometry, and the page it breaks

You pointed out that the content area has **rounded corners**, and that this is the main problem — because in UX terms a tab plus its content is one solid thing, a *page*, so when the first tab is selected the content's rounded top-left corner sits directly beneath it and cannot be rendered rounded. I had not measured corners at all. I measured borders, fills, gaps and seams, and reported none of it.

I went back to the same capture and measured. **You are right, and it is worse than rounded corners.**

```
vertical scan x=717..721, y=485..523      (arc pixels walk diagonally = anti-aliased radius)
  y=485  x717 #1e1e1e   x719 #2d2d2d   x721 #343434
  y=486  x718 #363636                          }  6 px arc — the TAB's border-top-left-radius
  y=487  x717 #363636                          }  (Caissa.qss:227)
  ...
  y=516  x717..720 #1e1e1e                     }
  y=518  x719 #363636                          }  8 px arc — the CONTENT's top-left corner
  y=519  x718 #363636                          }
  y=524  x716 #363636  (left border proper begins)

pane top border   y=516  #363636 runs x=724..1271   (starts 8 px in from the left edge)
pane left border  x=716  #363636 runs y=524..851    (starts 8 px down from the top edge)
```

An 8 px radius on both axes, and the notch it carves — `x=716..723, y=516..523` — is filled with `#1e1e1e`, the **window** background, directly beneath the selected first tab (`x=717..796`). The page has a bite taken out of it exactly where the selected tab is supposed to flow into it.

**Then I queried the live widget tree, and the structural finding is bigger than the visual one.** `dump_ui 12` over the control socket, matched against the pixels:

```
MainWindow                                    (331,115,1280,860)
  QWidget #WFritzOuterContainer               (0,0,1280,860)
    QSplitter                                 (0,146,1280,714)
      QSplitter                               (716,0,564,714)     → abs x=716  ✓ left border
        WFritzPane                            (0,319,564,395)
          _PaneTitleBar                       (0,0,...)
          QWidget #WFritzNotationContainer    (0,20,564,375)      → abs y=485  ✓ tab strip
            QTabBar #WFritzNotationTabBar     (0,0,564,31)        → abs y=485..515  ✓
            _FlowingNotation                  (0,31,564,344)      → abs y=516..859  ✓
```

Every pixel boundary I measured maps onto a widget edge. And the decisive fact:

> **`QTabWidget` does not appear anywhere in the application's widget tree.**

The notation "tab group" is `modern_fritz_ui.py:168-188` — a plain `QWidget` with a zero-margin `QVBoxLayout` holding a **bare `QTabBar`** (`:175`, with `setDrawBase(False)` at `:178`) and, as an unrelated sibling, `_FlowingNotation`, which `:109` declares as `class _FlowingNotation(QtWidgets.QTextEdit)`. So the 8 px radius is `QTextEdit { border: 1px solid #363636; border-radius: 8px }` at **`Caissa.qss:165-173`** — a generic input-widget rule, inherited by subclass matching, applied to all four corners because nothing ever told it this widget is a tab page.

Which means **`QTabWidget::pane { border: 1px solid #363636; top: -1px; }` at `Caissa.qss:214-218` matches nothing at all.** In my previous write-up I called `top: -1px` "the correct Qt merge idiom, defeated by the explicit `border-bottom`". That was wrong in a more fundamental way than I realised: it is not defeated, it **never runs**. There is no pane. The one declaration in the stylesheet whose entire job is to join a tab bar to its content is dead code.

So "it looks like disconnected components" is not a rendering accident. **The widgets *are* disconnected components** — a tab bar with its base disabled, and a text editor styled as a text editor, stacked in a box layout with no tab-group relationship between them. The QSS is faithfully rendering the structure it was given.

#### This breaks my `StyleSource` bridge, not just my detectors

My `effective` test was: *"a rule is only reported `effective: true` if its resolved text is actually found in `QApplication.styleSheet()`."* I called that "cheap and decisive."

It is cheap and it is **wrong**. `QTabWidget::pane` is in the stylesheet string, so that check returns `effective: true`, and the bridge would have sent me to `Caissa.qss:214` to fix the tab/pane merge — a rule that no widget in the application matches. That is my original `fritz-widgets.qss:290` mistake in a new costume: presence in the stylesheet proves the rule was **loaded**, not that anything **matches** it. So `effective` becomes three-valued:

| Value | Meaning | How it is decided |
|---|---|---|
| `loaded_unmatched` | in the stylesheet, but no widget of that type exists | selector's type name absent from the flattened widget tree |
| `matched_overridden` | a widget matches it, but `paintEvent` wins | `paint_overrides` on the matching class |
| `effective` | a widget matches and nothing overrides it | neither of the above |

and a new detector falls out, which is the cheapest one in the set and would have caught this at authoring time:

| Detector | Question | Catches |
|---|---|---|
| `orphan_style_rule` | does a QSS selector name a widget type that exists nowhere in the tree? | **`QTabWidget::pane`** — 4 dead declarations across 10 theme files |

That is a whole-tree query needing no pixels, and it generalises: every theme in `Resources/Styles/` carries a `QTabWidget::pane` block (`Dark.qss:49`, `Fritz.qss:203`, `Mid.qss:57`, `Midnight.qss:203`, `Modern Fritz.qss:203`, `Daylight.qss:203`, `DOS Fritz.qss:200`, `Win95 Fritz.qss:242`), and **all of them are dead** for as long as the app builds tab groups by hand.

#### The fourth primitive: `Corner`, and the surface that spans two widgets

`Fill`, `Ink` and `Seam` cannot express any of this. A corner radius is not a fill, not ink, and not a boundary between peers — it is the geometry of one node's border at one of its four corners, and it is only *wrong* in relation to a **different** node that is supposed to be part of the same surface.

```python
@dataclass(frozen=True, slots=True)
class Corner:
    """One corner of a node's border, measured from the arc's pixel staircase."""
    which: str            # "tl" | "tr" | "bl" | "br"
    radius_px: int        # 0 = square; measured, not read from QSS
    shows_hex: str = ""   # what fills the notch outside the arc
    shows_owner: str = "" # "parent" | "ancestor" — an ancestor colour means a visible bite
```

`radius_px` is measurable without any style knowledge: walk in along both edges from the corner until the border run becomes continuous; the offset is the radius. `shows_owner` reuses the `Seam` machinery — the notch here shows `#1e1e1e`, an **ancestor** colour, which is exactly what makes it read as a bite out of the page rather than as a soft corner on a floating card.

And the relation your reasoning depends on needs a name, because it spans two nodes that are not peers:

```python
@dataclass(frozen=True, slots=True)
class Surface:
    """Nodes that a design convention says render as one continuous plane."""
    surface_id: str
    member_ids: tuple[str, ...]   # ("tab[0]", "notation_content")
    role: str                     # "tab_page"
    joined_at: Seam | None        # the boundary they must merge across
    breaks: tuple[str, ...] = ()  # "corner_tl_radius_8", "seam_closed", "fill_mismatch"
```

`Surface` is where the UX rule lives — *a tab and its content are one page* — and it is a spec-supplied role, not a pixel fact, the same way the previous section's detector already needed `"role": "tab_group"`. **This is where `group_continuity` becomes `surface_broken`:** it stops being "does the selected tab share an open edge with its pane" and becomes **"enumerate the ways this `Surface` fails to be one plane"**, of which there are now four in this one widget, and the corner is the one that reads worst:

```
FINDINGS
  [warn] surface_broken  tab_page(tab[0] + notation_content)   4 breaks
    corner   notation_content.tl radius 8 px, notch shows #1e1e1e (ancestor)
             — directly beneath the SELECTED tab. A page cannot have a bite
               taken out of it where its own tab meets it.
    corner   notation_content.tr radius 8 px, same notch
    seam     tab[0] bottom edge CLOSED (#228df2 border) — does not open into content
    fill     tab[0] #272728 vs content #252526 — ΔE 2, no selection signal
    => The tab and its content are not one plane. They are two independently
       styled widgets that happen to be adjacent.
    hypotheses (ranked):
      1. no QTabWidget exists; content is a QTextEdit inheriting a generic
         8px input-widget radius                                        [likely]
      2. QTabWidget::pane radius authored but not zeroed for the first tab
    confirmed_by: modern_fritz_ui.py:175,184 + Caissa.qss:165-173
                  + QTabWidget absent from the widget tree

  [warn] orphan_style_rule  QTabWidget::pane
    Caissa.qss:214-218 (and 7 other theme files). No QTabWidget exists in the
    application. `top: -1px` — the tab/pane merge idiom — never executes.
```

<a id="the-notation-fix"></a>**The fix is therefore not the four QSS lines I proposed.** My previous version said "four lines in `Caissa.qss:220-236`". Those four lines are necessary and insufficient: they never touch the corner radius, and they edit a `::pane` rule that matches nothing — `Caissa.qss:214-218` is dead, and editing it changes nothing. **This paragraph is the single statement of the proposed fix; Phases 7a/7b and the fourth real check below all refer back to it rather than restating it.** Five changes, in one place:

| # | Change | Why |
|---|---|---|
| 1 | a dedicated `#WFritzNotationContainer > #WFritzFlowingNotation` rule squaring `border-top-left-radius` and `border-top-right-radius` to **0**, keeping the bottom pair rounded | flattens the top edge so the page has no bite taken out of it. The container objectName exists already (`modern_fritz_ui.py:169`/`:176`) and the docstring at `:163` names `WFritzFlowingNotation` — **but the class never calls `setObjectName` for it**, so that one line has to be added before the rule can match |
| 2 | `margin-right: 0` on `QTabBar::tab` | closes the 2 px holes showing `#1e1e1e` through to the grandparent |
| 3 | an **opening** bottom edge on `::tab:selected` instead of `border-bottom: 2px solid #228df2` | the accent must not replace the bottom border with a different closed one |
| 4 | a `::tab:selected` fill **distinct from the base** | `:233` currently declares it identical to `:222`, so selection carries no fill signal at all (ΔE 2) |
| 5 | a `background-color` on `QTabBar` itself | the strip has no fill rule, which is why the gaps and the 79 px past the last tab show the window through |

Whether to keep hand-rolling the tab group or move to a real `QTabWidget` is a design decision for you, not something this feature should assume — the report's job is to make both options visible and to stop pointing at `::pane`.

#### Four queries, four model extensions — the prediction held immediately

I wrote, one query ago, *"I am not going to pretend the fourth query will fit."* It did not, and it did not even need to be a fourth query — the same screenshot, looked at properly, needed two more primitives.

| Query | Needed | Broke |
|---|---|---|
| 1 — ribbon spacing | the `perceived` basis | three bases all said "uniform" |
| 2 — pane captions | gradient `Fill`, `hypotheses`/`confirmed_by` | one detector, no way in from a sentence, wrong mechanism asserted |
| 3 — notation tabs | `Seam`, `shows_owner` | **`spacing_uniformity` passes** |
| 3b — the same tabs, corners | **`Corner`, `Surface`**, three-valued `effective` | **`StyleSource` would name a rule that matches nothing** |

The 3b row is the one that should worry a reader most, because nobody gave me a new query for it — I simply had not looked at corners, and my report would have been *confidently incomplete* while naming a dead QSS rule as the fix. That is the failure mode this whole document is supposedly designed against.

Two things I am taking from it, both already reflected below:

- **Phase 2d is now mandatory rather than prudent.** The primitives are not enumerable by me in advance; four queries have produced four extensions, and the fourth arrived from re-reading a capture I had already analysed. `Scene` gets `Fill`, `Ink`, `Seam`, `Corner` and `Surface`, and then the build stops until you throw another query at it.
- **The `Segment` layer needs a completeness checklist, not just detectors.** The reason I missed the corners is not a missing detector — it is that nothing in my pipeline *measured* corners, so no detector could have fired. So `describe` must enumerate a fixed inventory per node (fill, ink, border per side, corner per corner, seam per neighbour) and mark each `measured` / `not_measured`, so a gap in the measurement is visible in the output instead of being silently absent. **An unmeasured property is indistinguishable from a correct one, and that is the defect that produced this correction.**

#### What the pattern argues for: a different build order

The detector list growing is fine and expected — detectors are ~40-line pure functions, and the plan is explicitly built so adding one is cheap. But the **data model** needing a new primitive on every single query is a different signal, and the honest reading is that I cannot enumerate the primitives up front.

What that argues for is a concrete change in build order rather than more up-front design: **implement `Scene` + `Measure` + the five primitives, then stop and run your next real query before writing the remaining detectors.** Detectors are cheap and I keep guessing them wrong; the primitives are what everything rests on and I have four confirmed data points for them. Phase 2b therefore ships `invisible_fill`, `spacing_uniformity`, `peer_adjacency`, `surface_broken` and `orphan_style_rule` — the five with evidence behind them — and the remaining eight become Phase 7 work driven by real queries. That is a smaller Phase 2b and a slower-looking plan, and it is the correct order given that three of the eight have been silent on every query so far and a fourth — `fill_extent`, the one I ranked first — was actively wrong on the query it was built for.

One genuinely good sign: **the process worked this time.** I measured, formed a hypothesis, checked the source before asserting, and the mechanism held — `margin-right: 2px` and a four-sided `border` map one-to-one onto what the pixels showed. The `hypotheses`/`confirmed_by` discipline from query 2 is what made me look first, and it changed the outcome.

### The seventh correction: I designed a library and no moment of reaching for it

Everything above describes what the tools measure. Nothing above describes **when I run them.** The entire invocation layer was one row in a file list — `tools/caissa-rpa +describe, locate, measure, report subcommands` — and that is not a design, it is a wish.

The failure this creates is concrete and it is my default behaviour: given *"the tabs in the notation panel look like disconnected components"*, my reflex is to grep `Caissa.qss` for `QTabBar`. That reflex is exactly what produced corrections 4, 5 and 6 — a wrong mechanism, a passing detector, and three separate attempts to fix a rule that matches no widget. **A perfectly correct measurement library that I never invoke leaves the failure rate unchanged.** So the invocation layer is not packaging; it is the part that makes the rest of the document take effect.

Two things I checked, and both change the design rather than confirming it:

- **There is no agent-facing surface in this repo at all.** `.claude/` holds `settings.local.json` and a `worktrees/` directory and nothing else — no `.claude/skills/`, no `.claude/commands/`, and no user-level `~/.claude/skills/`, so both directories are created by this feature rather than added to. The trigger has to be built from scratch, which is cheap — but it also means nothing today would make me reach for `tools/caissa-rpa` even if every phase below shipped.
- **A pasted image has no path on disk.** I parsed this session's transcript at `~/.claude/projects/-Users-johannes/<session>.jsonl` and found exactly two image blocks, both `role=user`, both `source: {"type": "base64", "media_type": "image/png", "data": …}` — 3 096 and 256 216 bytes. No filename anywhere, and no `CLAUDE_TRANSCRIPT_PATH` in the environment. So use case (b) as you stated it — *"I would upload a screenshot"* — has **no route into cv2** without a decode step, and I would fall straight back to interpreting the image in-context. That is the cloud interpretation this whole feature exists to remove, and it would have been discovered on the first real use.

This correction is different in kind from the other six. Those were wrong answers about pixels. This one is a **missing surface**: the plan was complete and internally consistent and would have shipped a tool nobody, including me, would call.

---

## Architecture

### Purity tiers and the coverage trap

`.coveragerc` omits only `Driver.py`, `Service.py`, `Vision/{Capture,Template,Ocr}.py`, `Fakes.py`. **Any new `Vision/` module falls inside the ≥90% branch gate (N-RPA-5) unless explicitly omitted.** So the split is deliberate: put every decision-making branch in numpy-free modules that fast `unit` tests can cover, and keep the cv2 modules thin and mechanical.

Tier numbers below are the **RPA scheme** (`_archive/rpa-layer/feature_spec.md:102-114`): Tier 0 dependency-free, Tier 1 stdlib-only, Tier 2 cv2/tesseract, Tier 3 Qt-touching. Not the four generalised names I used in an earlier draft.

| New module | Tier | Imports | Coverage | Marker |
|---|---|---|---|---|
| `Vision/Scene.py` | 1 | stdlib + `Types.Rect` | in gate, real tests | `unit` |
| `Vision/Region.py` | 1 | stdlib + `Types.Rect` | in gate, real tests | `unit` |
| `Vision/Measure.py` | 1 | stdlib + `Types.Rect` | in gate, real tests | `unit` |
| `Vision/Detectors.py` | 1 | stdlib + `Scene`, `Measure` | in gate, real tests | `unit` |
| `Vision/StyleSource.py` | 1 | stdlib `ast` + `Fritz.QssRules` | in gate, real tests | `unit` |
| `Vision/Segment.py` | **2** | `cv2`, `numpy` | omit | `rpa_cv` |
| `Vision/Annotate.py` | **2** | `cv2`, `numpy` | omit | `rpa_cv` |
| `Vision/Report.py` | 1 | stdlib + `json` | in gate, real tests | `unit` |

Every module docstring ends with a `:spec:` tag, the `bin/Code/Rpa/` convention (`Vision/Availability.py:1-18`) — **not** the `:purity:` tag `bin/Code/Fritz/` uses.

**Six of the eight are pure and cv2-free, and that is the point.** Every judgement this feature makes — region grounding, peer clustering, seam ownership, every detector, the four bases — is a function of `Rect`s, ints and hex strings. cv2 does one job: turn pixels into those. So the part most likely to be wrong is also the part that is fastest and cheapest to test and to revise, which is what makes iterating on detectors after each real query you throw at it affordable.

`StyleSource.py` is the only module that crosses feature packages, and deliberately so: `bin/Code/Fritz/QssRules.py:105` already has a pure `qproperties(text) -> dict[selector, dict[prop, value]]`. Rather than add a second QSS parser to the repo, **generalise it to `parse_rules(text) -> dict[selector, dict[prop, value]]` and reimplement `qproperties()` as a filter over it** — one parser, two callers. `scan_qss` (`:50`) is a Q1/Q3 linter, not a parser, so it is not reusable here. Keeping this in its own module leaves `Measure.py` purely geometric with zero cross-feature imports.

`Scene.py` and `Measure.py` are **numpy-free and cv2-free** — they operate on `list[Rect]`, ints and strings and never see an ndarray, which is what makes the geometry logic testable in milliseconds with synthetic rects and keeps `to_ascii()` (my primary input channel) provable without a display. Top-level `numpy`/`cv2` is nonetheless *legal* inside `Vision/` today, because `tests/unit/rpa/test_vision.py:71` prunes the directory and only flags `col_offset == 0`. Closing that hole, and the explicit allowlist that replaces it, are stated once in [*The purity boundary that makes this testable*](#purity-boundary); the fix is prerequisite **P3**.

But the location rule is not the binding one. **N-RPA-9 is about `sys.modules` at runtime, not about source location** — stated in full under *Standards conformance* → *The two mis-citations*. So it is not sufficient that `Segment.py` lives in `Vision/`; nothing on the app-start import path may *reach* it. `Vision/__init__.py` stays 0 bytes, and `Service.py` imports `Segment`/`Annotate` **inside** `rpa_describe`, not at module scope.

**N-RPA-2**: none of the six new modules may import PySide6 at any nesting depth. The allowlist at `tests/unit/rpa/test_completeness.py:51` is `{Driver.py, Capture.py, Service.py}` and stays unchanged. All Qt access goes through the existing `Capture.grab()`, and the `QThreadPool` submission stays inside `Service.py` — already on the allowlist and already omitted from coverage.

### Files to create

```
bin/Code/Rpa/Vision/Scene.py       SceneNode/Scene + Fill/Ink/Seam/Corner/Surface, to_dict(), to_ascii()
bin/Code/Rpa/Vision/Region.py      phrase -> Rect grounding; tree regions + pixel fallback
bin/Code/Rpa/Vision/Measure.py     four bases, gaps, alignment, peers(), owner_of() hit-test
bin/Code/Rpa/Vision/Detectors.py   the 13-detector registry (5 shipped in Phase 2b, 8
                                   deferred to Phase 7); run_all(scene, spec) -> Findings
bin/Code/Rpa/Vision/StyleSource.py QSS + paintEvent source resolution, inert-QSS detection
bin/Code/Rpa/Vision/Segment.py     fill-region + connected-component segmentation, palette
bin/Code/Rpa/Vision/Annotate.py    boxes/labels/dimension lines drawn onto a copy
bin/Code/Rpa/Vision/Report.py      report.json + scene.txt + crops + annotated.png + diff()
bin/Code/Rpa/Workflows/design_verify.py   baseline -> fix -> re-measure -> assert gone
tools/caissa-eyes                  THE AGENT-FACING CLI (0755); ingest/shot/locate/
                                   inspect/explain/verify/regions/doctor
.claude/skills/design-eyes/SKILL.md  the trigger + the seven-step loop + hard rules
.claude/commands/design-eyes.md      one-line explicit escape hatch into the skill
Resources/Rpa/Design/ribbon.spec.json     design truth for the ribbon
Resources/Rpa/Design/panes.spec.json      design truth for the side-panel panes
Resources/Rpa/Design/queries/*.json       THE QUERY CORPUS — see below
docs/features/rpa-design-vision/design-record.md   THIS DOCUMENT, VERBATIM. Committed in
                                   Phase 0a, BEFORE any other work — see below.
docs/features/rpa-design-vision/   initial_idea.md, feature_spec.md, feature_steps.md,
                                   implementation_plan.md  (the four SDD artefacts, Gate A,
                                   all four DERIVED FROM design-record.md)
                                 + design-approval.md      (ui-design-process.md §5 — the
                                   two-round sign-off that BLOCKS Phase 7b; written in 7a)
                                 + production_readiness.md (the de facto fifth artefact, present
                                   in all three archived features; the Gate E record)
tests/unit/rpa/test_scene.py        unit
tests/unit/rpa/test_region.py       unit    — phrase grounding, incl. "the side panel"
tests/unit/rpa/test_measure.py      unit    — the 6-tab spacing regression guard
tests/unit/rpa/test_detectors.py    unit    — one literal-driven case per detector
tests/unit/rpa/test_style_source.py unit    — must assert fritz-widgets.qss:290 is INERT
tests/unit/rpa/test_segment.py      rpa_cv
tests/unit/rpa/test_design_spec.py  unit
tests/unit/rpa/test_eyes_cli.py     unit    — ingest decode; per-command socket requirement;
                                              --format agent stays under 2 KB
tests/unit/rpa/test_query_corpus.py rpa + per-function rpa_cv — the acceptance suite;
                                    renders + verbal queries. NOT a new tests/rpa_cv/ dir:
                                    test_vision.py already sets module-level
                                    pytestmark = pytest.mark.rpa (:22) with per-function
                                    @pytest.mark.rpa_cv (:110,134,...), and
                                    tests/conftest.py:16-33 auto-skips rpa_cv when cv2 is
                                    absent or the platform is offscreen. Following that
                                    pattern keeps tests/unit/rpa/** (already in ruff.toml)
                                    and satisfies the one-suite-marker rule, which is
                                    module-level only (test_foundations.py:235).
```

### Files to modify

```
bin/Code/Rpa/Activities.py         +6 observer activities
bin/Code/Rpa/Service.py            fix _build_activity map; +rpa_describe/rpa_inspect/rpa_report;
                                   QThreadPool submit + result deque drained by pump_once
bin/Code/Rpa/Resolve.py            P5: walk the tree via Region.flatten (:200, :316);
                                   P7: +resolve_all(); forward selector.threshold to OCR (:460)
bin/Code/Rpa/Driver.py             QtDriver.widget_info() emits sub_rects + paint_overrides
bin/Code/Rpa/Types.py              +SubRect; P6: Rect gains intersects/intersection/area/
                                   translate/inset/contains_point
bin/Code/Rpa/Runner.py             pass run_dir into Context (:208) — currently dropped
bin/Code/Main/WBase.py             setObjectName on board / tb / pgn  (lexicon anchors)
bin/Code/Main/MainWindow.py        setObjectName on splitter / base / pgn_information
bin/Code/Rpa/Fakes.py              FakeDriver fixtures carry sub_rects + a synthetic screenshot
bin/Code/Rpa/Vision/Ocr.py         psm/upscale params; +read_words(); per-word gate instead of
                                   the all-or-nothing window gate (:94-96)
bin/Code/Rpa/Vision/Template.py    +0.5/2.0 to _MULTI_SCALES (#scale-trap: Retina crops);
                                   _iou (:46) delegates to Rect.iou — kill the duplicate
bin/Code/Fritz/QssRules.py         generalise qproperties() → parse_rules(); qproperties filters it
tools/caissa-rpa                   chmod +x only (it is currently -rw-r--r--, so every
                                   invocation is permission-denied). The design-eyes
                                   subcommands go in tools/caissa-eyes instead — its
                                   main() requires the socket before dispatch, which the
                                   static-image commands must not.
tools/design/ribbon_report.py      read Resources/Rpa/Design/ribbon.spec.json, drop TARGET
tools/design/elements.py           read the same spec, drop per-element targets
tools/design/compare.py            theme-parameterise chrome_mask + row_ink_profile palettes
tests/unit/rpa/test_vision.py      close the cv2-allowlist hole (#purity-boundary; P3)
.coveragerc                        omit Vision/Segment.py, Vision/Annotate.py
ruff.toml                          add "tools/caissa-eyes" to `include` — one entry only.
                                   The live file already covers tools/design/** and
                                   tests/unit/rpa/**; coding-standards.md:111 quotes a
                                   stale 4-entry version. See Standards conformance.
CHANGELOG.md                       under [Unreleased] → Added
```

**Not on the list, deliberately: `bin/Code/Debug/RemoteControl.py`.** `:325-345` dispatches any `rpa_*` verb via `getattr(self._rpa(), verb)`, so new verbs are just new methods on `RpaService`. If a change to `RemoteControl.py` turns out to be needed, something has gone wrong with the design.

---

## The hard problems

There are seven. Problems 2, 3 and 5 are where this feature actually succeeds or fails, and in my first draft each of them was a single line — which is fairly the criticism that "this is a spare plan for a difficult problem." Problems 1, 4, 6 and 7 are mechanical but each contains a trap that produces *plausible wrong answers* rather than errors, which for a measurement tool is the worse failure.

### 1. N-RPA-4 says verbs return in <200 ms; full-window OCR takes 1–3 s — *and `defer` runs on the Qt main thread*

The wire half is easy and mirrors the existing `rpa_run`/`rpa_status` split, honouring wire-protocol invariant 1 (*no blocking verb — waiting is client-side polling*) and invariant 2 (*read-only verbs always available, including mid-run*):

- `rpa_describe` — accepts a region + options, allocates a `report_id`, returns `{"report_id": ...}` immediately.
- `rpa_report` — read-only, returns `{"status": "queued"|"running"|"ready"|"failed", ...}`.
- `rpa_inspect` — **synchronous and always <200 ms**, because it takes no pixels at all: given a `report_id` whose scene is already `ready`, it runs `Detectors.run_all` over the stored `Scene` and returns ranked `Finding`s. This is the payoff of keeping the detectors pure — re-detecting with a different `only=` set or a different spec against one capture costs microseconds and needs no thread, no worker and no capture. It is the verb behind `caissa-eyes inspect` when a scene already exists, and it is read-only, so wire-protocol invariant 2 makes it available mid-run.

All three are plain methods on `RpaService`; `RemoteControl.py:333` dispatches via `getattr(svc, verb)`, so **no `RemoteControl.py` change is required.**

The part I missed: `QtDriver.defer()` (`Driver.py:224`) is `QTimer.singleShot`, which runs the callback **on the Qt main thread**. Deferring 1–3 s of tesseract there returns the verb in <200 ms but **freezes the entire UI** for the duration — and `pump_once()` is called from inside `_drain` (`RemoteControl.py:181`), so it would also stall every other verb. A "non-blocking" verb that hangs the app is worse than a slow one, because the caller cannot tell.

The work therefore splits by thread-affinity, which is forced by Qt rules rather than chosen:

| Stage | Thread | Why | Cost |
|---|---|---|---|
| `widget.grab()` + `snapshot()` | **main, synchronous** | Qt widgets are main-thread-only, full stop | ~5–20 ms |
| `Segment.*` (cv2 on the ndarray) | worker | no Qt objects touched — just numpy | ~20–80 ms |
| `Ocr.read_words` (tesseract) | worker | subprocess-bound | 300–3000 ms |
| `Annotate` + `Report` write | worker | pure file I/O | ~10–50 ms |
| result hand-back | main | mutate the report registry | <1 ms |

So `rpa_describe` captures **synchronously inside the verb** (cheap, and it must happen before the UI can change), hands the resulting `Screenshot` ndarray + snapshot dict to a `QThreadPool` worker, and returns. Nothing after the capture touches Qt. The worker posts its result back by appending to a `deque` that `pump_once()` drains — reusing the pump that already exists rather than inventing a signal path.

`Vision/Capture.py` stays the only Qt-touching module (N-RPA-2 intact); the `QThreadPool` submission lives in `Service.py`, which is already Qt-aware and already omitted from coverage.

**Fallback for `FakeDriver` and tests:** if no `QThreadPool` is available (no `QApplication`), the work runs inline. `rpa_describe` then returns `{"report_id": ..., "status": "ready"}` in one call. Deterministic tests never depend on thread timing.

**A recorded disagreement.** A reviewing agent argued the worker thread is unnecessary — chunk the work across successive `defer` ticks instead, keeping everything single-threaded and avoiding any thread-safety question. That is half right and worth writing down rather than quietly overruling:

- It is right that **`Segment` could** be chunked, and right that a thread introduces a lifetime hazard (a worker outliving the widget it captured from). The mitigation is that the worker holds only an ndarray and plain dicts — never a `QWidget` — so there is nothing to dangle.
- It is wrong about OCR, which is the only stage that actually matters. `Ocr` calls `pytesseract.image_to_data`, **one atomic subprocess call of 300–3000 ms**. There is no seam to chunk it at. Deferring it onto the main thread freezes the UI for that whole span no matter how the surrounding code is arranged.

So the design keeps the worker, confined to stages that provably touch no Qt object, and accepts the inline fallback as the tested path. If the worker ever proves unstable in the live app, the escape hatch is `with_ocr=False` by default (already the default on `DescribeScene`) — geometry alone is ~100 ms and needs no thread at all. **The thread is a requirement of OCR, not of the feature**, and that is the sentence to remember if this needs revisiting.

### 2. Node identity — where does `tab.file` actually come from?

This is the one I most obviously waved at. My worked example prints `tab.file` and `tab.home` as if those names materialise; the honest truth is **I typed them in by hand**. OCR read `File` at conf 95 and found nothing at all for `Home`, so a naive "name it after its OCR text" rule would have produced `tab.File` and `tab.<unknown>` — and a report keyed on `<unknown>` is useless for diffing across runs.

Identity has to be **positional first, textual second**, because position is deterministic and text is not:

```
node_id := <role>.<discriminator>

role          from the object tier: objectName if set, else lowercased cls
                ("wribbontabbar" → role "tabbar"; a sub_rect of it → "tab")
discriminator  in strict priority order:
  1. objectName of the widget itself, if unique          → "tab.wribbonhometab"
  2. sub_rect index from the owning composite            → "tab[1]"
  3. reading-order ordinal within its row group          → "fill[3]"
```

OCR then **promotes** a name rather than establishing it. If `read_words` returns a single word inside the node's ink box at confidence ≥ 80, `node_id` gains a human alias and keeps the positional one:

```json
{"node_id": "tab[1]", "alias": "home", "label": "", "label_confidence": 0.0}
{"node_id": "tab[0]", "alias": "file", "label": "File", "label_confidence": 0.95}
```

`tab[1]` has **no** `label` — OCR failed on it — but it still has a stable `node_id`, still has an `alias` (from `sub_rects` order matched against the ribbon JSON's declared tab list), and is therefore still diffable and still addressable by me in conversation. The measurements never depend on the alias.

Two rules fall out, and both need tests:

- **`node_id` must be stable across runs and across window widths.** A test renders `ribbon_home` at 720, 820 and 1100 px and asserts the `node_id` set is identical while rects differ. If IDs churn with width, every cross-run diff is noise and the feature is worthless.
- **`alias` is never load-bearing.** `MeasureSpacing(node_ids=...)` accepts either form, but `report.json` is keyed on `node_id`. A test asserts a report generated with OCR disabled entirely has the same keys and the same measurements as one with OCR on — only `label`/`alias` differ.

### 3. Correspondence — matching a reference scene to a candidate scene

`AssertDesignSpec(spec)` was one line. Behind it is the hardest algorithm here.

The Fritz reference is an 820-px-wide screenshot of a *different application* on a *different OS* at a *different DPR*, with different fonts and a different tab set. The candidate is Caissa's `WRibbon`. There is no shared ID space. Asking "is Caissa's tab spacing right" means first deciding **which candidate node corresponds to which reference node** — and getting that wrong produces confident, plausible, wrong numbers, which is the worst possible failure for a tool whose whole purpose is to be trusted.

I am deliberately **not** attempting general scene alignment. The scope narrows to what is both tractable and sufficient:

**Compare *derived invariants*, not node-to-node pairs.** The spec stores relationships that survive translation between the two applications, and the assertion checks those:

| Comparable | Why it transfers | Example |
|---|---|---|
| Band heights | vertical layout is width-independent | `tabrow_height == 21` |
| Palette roles | colour identity, not position | `accent == #007acc` |
| Intra-element padding | a property of one element | `tab pad_left == 13` |
| Gap **uniformity** | a predicate over a set, not an index | `is_uniform(tab fills) → True` |
| Ordinal relations | survives differing counts | `qat row is above tabrow` |

| **Not** comparable | Why |
|---|---|
| Absolute x of tab *n* | different tab sets, different text widths |
| Node-to-node rect equality | no shared ID space |
| Glyph ink widths | different fonts |

This is why the File/Home finding works without any correspondence at all: `is_uniform` over the *candidate's own* fill boxes is an internal predicate. The reference only had to supply the *rule* ("filled tabs are separated"), not a pixel to compare against.

Where node-level correspondence genuinely is needed — comparing Caissa-now against Caissa-after-a-change, i.e. regression rather than reference-matching — both sides *do* share an ID space, because both come from the same `node_id` algorithm above. So:

- **reference ↔ candidate**: invariant comparison only. Never claims per-node equality.
- **candidate ↔ candidate** (before/after): exact `node_id` join, report added / removed / moved / recoloured.

`Report.diff(scene_a, scene_b)` implements the second and is pure, cheap and fully unit-testable. The first is `AssertDesignSpec`, and every spec key carries its own tolerance (§ below). **If a spec key cannot be expressed as an invariant, it does not belong in the spec** — that constraint is what keeps this honest, and it is why the spec schema below has no absolute-x fields.

### 4. Coordinate spaces, and a resampling trap in `Screenshot.logical()`

Three spaces are in play and conflating them silently corrupts every measurement:

| Space | Origin | Unit | Produced by |
|---|---|---|---|
| **physical** | capture top-left | device px | `Screenshot.rgb` |
| **logical** | capture top-left | DPR-1 px | `Screenshot.logical()`, `Template.Match.rect` |
| **widget** | *parent* widget top-left | logical px | `QtDriver.widget_info()["rect"]` |

Two concrete hazards, both of which will produce plausible wrong answers rather than errors:

<a id="coordinate-basis"></a>**(a) `widget_info()` rects are parent-relative and nested.** `Driver.py:366` records `w.geometry()`, which is **parent-relative**, and nests children under `children`. CV rects are capture-absolute. So `owner_of` must flatten the tree accumulating parent offsets before any hit-test — that flattening is `Region.flatten`, and it is prerequisite **P5**. Phase 2 pins it with a test that hit-tests a known **deeply nested** widget — a shallow one passes even when the offset accumulation is wrong, **which is how this bug survives.** (This is the single statement of the hazard; the `owner_of` entry in *Public API* points back here.)

**(b) `Screenshot.logical()` resamples with `INTER_AREA`, which destroys exact-colour masks.** On this Mac DPR is 2. `logical()` averages 2×2 blocks, so the boundary pixels of a `#007acc` fill blend toward the neighbouring colour and a 43-px fill can measure 42 or 44 depending on `tol`. Worse, `tol=10` exact-ish matching gets *softer* at exactly the edges whose position I am trying to measure.

So the rule is: **segment in physical space, convert rects to logical afterwards.**

```python
# WRONG — the shape of ribbon_report.py:319 and my own first draft
regions = fill_regions(shot.logical(), "#007acc")

# RIGHT
regions_phys = fill_regions_raw(shot.rgb, "#007acc")          # crisp edges, no blending
regions = [to_logical(r, shot.dpr) for r in regions_phys]     # documented rounding
```

`to_logical` lives in `Measure.py` (pure, testable) with explicit rounding: `x` and `y` floor, `right` and `bottom` ceil, so a logical rect never *under*-covers its physical source. Every `Rect` in a report is logical; `report.json` records `"dpr"` and `"measured_in": "physical"` so the provenance is never ambiguous.

This also means `Segment` functions take an **ndarray**, not a `Screenshot` — the caller decides the space. That is a signature change from my first draft and it is the correct one.

Note the reference images are a third case: `~/Pictures/fritz-reference/*.png` are already flat files at DPR 1 with no `Screenshot` wrapper, so `dpr=1.0` and physical == logical. The trap only bites on live captures, which is exactly where it would have gone unnoticed longest.

### 5. Tolerance — the difference between a useful tool and one that cries wolf

Font rasterisation, antialiasing and hinting differ between machines and Qt versions. A layer that flags every 1-px difference gets ignored within a day; one that tolerates everything finds nothing. Tolerance must be **per measurement class**, declared in the spec, not a single global epsilon:

| Class | Tolerance | Rationale |
|---|---|---|
| Fill-box edges, band heights | **0 px** | painted from integer geometry — exact or it is a bug |
| Padding derived from fill − ink | **±1 px** | one antialiased edge pixel on each side |
| Glyph ink spans, text widths | **±2 px, or skip** | font-dependent; never a hard assertion |
| Palette hex | exact after quantisation | `fill_regions(tol=10)` absorbs blending |
| Uniformity predicates | `tolerance_px=1`, count must match exactly | the count mismatching *is* the finding |
| OCR text | advisory only | never fails a gate |

`AssertDesignSpec` emits `pass | fail | warn | skip` per key, never a bare boolean, and **`skip` is a first-class outcome** — "this could not be measured" must be distinguishable from "this was measured and is fine". The `"unavailable"` entry in my worked `report.json` already shows the shape; it needs to be the rule rather than an accident.

### 6. The effective stylesheet is a composed string, not a file — the bridge must invert two substitution passes

Naming a `file:line` for a style rule is the single most useful thing this layer does and the easiest to get silently wrong, because **no file on disk contains the rules that are actually in effect.** `QApplication.styleSheet()` is built by two different transforms:

| Pass | Where | What it does |
|---|---|---|
| 1 | `InitApp.py:~55-70` | Reads the theme `.qss`; for each `#RRGGBB` literal, looks up `"{selector}|{property}"` in `Code.dic_colors` and **rewrites the colour in place**. Line numbers survive, colour values do not. |
| 2 | `InitApp.py:130-144` | Reads `fritz-widgets.qss`, replaces every `{KEY}` placeholder from `Code.dic_colors`, and **appends** the result. Only for modes with a `ribbon` key. |

So a report that says `background-color: #007acc at fritz-widgets.qss:290` is claiming something no text file says — the file says `{CHROME_ACCENT}`. Both the authored form and the resolved value are needed, or I cannot act on it: I need the placeholder name to edit the right thing and the resolved value to know what it currently renders as.

`StyleSource.parse_rules()` therefore indexes **sources plus their substitution maps**, and every emitted rule carries four fields:

```json
{"selector": "#WRibbonTabBar::tab:first",
 "file": "Resources/Styles/fritz-widgets.qss", "line": 290,
 "authored": {"background-color": "{CHROME_ACCENT}"},
 "resolved": {"background-color": "#007acc"},
 "placeholder_of": {"background-color": "CHROME_ACCENT"},
 "effective": false, "reason": "overridden by _FlatTabBar.paintEvent (WRibbon.py:127)"}
```

And there is a cheap, decisive confirmation step: **a rule is only reported `effective: true` if its resolved text is actually found in `QApplication.styleSheet()`.** That single check catches theme mismatches, skipped overlays and stale files without any specificity modelling. It needs a live `QApplication`, so it degrades to `effective: "unconfirmed"` in offline/mockup use — which is honest, and better than asserting.

This also means the `--live` path is not a nicety. Only the live app can confirm which rules are in force; the offscreen mockup path can report the authored rules and the `paintEvent` override, but must label QSS effectiveness as unconfirmed. That asymmetry goes in `report.json`, not in prose.

### 7. QTabBar tabs are painted, not child widgets — the object tier is blind

`bin/Code/Fritz/WRibbon.py:700` builds one `_FlatTabBar`; every tab is added with `addTab()` at `:704`. Tabs are not child widgets and have no individual `objectName`, so `snapshot().widget_tree` cannot see them. This is precisely the `vision.md` case for "custom-painted widget → image tier".

Resolved **without** a new driver verb: extend `QtDriver.widget_info()` (`Driver.py:359`) to emit a `sub_rects` list for composite painted widgets — `QTabBar` via `tabRect(i)`, `QToolBar`/`QMenuBar` via `actionGeometry`, `QTabWidget` by delegating to `.tabBar()`. The data arrives through the existing `snapshot()` contract verb, `FakeDriver` populates it from fixtures, and the base `Driver` seam stays at 8 methods.

**Plus a second key that turns out to be essential: `paint_overrides`.** Without knowing that `_FlatTabBar` overrides `paintEvent`, and where, the report cannot name the paint authority — and naming it is the single most actionable line in the whole output. `widget_info` therefore also emits, for each widget, the subset of `{paintEvent, sizeHint, tabSizeHint}` present in `type(w).__dict__` walking the MRO up to `QWidget`, with the defining class name and `inspect.getsourcefile`/`getsourcelines` for the `file:line`. `inspect` is stdlib and `Driver.py` is already in the PySide6 allowlist, so this crosses no tier boundary. It is what lets `StyleSource` say *"`fritz-widgets.qss:290` matches your selector but `WRibbon.py:127` defeats it"* instead of sending me to edit dead code.

Two costs to control, since `snapshot()` is on the hot path for every verb:

- `_sub_rects` and `_paint_overrides` must **early-return** on anything that is not a composite/custom widget, and be individually wrapped so a Qt exception cannot break `snapshot()` — which already swallows screenshot failures the same way at `Driver.py:148-178`.
- `inspect.getsourcelines` does file I/O. Results are memoised per class for the process lifetime, not recomputed per widget per snapshot.
- A timing test asserts `rpa_state` still returns in <200 ms at real depth on the live app. If it does not, `paint_overrides` moves behind an opt-in flag on `snapshot(depth=…)` rather than being emitted always.

This deliberately avoids the anti-pattern in `Workflows/config_roundtrip.py`, which calls the `QtDriver`-only `click_dialog_button()` and therefore breaks under `FakeDriver`. **New activities use only the 8 contract verbs.**

---

## Data model

One node per element carrying up to four measured boxes, rather than one node per basis. My first draft used `basis: str` on `SceneNode` — three nodes for one tab — which makes the *derived* perceived basis impossible to express, because it is a relation between a node and its neighbour's visible edges rather than a property of a box.

```python
BASIS_WIDGET, BASIS_FILL, BASIS_INK, BASIS_PERCEIVED = "widget", "fill", "ink", "perceived"

@dataclass(frozen=True, slots=True)
class Fill:
    rect: Rect
    kind: str = "flat"     # "flat" | "gradient_v" | "gradient_h" | "textured"
    hex_color: str = ""    # flat only
    hex_start: str = ""    # gradient endpoints, sampled at the band's extremes
    hex_end: str = ""
    visible: bool = False  # MAX perceptual distance from background_hex over the ramp
    visible_delta: int = 0 # that max distance, so a report can show its own margin
    background_hex: str = ""  # the LOCAL background compared against, never a global constant
    border_px: int = 0     # uniform border ring, stripped before ink measurement
    border_hex: str = ""

@dataclass(frozen=True, slots=True)
class Ink:
    rect: Rect
    coverage: float        # fraction of node pixels that are ink
    hex_dominant: str

@dataclass(frozen=True, slots=True)
class SceneNode:
    node_id: str                  # stable & positional: "tab[1]"
    rect: Rect                    # widget/sub_rect basis, logical (DPR-1) px
    role: str = "widget"          # "widget" | "tab" | "action" | "region"
    alias: str = ""               # human name; NEVER load-bearing
    label: str = ""               # OCR text; "" when OCR failed or was off
    label_confidence: float = 0.0
    object_name: str = ""
    cls: str = ""
    fill: Fill | None = None      # None = not measured (≠ measured as absent)
    ink: Ink | None = None
    corners: tuple[Corner, ...] = ()   # up to 4; () = NOT MEASURED, not "square"
    borders: dict[str, tuple[int, str]] = field(default_factory=dict)  # side -> (px, hex)
    measured: frozenset[str] = frozenset()   # {"fill","ink","corners","borders","seams"}
    sources: tuple[str, ...] = () # which tiers contributed, strongest first
    style_rules: tuple[dict, ...] = ()
    paint_authority: dict | None = None
    children: tuple["SceneNode", ...] = ()
    attrs: dict[str, str] = field(default_factory=dict)   # {"selected": "true"}

@dataclass(frozen=True, slots=True)
class Scene:
    scene_id: str
    region: Rect
    root: SceneNode
    palette: tuple[tuple[str, int], ...]   # (hex, pixel_count) descending
    theme: str = ""
    ui_mode: str = ""
    dpr: float = 1.0
    seams: tuple[Seam, ...] = ()           # BETWEEN nodes — belongs to the scene, not a node
    surfaces: tuple[Surface, ...] = ()     # spec-supplied multi-node planes
    clusters: tuple[PeerCluster, ...] = ()
    findings: tuple[Finding, ...] = ()
    warnings: tuple[str, ...] = ()         # "ocr_unavailable", "qss_unconfirmed"
    def to_dict(self) -> dict
    def to_ascii(self, verbosity: str = "full") -> str
    @classmethod
    def from_observations(cls, nodes, seams=(), palette=(), **meta) -> "Scene"
```

**`seams`, `surfaces` and `clusters` hang off `Scene`, not `SceneNode`, and that is forced rather than stylistic.** All three are relations *between* nodes — a `Seam` has two endpoints, a `Surface` names members in different parents, a `PeerCluster` spans parents entirely. Hanging them on a node would require picking an arbitrary owner and would make `SceneNode.measured` claim `"seams"` for a property no single node holds. `SceneNode.measured` may still contain `"seams"`: it means *"this node's boundaries were walked"*, and the resulting `Seam` objects are indexed on the scene by `(before_id, after_id)`.

**One placement rule, because the obvious arrangement is circular.** `Scene.findings` references `Finding`, and every `Measure` function takes `SceneNode`. If `Finding`/`Gap`/`PeerCluster` lived in `Measure.py` the two modules would import each other. So: **every frozen dataclass in this feature is defined in `Vision/Scene.py` — `Fill`, `Ink`, `Seam`, `Corner`, `Surface`, `SceneNode`, `Scene`, `Gap`, `Hypothesis`, `Finding`, `PeerAttr`, `PeerCluster`, `RegionMatch` — and `Measure.py`, `Region.py`, `Detectors.py`, `StyleSource.py` and `Report.py` contain functions only.** The dependency graph is a tree with `Scene.py` at the root, which is also what keeps the ≥90 % gate honest: `Scene.py` is data plus two renderers and is trivially covered, and the branchy logic lives in leaf modules that import it and nothing else. Grouping the types by *which module operates on them* is the arrangement that does not compile.

Five modelling decisions that are load-bearing rather than cosmetic:

- **`fill.visible` is the whole ballgame**, and both of your queries are the same value of it being `False`. It is computed against `background_hex` sampled *locally*: `paintEvent` fills unselected ribbon tabs with an opaque `palette().window()` equal to the surrounding background, and the pane captions paint a gradient whose midpoint equals the pane background. A global-constant comparison reports both as "has a fill" and hides both defects.
- **For a gradient, `visible` is the MAXIMUM distance from the background across the ramp, not the mean.** `#252526 → #363636` over `#2d2d2d` has ΔE ≈ 1 in the middle and 8–9 at the ends: a faintly visible top and bottom edge with an invisible middle. That is a *different* defect from a uniformly invisible band and must not report identically — hence `visible_delta` carried alongside, so the report shows its own margin rather than a bare boolean.
- **`None` ≠ absent.** `fill=None` means "not measured"; `fill=Fill(visible=False)` means "measured, and it presents no edge". Collapsing these is how a report ends up silently claiming uniformity — and in the caption case, `fill_regions(hex)` on a gradient returns *nothing*, which would have printed as "no fill measured" and read as **absent** rather than **invisible**. Two words apart, opposite fixes.
- **`border_px` must be stripped before ink measurement.** Home's 1 px `#9daab8` border otherwise makes its ink read as the full tab (46..105) instead of the glyphs (58..93), which corrupts every derived padding and perceived gap.
- **`measured` is the fix for the corner miss.** `corners=()` is ambiguous between "square" and "nobody looked", and that ambiguity is precisely what let me publish a report on the notation tabs with no corner data and not notice. `measured` names the inventory that was actually attempted, `to_ascii()` prints a `not measured:` line for the difference, and a detector may only conclude about a property present in `measured`. **A property nobody measured must never render as a property that passed.**

Gradients are not an edge case in this codebase — `qproperty-titleTop`/`titleBottom` is the documented pane contract (`docs/fritz/qss-contract.md:30-67`) and `WFritzPane.py:257-272` is the reference implementation. A `Fill` model that only understands flat colours cannot see the Fritz house style.

The reconciliation types — defined in `Scene.py` per the placement rule above, and consumed by `Measure` and `Detectors`:

```python
@dataclass(frozen=True, slots=True)
class Gap:
    basis: str
    before_id: str
    after_id: str
    axis: str
    px: int | None                # None = undefined ON THIS BASIS
    undefined_reason: str = ""    # e.g. "after.fill.visible is False"

@dataclass(frozen=True, slots=True)
class Hypothesis:
    mechanism: str                # "gradient endpoints straddle the pane background"
    likelihood: str = "possible"  # "likely" | "possible" | "unlikely"
    would_confirm: str = ""       # what evidence would settle it — a file, a property, a probe
    ruled_out_by: str = ""        # set when a MEASUREMENT already excludes it

@dataclass(frozen=True, slots=True)
class Finding:
    kind: str                     # detector name: "invisible_fill" | "spacing_uniformity" | ...
    verdict: str                  # "ok" | "non_uniform" | "violated" | "indeterminate"
    summary: str                  # one line of plain English — MEASUREMENT ONLY, no mechanism
    node_ids: tuple[str, ...] = ()   # every node it covers; drives ranking
    severity: str = "warn"           # "error" | "warn" | "info"
    measurements: dict[str, str] = field(default_factory=dict)  # what the pixels say
    hypotheses: tuple[Hypothesis, ...] = ()   # candidate mechanisms, ranked, NEVER asserted
    confirmed_by: str = ""        # "" until step 5 resolves it; printed as "(pending)"
    per_basis: dict[str, str] = field(default_factory=dict)   # spacing only
    gaps: tuple[Gap, ...] = ()                                # spacing only
    caused_by: str = ""           # kind of the finding this one is a consequence of
    evidence: dict[str, str] = field(default_factory=dict)
    sources: tuple[dict, ...] = ()   # style_sources_for() output — where to fix it
```

`node_ids` and `caused_by` are what make a multi-detector report readable rather than a pile. `len(node_ids)` is the secondary ranking key after severity, so a defect spanning four panes outranks one widget. `caused_by` lets a detector say "this is downstream of that" — needed immediately, since `spacing_uniformity` on the ribbon is downstream of `invisible_fill`.

**`hypotheses` / `confirmed_by` exist because I asserted a wrong mechanism and nearly acted on it.** The rule they encode:

- `summary` and `measurements` contain only what was measured. No causal language.
- `hypotheses` is where any explanation goes, always plural, always ranked, and **rendered with its likelihood label attached**. `Hypothesis.ruled_out_by` is the important field: when a measurement already excludes a mechanism (`width CONSTANT 566` excludes "fill is text-sized"), the detector says so, which is how the report argues *against* itself.
- `confirmed_by` is empty until the `StyleSource` bridge or a live probe resolves it, and renders as `(pending)`. **A `Finding` with hypotheses and no `confirmed_by` is not actionable and must not read as though it is.**

The cost of getting this wrong is concrete, not theoretical: asserting "the fill is text-sized" would have sent me to add stretch/`setSizePolicy` to `_PaneTitleBar` — a widget that already spans its pane — producing a no-op diff and an hour spent wondering why the screenshot did not change. **Two hypotheses can be pixel-identical; the report's job is to say so, not to pick.**

`PeerCluster` and `PeerAttr` live alongside them, same module:

```python
@dataclass(frozen=True, slots=True)
class PeerAttr:
    name: str
    status: str                   # "CONSTANT" | "VARYING"
    values: tuple                 # one entry per member, member order
    normalised: tuple = ()        # e.g. width/parent_w — catches container-relative drift

@dataclass(frozen=True, slots=True)
class PeerCluster:
    cluster_id: str               # "pane_caption"
    signature: tuple
    members: tuple[str, ...]      # node_ids, in reading order
    parents: tuple[str, ...]
```

**`Finding.verdict` is `non_uniform` if *any* basis says non-uniform**, and basis disagreement is promoted to its own `Finding`. Averaging the bases or trusting a single one reproduces exactly the failure that made my first design agree with the naive measurement and contradict your eye.

### Worked example — the File/Home gap, measured for real

**This is the entire deliverable of the feature.** If `scene.txt` reads like this, I can diagnose and fix the bug without ever seeing a pixel. Numbers are from the 6-tab probe above (font caveat applies — re-measure before committing):

```
scene: ribbon_tabbar   region=(0,0,354,25)  dpr=2.0  theme=Caissa  ui_mode="Modern Fritz"
palette  #1f1f1f:4210  #ffffff:1490  #007acc:1150  #cccccc:302  #9daab8:97  #005b99:29

QTabBar #WRibbonTabBar (0,0,354,25)  sources=[object,subrect,pixel]
  paint authority: paint_event  bin/Code/Fritz/WRibbon.py:127  (_FlatTabBar.paintEvent)
    OVERRIDES  ::tab {background,color}  ::tab:first {background-color,color}
               ::tab:selected {background-color,color,border}  ::tab:hover {...}
  qss effective (geometry only): fritz-widgets.qss:282  padding: 4px 13px
  qss effective (geometry only): fritz-widgets.qss:285  font-size: 8pt   <- sizeHint font
    NOTE paintEvent draws with self.font() = 10pt (WRibbon.py:703)  MISMATCH

  idx label     widget rect      fill                        ink       perceived
  --- --------- ---------------- --------------------------- --------- ---------
   0  File      x   0..45  w 46  #007acc         VISIBLE      13.. 32  (first)
   1  Home  [*] x  46..105 w 60  #ffffff +1px #9daab8 VISIBLE 58.. 93       12
   2  Board     x 106..164 w 59  palette(Window) INVISIBLE   118..151       13
   3  Analysis  x 165..236 w 72  palette(Window) INVISIBLE   175..225       24
   4  Engine    x 237..300 w 64  palette(Window) INVISIBLE   249..288       24
   5  View      x 301..353 w 53  palette(Window) INVISIBLE   313..341       25

  |File______|Home________|Board_______|Analysis______|Engine_____|View____|
  [##########][==========][            ][             ][          ][       ]
   ^#007acc    ^#ffffff+border          ^ no visible fill from here on

  gaps          widget  fill  ink  perceived
  File→Home          0     0   25         12
  Home→Board         0     -   24         13
  Board→Analysis     0     -   23         24
  Analysis→Engine    0     -   23         24
  Engine→View        0     -   24         25
                              ( - = undefined on this basis )

FINDINGS
  [warn non_uniform] spacing_uniformity axis=x
    widget:    uniform        (all 0)
    fill:      indeterminate  (4 of 5 undefined — neighbouring fills invisible)
    ink:       uniform        (23..25, variance 0.7)
    perceived: NON-UNIFORM    (12,13,24,24,25 — 2.08x spread)
    => Geometrically uniform, VISUALLY non-uniform. Only File and Home are
       painted, so their neighbours read 12-13 px from a hard edge while
       transparent tabs read 24-25 px. The complaint is correct; the widget
       measurement is not wrong, it is measuring the wrong thing.

  [warn] basis_disagreement axis=x  ratio=2.08
    => widget says uniform, perceived says non_uniform. Do not trust a
       single-basis gap number for this widget.

  [warn] style_ineffective  #WRibbonTabBar::tab:first
    fritz-widgets.qss:290  background-color: {CHROME_ACCENT} -> #007acc
    NEVER APPLIED. _FlatTabBar._BG_FIRST (WRibbon.py:118) paints #007acc
    unconditionally. Editing this QSS rule will have no visual effect.
    (Fritz.qss:1015 declares the same thing and is also inert.)

  [warn] font_mismatch  #WRibbonTabBar
    tabSizeHint uses QSS font-size 8pt (fritz-widgets.qss:285);
    paintEvent uses self.font() 10pt (WRibbon.py:703). Widths measure
    advance(text,8pt)+26, so glyphs overflow 3-5 px and effective side
    padding varies 10.5..12 px against an authored 13 px.

  [warn e1] theme_blindness  #WRibbonTabBar
    7 QColor literals at WRibbon.py:118-124 are not QtCore.Property defaults.
    Selected tab paints #ffffff/#005b99 even under the dark palette.
    Violates ui-design-process.md §7 (E1-E4).

  [info] suspected_low_contrast  unselected tabs
    UNVERIFIED: _FG_NORMAL #1e1e1e (WRibbon.py:123) on palette().window().
    Probe fonts differed from the live app; confirm at Phase 6.
```

Two things to notice about that output, both deliberate:

- The **`perceived` column is the one that agrees with your eye**, and the report says so explicitly rather than leaving me to infer it. Every other basis reports "fine".
- The five findings are ranked and each names a `file:line` I can act on. Three of them (`font_mismatch`, `theme_blindness`, `style_ineffective`) are defects **nobody was looking for** — they fell out of measuring properly.

`report.json` carries the same content structurally, keyed on `node_id`, with `Gap.px: null` + `undefined_reason` where a basis is undefined, and every `style_rule` carrying `authored` / `resolved` / `placeholder_of` / `effective` as in hard problem 6. The `[info]` finding stays `severity: info` with `UNVERIFIED` in its text because the probe's fonts were wrong. **Reporting a suspicion as a suspicion is a requirement, not a stylistic preference** — a layer that promotes guesses to findings is worse than no layer, because I would act on them.

### Worked example 2 — *"the title bars in the side panel do not look right to me"*

The first example is one widget under a microscope. This is the other shape of query: a sentence, a whole-window capture, and no idea yet what I am looking for. **This is also the version corrected after reading the code** — my first draft of this block led with `fill_extent`, which the source disproves. Values are illustrative; the real ones come from a measured run.

```
$ tools/caissa-eyes inspect --phrase "the side panel"

region "side panel"  Rect(748,200,566,720)  source=lexicon->objectName  confidence=high
  matched #WFritzRightCol via LEXICON["side panel"]   (modern_fritz_ui.py:461)
scene: 4 panes, 37 nodes, 3 peer clusters   dpr=2.0  theme=Caissa/dark

peer cluster "pane_caption"  n=4
  members   caption[Players] caption[Engine analysis] caption[Eval profile] caption[Notation]
  left_edge        CONSTANT  755
  top_offset       CONSTANT  +0 from parent top
  height           CONSTANT  20
  width            CONSTANT  566     <- full pane width. NOT text-width.
  fill.kind        CONSTANT  gradient_v
  fill.hex_start   CONSTANT  #252526
  fill.hex_end     CONSTANT  #363636
  fill.visible     CONSTANT  False   <- the finding
  background_hex   CONSTANT  #2d2d2d
  fg_hex           CONSTANT  #d6d6dd
  child_count      CONSTANT  1       <- spec says 3

FINDINGS  (4, ranked)
  [warn] invisible_fill  pane_caption x4        <- covers all 4 panes, ranked first
    Each caption IS full-width (566 px, spanning its pane) and IS painted,
    with a vertical gradient #252526 -> #363636. Its background is #2d2d2d,
    which lies BETWEEN the two endpoints. Mean band colour #2d2d2e; ΔE from
    background 1.0 at the midpoint, 8..9 at the extremes.
    => The title bar is drawn, correctly sized, and invisible. Only the bold
       text reads as a header, which is why it looks like a text-width chip.
    hypotheses (ranked):
      1. gradient endpoints straddle the pane background colour   [likely]
      2. pane background-color changed without updating titleTop/Bottom
      3. gradient direction inverted vs. the approved mockup
    confirmed_by: (pending — step 5)

  [warn] missing_child  pane_caption x4
    panes.spec.json declares children ["title_label","menu_button","close_button"];
    only title_label has a measurable node. 0 of 8 expected 16x16 buttons found
    in any caption band.

  [warn] contrast  pane_caption x4
    fg #d6d6dd on local fill #2d2d2e -> 9.8:1 (adequate), BUT identical to body
    text on body background. Caption and body are typographically
    indistinguishable: same fg, same effective bg, differing only by weight.

  [info] text_duplication  region "Notation" pane
    "Notation" appears at caption(752,529,52,20) and at tab[0](756,551,77,26),
    2 px apart vertically.
```

Four points about that output, three of which exist only because I got this wrong first:

- **The top finding states what it measured, and its mechanism separately, as ranked hypotheses.** `width CONSTANT 566` is a *measurement* and it is what kills my original diagnosis outright — a text-width chip would show `width VARYING 40,95,68,52`. Had my first report printed that row, I would not have believed the wrong mechanism for as long as I did. **The measurement that disproves a hypothesis is often already in the table; the report has to show it rather than only showing what supports the conclusion.**
- **`fill_extent` does not fire here, and `peer_divergence` finds nothing.** Both of the detectors I had built for this query are silent on it. `invisible_fill` — which I had as a *field* — is the whole answer.
- **`contrast` fires for an unexpected reason.** Not "too dim" but "identical to body text". Contrast against a *local* fill that happens to equal the body background means the caption has no chromatic separation at all. A global-background contrast check would have reported 9.8:1 and passed it.
- **Nothing above required the source code.** Region, cluster, measurement, and three ranked hypotheses all come from pixels plus one spec file. Step 5 then picks between the hypotheses — and `confirmed_by: (pending)` is printed *as pending*, so a hypothesis never reads as a cause.

### The text channel has a budget, and the whole window blows it

That example is ~1.5 KB for 7 nodes. The Fritz `full` scene has on the order of 400 widgets and, with fills and glyph boxes, several thousand nodes. At the same density that is **hundreds of KB of scene text** — which does not fit usefully in context, and if it did, the signal would be buried. A vision layer whose output I cannot read is the same failure as one whose output is a picture.

So verbosity is a designed parameter, not an afterthought:

| Level | Content | Typical size | Used for |
|---|---|---|---|
| `findings` | `Finding` list only, ranked by severity | ~1 KB | default over the wire; whole-window scans |
| `summary` | findings + one line per node, no per-basis columns | ~5 KB | a pane or a toolbar |
| `full` | the worked example above | ~1.5 KB per 7 nodes | one widget under investigation |
| `report.json` | everything, always, on disk | unbounded | the artefact; I read slices with `Read`/`jq` |

Two rules follow. **`report.json` is always complete and always on disk; `scene.txt` is a rendering of it at a chosen verbosity.** And **`DescribeScene` requires a `selector`** — there is no "describe everything" call, because the useful question is always about a region. Whole-window scanning is a separate, deliberately lower-resolution mode: `findings` verbosity, geometry only, no OCR, whose output is a list of *places to look*, not a description.

This is also why `Finding.summary` is a required field carrying one line of plain English. At `findings` verbosity that string **is** the entire report. If it does not stand alone, the level is useless.

---

## Public API

`Vision/Measure.py` — pure, numpy-free:

```python
# geometry primitives
def gap(a: Rect, b: Rect, axis: str = "x") -> int
def to_logical(r: Rect, dpr: float) -> Rect        # x,y floor; right,bottom ceil
def aligned(rects: Sequence[Rect], edge: str = "top", tolerance_px: int = 1) -> bool
def group_rows(rects: Sequence[Rect], tolerance_px: int = 2) -> list[list[Rect]]

# the four bases
def gaps(nodes: Sequence[SceneNode], axis: str = "x", basis: str = BASIS_WIDGET) -> list[Gap]
def perceived_gaps(nodes: Sequence[SceneNode], axis: str = "x") -> list[Gap]
def gaps_all_bases(nodes: Sequence[SceneNode], axis: str = "x") -> dict[str, list[Gap]]
def fill_is_visible(fill_hex: str, background_hex: str, delta: int = 12) -> bool
def uniformity(values: Sequence[int | None], tolerance_px: int = 1) -> tuple[str, float]

# seams — the boundary BETWEEN nodes, which no per-node measurement can express
def seams(nodes: Sequence[SceneNode], axis: str = "x") -> list[Seam]
def seam_owner(shows_hex: str, node: SceneNode, ancestors: Sequence[SceneNode]) -> str
def edge_is_open(node: SceneNode, side: str, neighbour: SceneNode) -> bool

# surfaces — nodes a design convention says are ONE plane (tab + its content)
def surfaces(scene: Scene, spec: dict) -> list[Surface]      # roles come from the spec
def surface_breaks(surface: Surface, scene: Scene) -> list[str]
    # "corner_tl_radius_8" | "seam_closed" | "fill_mismatch" | "seam_shows_ancestor"

# peer clustering — what makes "the title bars" a set
def peer_signature(node: SceneNode, parent: SceneNode | None) -> tuple
def peers(scene: Scene, min_size: int = 2) -> list[PeerCluster]
def compare_peers(cluster: PeerCluster) -> dict[str, PeerAttr]   # CONSTANT | VARYING + values

# perceptual helpers the detectors need
def relative_luminance(hex_colour: str) -> float
def contrast_ratio(fg_hex: str, bg_hex: str) -> float            # WCAG-style, 1.0..21.0

# the pixels→code bridge
def owner_of(rect: Rect, snapshot, min_overlap: float = 0.9) -> dict | None
def sub_rect_of(widget: dict, rect: Rect) -> dict | None
```

`perceived_gaps` is the derived basis, so its rule needs stating precisely: for each adjacent pair, walk right from the left node's ink edge looking for the first *visible* boundary — a `fill.visible` edge or a `border_px > 0` edge, from either node — and measure to it; if none exists before the right node's ink begins, fall through to ink-to-ink. `undefined_reason` records which case fired.

`peers` is what the second query needs and it is the sleeper function in the feature. Two rules make it work rather than produce mush:

- **Signature buckets, not exact values.** Heights bucket to ±1 px and fills to a quantised hex, or antialiasing splits one class into four singletons. Cluster size < 2 is discarded — a class of one has nothing to compare against.
- **`index within parent` is part of the signature.** That is what makes the four pane captions one class while excluding the pane bodies below them. Without it, "first child of a pane" and "second child of a pane" merge and every attribute reads VARYING.

`compare_peers` returns per-attribute `CONSTANT`/`VARYING` with the values, and `peer_divergence` turns that into a `Finding`. The pane-caption diagnosis is literally this table with one row flagged, which is why the detector needs no reference image.

`Vision/Region.py` — phrase grounding, pure:

```python
LEXICON: dict[str, tuple[str, ...]]   # phrase -> ordered candidate anchors
def flatten(widget_tree: Sequence[dict], origin: Rect) -> list[dict]   # P5 — absolute rects
def named_regions(snapshot) -> dict[str, Rect]        # from the widget tree, absolute logical px
def resolve_phrase(phrase: str, snapshot, capture_rect: Rect) -> RegionMatch | None
def geometric_region(phrase: str, capture_rect: Rect) -> Rect | None   # "top right", "bottom half"
def decompose(img_rects: Sequence[Rect], capture: Rect) -> list[Rect]  # pixel fallback, pure
def nodes_in(scene: Scene, region: Rect, min_containment: float = 0.8) -> list[SceneNode]
```

`flatten` is the P5 fix and it lives here, in the pure tier, because it is where every consumer needs it: a recursive walk of `children` accumulating parent offsets, turning parent-relative `w.geometry()` rects into capture-absolute ones. It is the function `Resolve.visible_elements` should have been calling all along, and `Measure.owner_of` consumes the same output.

**The lexicon has to be built against objectNames that exist, and half of them do not.** What I confirmed in the tree:

| Phrase | Anchor | Status |
|---|---|---|
| `side panel`, `right panel`, `panel column` | `#WFritzRightCol` (`modern_fritz_ui.py:461`) | **exists** — your query resolves |
| the outer frame | `#WFritzOuterContainer` (`:513`) | **exists** |
| a named pane, e.g. `the notation pane` | `PaneSpec.key`/`.label` (`Fritz/Types.py:16-31`) via `_PANE_SPECS` (`modern_fritz_ui.py:32-38`) | **exists** — the repo's only key↔human-label table, and exactly what a phrase lexicon needs |
| `main area`, `right column` | `Layouts.PRESETS` zone keys `"main"` / `"right_col"` (`Fritz/Layouts.py:27-52`) | **exists** — the only pre-existing region vocabulary in the codebase; reuse the spellings rather than inventing rivals |
| `the board` | `WBase.board` | **no objectName at all** |
| `the toolbar` | `WBase.tb` | **no objectName** |
| `the notation`, `the move list` | `WBase.pgn`, `MainWindow.pgn_information` | **no objectName** |

So the three phrases most likely to come out of your mouth first are the three that cannot be resolved by objectName today. The ladder handles it — `LEXICON` values are an *ordered tuple of anchors*, tried in turn: objectName, then class name (`Tabla`, `WBase`), then Python attribute path via the `board_info` precedent (`Driver.py:573`), then geometric fallback. But the better fix is to **add the missing objectNames** — six one-line `setObjectName` calls, no behaviour change, and they make the whole side of the feature that starts from a sentence work by name instead of by heuristic. That goes in Phase 1 alongside P5, and it is the cheapest high-leverage change in the plan.

`resolve_phrase` returns a `RegionMatch` carrying `rect`, `source` (`"lexicon" | "objectname" | "classname" | "attrpath" | "geometric" | "pixel"`) and `confidence`, and **must return `None` rather than guess.** A wrong region silently answers a different question than the one you asked, which is the worst failure mode this layer has: the output would be confident, well-formatted, and about the wrong part of the screen. When `resolve_phrase` returns `None` the honest response is to list which region names *are* available — `named_regions` makes that a one-liner — and let you pick.

`Vision/Detectors.py` — the registry, pure:

```python
DETECTORS: dict[str, Callable[[Scene, dict], list[Finding]]]
def run_all(scene: Scene, spec: dict | None = None,
            only: Sequence[str] = ()) -> list[Finding]     # ranked, most severe first

# Phase 2b — the five with evidence
def invisible_fill(scene, spec) -> list[Finding]        # all 3 queries — write this first
def peer_adjacency(scene, spec) -> list[Finding]        # query 3 — consumes Seam.shows_owner
def surface_broken(scene, spec) -> list[Finding]        # query 3+3b — Corner + Seam + Fill
def orphan_style_rule(scene, spec) -> list[Finding]     # query 3b — no pixels needed at all
def spacing_uniformity(scene, spec) -> list[Finding]    # query 1 — was reconcile()

# Phase 7 — written when a real query needs one, not before.
# Each ships as an xfail(strict=True) named test from Phase 0 (sdd-workflow.md:85-87),
# so the name is in feature_steps.md and a secretly-passing stub is a hard failure.
# contrast, missing_child, text_duplication, fill_extent,
# peer_divergence, edge_alignment, containment, theme_blindness
```

Every detector has the same signature, takes no pixels, and is unit-tested from a literal `Scene`. `run_all` ranking is `error > warn > info`, then by how many nodes a finding covers — a defect affecting four panes outranks one affecting a single widget, which is the right default when I am reading only the top few lines.

#### The canonical `Finding.kind` registry

`Finding.kind` is a closed vocabulary, and it has to be written down in one place because the worked examples above print kinds that are *not* detector names — `basis_disagreement`, `style_ineffective`, `font_mismatch`, `suspected_low_contrast`, `deviation_stale`. Those are real outputs of real layers, but if they are not registered then `Detectors.DETECTORS` is not the whole vocabulary and `expect_absent` / `expect_verdict` in the corpus cannot be validated against a known key set. Seventeen kinds, thirteen of them detectors:

| `kind` | Emitter | Phase | Fires in |
|---|---|---|---|
| `invisible_fill` | detector | **2b** | queries 1, 2, 3 |
| `peer_adjacency` | detector | **2b** | query 3 |
| `surface_broken` | detector | **2b** | queries 3, 3b |
| `orphan_style_rule` | detector | **2b** | query 3b |
| `spacing_uniformity` | detector | **2b** | query 1 |
| `contrast` | detector | 7 | query 2 |
| `missing_child` | detector | 7 | query 2 |
| `text_duplication` | detector | 7 | query 2 (`info`) |
| `fill_extent` | detector | 7 | query 3 (minor); **must not fire on query 2** |
| `peer_divergence` | detector | 7 | none yet |
| `edge_alignment` | detector | 7 | none yet |
| `containment` | detector | 7 | none yet |
| `theme_blindness` | detector | 7 | query 1 — the `WRibbon.py:118-124` E1 literals |
| `basis_disagreement` | **`run_all`**, not a registered detector | **2b** | query 1 |
| `style_ineffective` | **`StyleSource`**, promoted by `Report.emit` | **2c** | queries 1, 3b |
| `font_mismatch` | **`StyleSource`** (QSS `font-size` vs `paintEvent` `self.font()`) | **2c** | query 1 |
| `deviation_stale` | **`AssertDesignSpec`** | **5** | when a `known_deviations` entry starts passing. The activity ships in Phase 4, but the kind cannot fire until Phase 5 writes the first `known_deviations` block, so 5 is where its test lives |

Four rules this table settles, each of which was ambiguous in the prose above:

- **`basis_disagreement` is emitted by `run_all`, not by `spacing_uniformity`.** It is a statement *about* a detector's per-basis output, so a detector cannot own it without reaching into its own result. `run_all` inspects `Finding.per_basis` on every finding that populates it and emits one `basis_disagreement` per disagreeing set, with `caused_by` pointing at the originating finding. That keeps `spacing_uniformity` a pure predicate and keeps the meta-observation in exactly one place.
- **`style_ineffective` and `orphan_style_rule` are not the same finding**, and the three-valued `effective` is what separates them: `matched_overridden` → `style_ineffective` (a widget matches, `paintEvent` wins — `fritz-widgets.qss:290`); `loaded_unmatched` → `orphan_style_rule` (nothing matches at all — `Caissa.qss:214`). Both say "do not edit this rule", for different reasons, and the skill's hard rule names both states for that reason. `orphan_style_rule` is a detector because it is a whole-tree predicate needing no pixels; `style_ineffective` is emitted by the bridge because it is per-rule and needs `paint_overrides`.
- **The name is `theme_blindness`, never `theme_blind`.** An earlier draft of the first worked example used the short form; there is one name, and it is the Phase-7 detector's. Worth stating because it is the kind of drift a closed-vocabulary `expect_absent` list turns into a silently-unmatched key rather than an error.
- **`suspected_low_contrast` is `contrast` at `severity: info` with `UNVERIFIED` in its text**, not a separate kind. It is what `contrast` emits when the measurement's provenance is untrustworthy — in that example, the probe's fonts differed from the live app. Registering it as its own kind would let a future report emit a low-confidence contrast claim that no `expect_absent` key can suppress.

**Consequence for the two worked examples above: they print the Phase-7-complete report, not the Phase-2b one.** Worked example 1 shows `spacing_uniformity`, `basis_disagreement` and `style_ineffective`/`font_mismatch` (2b + 2c) alongside `theme_blindness` and `suspected_low_contrast` (Phase 7). Worked example 2's top finding `invisible_fill` is 2b; its `missing_child`, `contrast` and `text_duplication` lines are all Phase 7. That is deliberate — the examples exist to show the *shape* of a complete report, which is what fixes the output format — but Phase 2b's own gate asserts only the 2b subset, and the corpus's `expect_also` keys are phase-tagged accordingly.

**`invisible_fill` is now the one to write first**, because it is the only detector that fires on both queries and it is where the corrected diagnosis lives. Its test is two literal `Scene`s:

- the ribbon: four tabs with `Fill(kind="flat", hex_color=="background_hex")` → four findings, `visible_delta == 0`;
- the captions: four `Fill(kind="gradient_v", hex_start="#252526", hex_end="#363636", background_hex="#2d2d2d")` → four findings, with a companion assertion that the **mean**-based visibility rule would have passed them. That second assertion is the one that pins the max-vs-mean decision to its cause rather than to a symptom.

`spacing_uniformity` keeps its own literal-driven guard from the 6-tab table: `perceived == [12,13,24,24,25]` `non_uniform` while `widget == [0,0,0,0,0]` `uniform`.

`peer_adjacency` gets the query-3 literals: five tab nodes with `Seam(px=2, shows_hex="#1e1e1e", shows_owner="ancestor", closed=True)` between them, asserting it fires — **with a companion assertion that `spacing_uniformity` on the same `Scene` returns `uniform`**. That paired assertion is the regression guard for the wrong-predicate lesson: it pins in a test that uniformity is not sufficient, so nobody later "simplifies" `peer_adjacency` into a uniformity check. A second literal with `shows_owner="parent"` asserts it stays **silent** — a deliberate margin in the parent's own colour is not a defect.

`surface_broken` gets a `Surface("tab_page", ("tab[0]", "notation_content"))` literal carrying `Corner("tl", radius_px=8, shows_hex="#1e1e1e", shows_owner="ancestor")`, a closed joining `Seam`, and ΔE-2 fills — asserting **exactly four breaks**, and asserting the corner break is listed **first**, because it is the one you identified as the main problem and a report that buries it under the fill delta has mis-ranked the diagnosis. A second literal with `radius_px=0` and an open seam asserts zero breaks. And a third with `corners=()` / `measured` lacking `"corners"` asserts the finding reports `indeterminate` for the corner slot rather than `ok` — the direct regression guard for the miss.

`orphan_style_rule` needs no `Scene` at all: a literal selector list plus a literal set of class names present in the tree. The seed case is `QTabWidget::pane` against a tree containing `QTabBar` and `QTextEdit` but no `QTabWidget`, asserting it fires; the negative case is `QTabBar::tab` against the same tree, asserting silence.

And `fill_extent`, when it eventually gets written, gets an **inverted** test — a literal four-caption `Scene` with `width CONSTANT 566` against parents 566 px wide, asserting it emits **nothing**. That is the regression guard for my own wrong diagnosis: if `fill_extent` ever fires on a full-width element, it has reproduced the mistake this plan is built around correcting. False-positive tests matter as much as true-positive ones here, because a confident wrong finding costs more than a missing one.

`owner_of` reuses `Rect.contains` and `Rect.iou` (`Types.py:74,87`) plus `TargetResolver.visible_elements` (`Resolve.py:189`), returning the **smallest** containing widget, ties broken by highest IoU.

⚠️ **Two hops, not one.** `visible_elements` returns `ElementRef`, which has exactly `selector` and `rect` — no sub-elements. So resolving your pasted crop of the Home tab needs `owner_of` → the `WRibbonTabBar` widget dict, then `sub_rect_of` → `{"index": 1, "role": "tab", "text": "Home"}`. My first draft had this as a single hop, which cannot reach a tab.

⚠️ **Coordinate basis.** `owner_of` takes `Region.flatten`'s output, never a raw `snapshot.widget_tree` — see [hard problem 4(a)](#coordinate-basis) for why, and P5 for the fact that nothing in `bin/Code/Rpa/` flattens that tree today.

`style_sources_for` is the pixels→code bridge, and per the `_FlatTabBar` finding it must consult **two** sources and rank them by what actually renders:

```python
[{"kind": "qss",   "file": "Resources/Styles/fritz-widgets.qss", "line": 282,
  "selector": "#WRibbonTabBar::tab",
  "authored": {"padding": "4px 13px"}, "resolved": {"padding": "4px 13px"},
  "effective": True,  "governs": ["geometry"]},
 {"kind": "qss",   "file": "Resources/Styles/fritz-widgets.qss", "line": 290,
  "selector": "#WRibbonTabBar::tab:first",
  "authored": {"background-color": "{CHROME_ACCENT}"},
  "resolved": {"background-color": "#007acc"},
  "placeholder_of": {"background-color": "CHROME_ACCENT"},
  "effective": False, "reason": "overridden by paintEvent ownership in WRibbon.py:127"},
 {"kind": "qss",   "file": "Resources/Styles/Fritz.qss", "line": 1015,
  "selector": "#WRibbonTabBar::tab:first",
  "effective": False, "reason": "shadowed by appended fritz-widgets.qss AND inert"},
 {"kind": "paint", "file": "bin/Code/Fritz/WRibbon.py", "line": 118,
  "symbol": "_FlatTabBar._BG_FIRST", "value": "#007acc",
  "effective": True,  "governs": ["fill"], "e1_violation": True}]
```

Detection rule: if the owning widget's class overrides `paintEvent` (from `paint_overrides` in the snapshot — no separate AST scan needed) and declares bare `QColor("#RRGGBB")` class constants that are not `QtCore.Property` defaults, then QSS colour declarations for that selector are marked `effective: False` and the Python constants become governing. `e1_violation: True` is reported because §7 requires those values come from the QSS. Geometry declarations (`padding`, `font-size`, `margin`) stay `effective: True` — `paintEvent` does not override `tabSizeHint`, so the split is per-property, not per-rule.

`StyleSource.py` is where I most expect to be wrong, so it gets the sharpest test: **`test_style_source.py` must assert that a query for the File tab's background returns `WRibbon.py:118` as governing and marks *both* `fritz-widgets.qss:290` and `Fritz.qss:1015` inert.** If it names either QSS file as effective, the bridge has reproduced my own original mistake and the phase fails.

`Vision/Segment.py` — cv2, taking **ndarrays** (the caller owns the coordinate space, per hard problem 4):

```python
def palette(img, region: Rect | None = None, top_n: int = 8) -> list[tuple[str, int]]
def dominant_hex(img, region: Rect) -> str
def fill_regions(img, hex_colour: str, tol: int = 10, min_px: int = 32) -> list[Rect]
def fill_of(img, region: Rect, background_hex: str,
            border_probe_px: int = 2) -> Fill    # detects flat|gradient_v|gradient_h + border ring
def glyph_boxes(img, region: Rect | None = None, polarity: str = "auto",
                min_area: int = 4, max_w: int = 40, max_h: int = 20) -> list[Rect]
def ink_of(img, region: Rect, fill_hex: str, delta: int = 30,
           strip_border_px: int = 0) -> Ink | None
def row_bands(img, bg_hex: str, min_ink: int = 5) -> list[tuple[int, int]]
def seam_of(img, a: Rect, b: Rect, axis: str = "x") -> tuple[str, bool, str]
                                    # (shows_hex, closed, border_hex) for the strip between a and b
def border_run(img, region: Rect, side: str) -> tuple[int, str]   # (px_thickness, hex) or (0, "")
def corner_of(img, region: Rect, which: str, border_hex: str,
              max_radius: int = 24) -> Corner
    # walks in along both edges until the border run is continuous; that offset IS the
    # radius. Samples the notch outside the arc for shows_hex. Anti-aliasing tolerant:
    # a pixel counts as border if it is within tol of border_hex OR strictly between
    # border_hex and the notch colour.
```

`row_bands` generalises `ribbon_report.py:124` `_band_height`; `palette`/`dominant_hex` generalise `_dominant_hex`/`_nearest_hex`; all stop being ribbon-specific.

Four signatures encode empirical findings rather than taste, and each needs the stated test:

- **`fill_regions` uses `cv2.connectedComponentsWithStats` + `min_px`.** A global bbox over the colour mask is the obvious implementation and it is wrong — on your crop it merged Home's white fill with File's white glyphs into one 82-px phantom. Test asserts two components, not one.
- **`glyph_boxes` takes `polarity`, not a bare threshold.** `"auto"` derives the region's dominant fill and thresholds relative to it, so inverted/selected elements work. Test includes an inverted fixture that a fixed threshold of 150 provably fails.
- **`ink_of` takes `fill_hex`, not a global background.** `paintEvent` fills unselected tabs with opaque `palette().window()`; a global dark-pixel predicate reported Board's ink as `106..164` — *the entire tab* — instead of `118..151`. Ink is measured against the **local** fill.
- **`ink_of` takes `strip_border_px`.** Home's 1-px `#9daab8` border otherwise makes its ink read `46..105` instead of `58..93`, silently corrupting every padding and perceived gap downstream. `fill_of` detects the ring; `ink_of` strips it. Test asserts `58..93` on a committed fixture.
- **`fill_of` classifies flat vs gradient and takes `background_hex` as a required argument.** `fill_regions(img, hex)` matches a single colour and therefore returns *nothing* on the caption band — my original `fill_of` would have reported no fill where there is a full-width painted one. Classification is cheap and deterministic: sample the region's row means (and column means), and if the endpoint delta exceeds the internal row-to-row variance, it is a gradient along that axis; record `hex_start`/`hex_end` from the extremes. `background_hex` is required rather than defaulted because `visible` is meaningless without it, and a default would silently reintroduce the global-constant bug that hides both defects. Test: a `cv2`-drawn vertical ramp `#252526 → #363636` on a `#2d2d2d` field asserts `kind == "gradient_v"`, correct endpoints, `visible is False`, and `visible_delta <= 9`.

Those are the reason `Segment` cannot be a thin mechanical wrapper. Each is a real algorithmic requirement discovered by measurement, and each was producing a confidently wrong — or confidently empty — answer before it was found.

`Vision/Ocr.py` — extend, do not replace:

```python
def find_phrase(screenshot, phrase, confidence_threshold=50.0,
                psm: int = 11, upscale: int = 4) -> list[Match]      # psm/upscale are new
def read_words(screenshot, region=None, psm: int = 11,
               upscale: int = 4) -> list[tuple[str, Rect, float]]    # new
```

Default PSM moves 3 → 11 on the evidence above. `read_words` returns everything found with confidences, so callers see low-confidence hits instead of having them silently dropped.

`Vision/Scene.py` — **every frozen dataclass in the feature, plus two renderers, and nothing else** (the placement rule from *Data model*):

```python
# the five primitives + the eight supporting types — thirteen in all, and the same
# thirteen the placement rule in *Data model* names. @dataclass(frozen=True, slots=True):
#   Fill  Ink  Seam  Corner  Surface
#   SceneNode  Scene  Gap  Hypothesis  Finding  PeerAttr  PeerCluster  RegionMatch
# NOT here: SubRect. It is driver wire data alongside Rect/ElementRef, so it goes in
# Types.py (N-RPA-1 row below) — Scene.py holds only types this feature's own logic
# produces. A Scene node references a sub-rect by node_id, never by holding one.
BASIS_WIDGET, BASIS_FILL, BASIS_INK, BASIS_PERCEIVED = "widget", "fill", "ink", "perceived"
MEASURABLE: tuple[str, ...] = ("fill", "ink", "borders", "corners", "seams")
    # the completeness inventory. describe() must attempt every entry and record the
    # result in SceneNode.measured; to_ascii() prints the difference as `not measured:`.
    # This constant IS the fix for correction 6 — the inventory is data, not a habit.

class Scene:                        # methods, since they are pure renderings of self
    def to_dict(self) -> dict                                  # report.json body
    def to_ascii(self, verbosity: str = "full") -> str          # findings|summary|full
    @classmethod
    def from_observations(cls, nodes, seams=(), palette=(), **meta) -> "Scene"
```

Only `Scene` carries methods, and only two, both pure functions of `self` — which is what keeps `Scene.py` trivially coverable under the ≥90 % gate while the branchy logic sits in leaf modules that import it.

`Vision/Report.py` — pure, stdlib + `json`:

```python
def emit(scene: Scene, out_dir: Path, annotate: bool = True,
         verbosity: str = "full") -> dict          # {"report_json", "scene_txt", "annotated_png",
                                                   #  "crops": [...]} — paths, all written
def render(scene: Scene, fmt: str = "agent") -> str
    # "agent"  — findings only, ranked, ≤2 KB, last line starts "NEXT:"
    # "json"   — json.dumps(scene.to_dict())
    # "human"  — the full worked-example layout
def diff(before: Scene, after: Scene) -> dict
    # joins on node_id — added / removed / moved / recoloured / findings_gone / findings_new
def write_spec(scene: Scene, name: str, out: Path) -> Path     # scene -> *.spec.json
def two_sided_pass(before: Scene, after: Scene, target_kind: str) -> tuple[bool, str]
    # THE verify predicate: target_kind gone AND no new finding at or above `warn`.
    # Returns the reason on failure, so `caissa-eyes verify` can print which half failed.
```

`emit` **always writes the complete `report.json`** regardless of `verbosity`; `verbosity` only selects what `scene.txt` renders. `two_sided_pass` is a named function rather than inline logic in the workflow because both `design_verify.postcondition` and `caissa-eyes verify` need it and it is the one predicate that must not drift between them — a one-sided pass is how "I deleted the captions" scores green.

`Vision/StyleSource.py` — pure, stdlib `ast` + `Fritz.QssRules`:

```python
def parse_rules(text: str) -> dict[str, dict[str, str]]   # lives in QssRules; re-exported here
def style_sources_for(object_name: str, cls: str, qss_sources: Sequence[tuple[Path, str]],
                      paint_overrides: dict, widget_types: frozenset[str],
                      colour_map: dict[str, str] | None = None,
                      live_stylesheet: str | None = None) -> list[dict]
def effective(selector: str, rule: dict, paint_overrides: dict,
              widget_types: frozenset[str],
              live_stylesheet: str | None) -> str
    # "loaded_unmatched" | "matched_overridden" | "effective" | "unconfirmed"
def paint_colour_constants(source_path: Path, cls: str) -> list[dict]
    # ast-only: bare QColor("#RRGGBB") class attrs that are NOT QtCore.Property defaults.
    # Each carries e1_violation=True. This is what makes theme_blindness a static check.
def resolve_placeholders(text: str, colour_map: dict[str, str]) -> tuple[str, dict[str, str]]
    # inverts InitApp pass 2: returns (resolved_text, {property: placeholder_name})
```

`widget_types` is the argument that makes `loaded_unmatched` possible and it is why `StyleSource` needs `Region.flatten`'s output rather than just the QSS: the flattened tree's set of class names is what proves `QTabWidget` is absent. `live_stylesheet=None` forces `"unconfirmed"` — the offline/mockup path may never claim `effective`.

`Vision/Annotate.py` — cv2, taking **ndarrays**, drawing onto a copy, returning a copy:

```python
def boxes(img, nodes: Sequence[SceneNode], colour_by: str = "basis") -> "ndarray"
def dimension_line(img, a: Rect, b: Rect, axis: str, label: str) -> "ndarray"
def label_nodes(img, nodes: Sequence[SceneNode], use: str = "node_id") -> "ndarray"
def highlight_findings(img, findings: Sequence[Finding], nodes) -> "ndarray"
def crops(img, nodes: Sequence[SceneNode], out_dir: Path, pad_px: int = 4) -> list[Path]
```

`Annotate` is **evidence for you, never an assertion** (N-RPA-7). Nothing in the test suite compares an annotated PNG, and `use="node_id"` rather than `alias` is deliberate — the annotated image has to be readable against `report.json`, which is keyed on `node_id`. It is the thinnest of the eight modules on purpose: it is omitted from coverage, so any decision it makes is a decision made outside the gate.

### Activities

**Six.** All read-only observers following the `GetText`/`ElementExists` precedent — store into `ctx.extra[key]`, `postcondition` returns `key in ctx.extra` (idempotent, per `docs/rpa/activities.md`). None actuates; each makes at most one `driver` call; all use only the 8 contract verbs.

```python
Locate(phrase="", fragment_path="", text="", region=None, key="located", threshold=0.80)
DescribeScene(target="located", key="scene", with_pixels=True, with_ocr=False, with_style=True)
Inspect(scene_key="scene", key="findings", detectors=(), spec_name="")
MeasureSpacing(scene_key="scene", key="spacing", axis="x", tolerance_px=1)
AssertDesignSpec(spec_name, key="verdicts", scene_key="scene", strict=False)
EmitVisionReport(scene_key="scene", out_dir="", key="report_path", annotate=True)
```

The shape changed because of the second query. `Locate` now takes **`phrase` first**, which is the entry point a sentence uses, and the fallback ladder is explicit and ordered:

| # | Input | Mechanism | When it fires |
|---|---|---|---|
| 1 | `phrase="the side panel"` | `Region.resolve_phrase` — lexicon → objectName → geometric | a verbal query, the common case |
| 2 | `fragment_path=...` | `Template.find_all` at scales incl. 0.5/2.0 ([why](#scale-trap)) | you pasted a crop |
| 3 | `text="Home"` | `Ocr.find_phrase(psm=11)` | you named a literal on-screen label |
| 4 | `region=Rect(...)` | as given | I already narrowed it |
| 5 | none of the above | whole window at `findings` verbosity | triage — output is *places to look* |

The honest limit stays: `Ocr.find_phrase` matches exact word sequences, so *"the tab next to File"* resolves via rung 1 or not at all. But rung 1 is the one that makes verbal queries work at all, and it was entirely absent from my previous draft — which is precisely why the side-panel question had no way in.

`Inspect` is new and is the activity that answers *"does this look right?"*. It runs `Detectors.run_all` over an already-built `Scene` and stores ranked `Finding`s. It is separate from `DescribeScene` because describing is expensive (pixels, maybe OCR) and detecting is nearly free and pure — so I can re-run detection with different detectors or a different spec against one capture, which is exactly the loop when I am narrowing down what you meant.

`MeasureSpacing` survives as a named activity rather than folding into `Inspect` because "measure these specific gaps for me" is a question I ask directly, without wanting the other seven detectors' output.

`AssertDesignSpec(strict=False)` records mismatches into `ctx.extra` without failing the step (observer semantics); `strict=True` raises, for a gate workflow. `out_dir=""` means `ctx.run_dir` — which requires the one-line `Runner` fix in the prerequisites.

Every activity must degrade gracefully when `ctx.snapshot.screenshot is None`, because `FakeDriver.snapshot()` never populates it. Degradation is specified, not incidental:

| Missing | Behaviour | Marker on the report |
|---|---|---|
| `cv2` | object + `sub_rects` tiers only; no fill/ink | `warnings: ["cv_unavailable"]`, fill/ink `null` |
| `pytesseract` | all geometry, no labels | `warnings: ["ocr_unavailable"]`, `label: ""` |
| `screenshot is None` | object tier only | `warnings: ["no_capture"]` |
| no live `QApplication` | authored QSS + paint authority, no confirmation | `effective: "unconfirmed"` |
| `sub_rects` absent | widget basis only; no per-tab nodes | `perceived: indeterminate` |

The rule underneath: **a missing tier degrades the report, never invents a value, and always says so in `warnings`.** `indeterminate` and `null` are first-class outcomes. A report that silently omits the perceived basis would read as "uniform" and reproduce the original failure.

<a id="purity-boundary"></a>
### The purity boundary that makes this testable

`Segment.py` imports `cv2`; `Scene.py`, `Measure.py` and `Report.py` must not, or they fall out of the ≥90% branch gate (N-RPA-5) and — because a pure module that transitively pulls cv2 puts it in `sys.modules` at app start — break **N-RPA-9** as well. The dependency therefore points **one way**: `Fill`, `Ink`, `SceneNode`, `Scene`, `Gap` and `Finding` are all defined in the stdlib-only modules, and `Segment.py` imports *them* to construct its return values. Nothing downstream of `Segment` ever sees an ndarray.

That is the single most important structural decision here. If `Scene.py` or `Measure.py` ever accepts a `Screenshot`, cv2 leaks into the pure tier and both the coverage gate and the import test fail — and the four-basis logic, which is the actual value of the feature, becomes untestable without a display.

There is also a hole in the existing guard: `tests/unit/rpa/test_vision.py:71` prunes the whole `Vision` directory, so top-level `cv2` is currently legal in *any* `Vision/` module. A new `test_cv2_confined_to_designated_vision_modules` with an explicit allowlist `{Capture.py, Template.py, Ocr.py, Segment.py, Annotate.py}` is what actually enforces the boundary. Without it nothing stops someone importing cv2 into `Measure.py` and quietly disabling the gate.

---

## Standards conformance — and two rules I had cited wrongly

Yes: this is built as RPA activities under the existing RPA standards, and the verify loop is the documented `Runner` loop rather than a bespoke script. Writing that down turned up two places where my own plan was already non-conformant, so the section is corrections first.

### The two mis-citations

**N-RPA-9 is not the rule I thought it was.** I had it as *"no top-level cv2/numpy outside `Vision/`"*. The normative text (`docs/features/_archive/rpa-layer/feature_spec.md:63`) is:

> **N-RPA-9**: `cv2` and `numpy` **MUST NOT** appear in `sys.modules` after a plain app start without an `rpa_*` verb.

That is a **runtime lazy-import rule about process state**, not a source-location rule. The location rule is a separate AST guard (`test_no_toplevel_numpy_or_cv2_import_outside_vision`) supporting N-RPA-1. The consequence is concrete and I had missed it: it is not enough for `Segment.py` to live in `Vision/`. Nothing on the app-start import path may *reach* it. So:

- `Vision/__init__.py` stays **0 bytes** (`docs/rpa/vision.md:17` — *"zero import cost"*, and it is deliberate).
- `Service.py`'s `rpa_describe` imports `Segment`/`Annotate` **inside the method**, matching the house pattern (`QtDriver.widget_info` does `from PySide6 import QtWidgets` at `Driver.py:366`; `Availability.probe()` is lazy and cached).
- `Detectors.py`, `Measure.py`, `Region.py`, `Scene.py`, `Report.py` and `StyleSource.py` must be importable with cv2 uninstalled — which the purity tiering already gives, but now for a second and stronger reason than coverage.
- The gate is a **runtime** assertion (`"cv2" not in sys.modules` after a plain start), not only the AST test. P3 fixes the AST hole; N-RPA-9 needs the runtime check as well.

**N-RPA-4 carries a qualifier I dropped**: *"`rpa_*` verbs MUST return in < 200 ms **while a run is active**"* (`:58`). I had it as unconditional. I am keeping the stricter unconditional reading anyway — `rpa_describe` returning a `report_id` immediately is the right design regardless — but the plan should not misquote the rule it claims to satisfy.

### Rules this feature touches, and what satisfies each

| Rule | Text (abbreviated) | How this feature satisfies it |
|---|---|---|
| **N-RPA-1** | `Types.py` zero third-party imports | `SubRect` and the six new `Rect` methods (P6) are stdlib-only. The five primitives (`Fill`/`Ink`/`Seam`/`Corner`/`Surface`) go in `Vision/Scene.py`, **not** `Types.py` — the same call `docs/rpa/decisions.md:109` records for `Screenshot`/`Match`. |
| **N-RPA-2** | Only `Driver.py`, `Vision/Capture.py`, `Service.py` may import PySide6 | None of the eight new modules imports Qt at any depth. Capture stays in `Capture.py`; the `QThreadPool` submission stays in `Service.py`. Allowlist at `tests/unit/rpa/test_completeness.py:51` unchanged. |
| **N-RPA-3** | **No `time.sleep()` anywhere in the package** | The worker thread must not sleep, and the `rpa_report` poll loop lives in `tools/caissa-eyes`, **outside** `Code.Rpa` — reusing `CaissaRpaClient.run_and_wait()`'s polling idiom (`tests/ui/rpa_client.py`) rather than writing a second one. |
| **N-RPA-4** | `rpa_*` verbs return < 200 ms | `rpa_describe` captures synchronously (~5–20 ms) and returns a `report_id`; `rpa_report` is read-only. Hard problem 1. |
| **N-RPA-5** | ≥ 90 % branch for `Code.Rpa`, omitting Qt-touching and test-double modules | Six of eight new modules are in the gate. `Segment.py`/`Annotate.py` are omitted on the **established precedent**, not by assertion: `.coveragerc` already omits `Vision/Template.py` and `Vision/Ocr.py`, which are not Qt-touching either — the operative criterion is *requires cv2/tesseract at import*. |
| **N-RPA-6** | RST docstrings on **all** callables, public *and* non-public | Every private helper in the eight modules too. Module docstrings follow the house shape: path line, prose, `Usage::`, then a `:spec:` tag (see `Vision/Availability.py:1-18`). |
| **N-RPA-7** | No full-window pixel equality in CV assertions | Every corpus assertion is structural (`kind`, cluster size, `min_nodes`, a break list). `Report.diff` joins on `node_id`, never on pixels. The annotated PNG is evidence for you, never an assertion. |
| **N-RPA-8** | Capture via `widget.grab()`/`QTest` — never `pyautogui`, `mss`, CoreGraphics | `Capture.grab()` only. **`ingest` is not an exception**: it decodes an image *you* already took and pasted. Nothing in this feature screen-scrapes the OS. |
| **N-RPA-9** | cv2/numpy absent from `sys.modules` after a plain app start | Lazy imports as above, plus a runtime gate. Corrected — see above. |
| **N-RPA-10** | Run deadline 90 000 ms | `design_verify` does capture→describe→detect twice; worst case ~8 s with OCR on. Comfortable. |
| **E1–E4** | `qproperty-` contract; a `#RRGGBB` literal in a widget module only as a `QtCore.Property` default (`ui-design-process.md` §7) | Reported, not violated: `theme_blindness` and the `e1_violation: True` flag on `WRibbon.py:118-124` exist to surface it. The feature adds no literals of its own. |
| **§9** | Reference crops MUST NOT be committed; the harness has no role in `make test` | Oracle comparison stays in `tools/design/`. The corpus renders its own scenes with `fritz_mock`. |

### The verify loop is the `Runner` loop — not a script

`Workflows/design_verify.py` follows `Workflows/classical_invariant.py` exactly, which is the repo's canonical **assert-in-`postcondition`** workflow: a module docstring with a `:spec:` tag, private `_Activity` subclasses, and a `register(name, [...])` call. Concretely:

- Activities implement `precondition` / `execute` / `postcondition`, plus optional `compensate` and `prepare_next` — `docs/rpa/authoring-workflows.md:62-80`. My earlier draft said "act"; the method is **`execute`**. All six new activities leave `compensable` at its default `False` — see the conformance item below on `compensate` raising rather than no-opping.
- `precondition` is called at CHECK_PRE, `execute` at ACT, `postcondition` at VERIFY, once per pump, within the 14-member `SubState` machine (`Runner.py:85-105`; canonical table in `docs/rpa/state-machine.md §2`).
- The six observer activities take the `GetText`/`TakeScreenshot` shape: `execute` stores into `ctx.extra[self.key]`, `postcondition` returns `self.key in ctx.extra` (`Activities.py:331,340,428,436`). That is what makes them idempotent.
- **The loop's timing constraints bind `DescribeScene`.** `postcondition` "must be fast and non-blocking" (`Activities.py:104`) and `VERIFY_TIMEOUT_MS = 5_000` per attempt (`Runner.py:47`). OCR at 300–3000 ms therefore cannot run *in* `postcondition`: `execute` kicks off the async describe and `postcondition` polls the report registry for readiness across successive pumps. `DescribeScene(with_ocr=True)` declares `max_attempts = 2` for a 10 s budget; `settle_ms` stays small because there is nothing to settle after a read-only capture. This is the async machinery from hard problem 1 wired to the activity contract, which my previous draft left disconnected.
- Registration: the workflow module must be added to `_load_builtin_workflows()` in `Service.py` (`authoring-workflows.md:41`) — a named change, not just "modify `Service.py`".
- It must pass `dry_run`, which lints selector syntax, manifest coverage, state-graph reachability and structurally-unsatisfiable preconditions (`docs/rpa/testing.md:97-105`).
- Tests: a Registry unit test plus an `rpa_ui` integration test using `CaissaRpaClient.run_and_wait()` (`testing.md:139-150`), exactly one suite marker per module (enforced by `test_every_collected_test_has_exactly_one_suite_marker`).

The two-sided pass condition lives in `postcondition`, which is the honest place for it: the targeted `Finding` is gone **and** `Report.diff` shows no new finding at or above `warn`. A `postcondition` returning `False` drives DECIDE_RECOVERY → BACKOFF → retry through the existing machine rather than a bespoke retry loop.

### Existing utilities to reuse rather than reinvent

Four of these I was about to duplicate:

| Need | Existing thing | Where |
|---|---|---|
| cv2/tesseract capability check for `caissa-eyes doctor` and the degradation matrix | `Availability.probe()` → `AvailabilityFlags(cv_available, ocr_available, reason)`, cached, never raises | `Vision/Availability.py` |
| Run provenance (DPR, theme, ui_mode, cv/ocr availability) | the journal's **`env` block**, already recorded at run start | `docs/rpa/testing.md:121` |
| Polling a long verb from a client | `CaissaRpaClient.run_and_wait()` | `tests/ui/rpa_client.py` |
| QSS parsing | `QssRules.qproperties()` → generalise to `parse_rules()` | `Fritz/QssRules.py:105` |
| IoU | `Rect.iou` — kill `Template.py:46`'s duplicate | `Types.py:87` |
| Failure evidence convention | `failure-<step>.png` written beside the journal on final-attempt failure | `docs/rpa/testing.md:126` |

`report.json` should therefore **reference** the journal `env` block for DPR/theme/ui_mode rather than carrying a parallel copy — one more copy of the same truth is the mistake this plan spends a whole section on elsewhere.

One more, and it is a free win: **`make rpa-doctor` is a print-only stub** (`Makefile:80-84`) whose message reads *"RPA doctor: Vision/Availability not yet implemented (Phase 7)"* — but `Vision/Availability.py` exists and works. `caissa-eyes doctor` is the same query, so Phase 4b wires both to `Availability.probe()` rather than shipping a second capability checker beside a stale stub.

<a id="sdd-gates"></a>
### The SDD side: which gates bind this feature, and one that blocks Phase 7b

The workflow is two documents with declared precedence (`docs/process/sdd-workflow.md:5-8`): `docs/standards/spec-driven-development.md` is the normative *what*, `docs/process/sdd-workflow.md` the operational *how*, **and the standard wins on conflict.** There is no `docs/standards/sdd-workflow.md`. Four points bind concretely:

- **Gate A is a hard stop.** *"Implementation MUST NOT begin before Gate A passes… When spec and code conflict, the spec governs"* (`sdd-workflow.md:32-34`). So Phase 0 is not paperwork ahead of Phase 1; it gates it. The spec carries R/I/P/Q/N with RFC-2119 vocabulary and a mandatory **§8 Classical Invariant Impact** section — which for this feature is short and true: every new activity is read-only, and `classical` mode gains six `setObjectName` calls and nothing else.
- **A fifth artefact exists that neither SDD document's table lists**: `production_readiness.md`, present in all three archived features (`_archive/rpa-layer/`, `_archive/retro-engine/`, `_archive/fritz-polish/`) as the written Gate E record. Phase 0 plans for it.
- **The planned-test-name gate has a parser contract**, and my test names must satisfy it literally: a `-` bullet, optionally backticked, matching `test_\w+`, under a heading starting `**TDD test cases` (`tests/unit/fritz/test_completeness.py:318-335`). P4's fix takes the **fritz** version as its template, not the RPA one — `:308-313` raises `FileNotFoundError` on a missing path where the RPA copy `pytest.skip`s, which is exactly how the RPA gate went vacuous.
- **Deferral has a prescribed mechanism**: `@pytest.mark.xfail(strict=True, reason="Requires Phase N …")`, *"non-negotiable… Never use `skip` for deferred work"* (`sdd-workflow.md:85-87`). That is how the eight deferred detectors keep their names in `feature_steps.md` through Phases 2b–6 without the gate passing vacuously — and it is strictly better than my "written only when a query needs them", because a secretly-passing stub becomes a hard failure. Bug fixes additionally carry `@pytest.mark.regression` in the same commit as the fix, which covers the P5 `classical_invariant` repair.

Two corrections to what I wrote above. There are **eight** suite markers, not five — `_SUITE_MARKERS` at `tests/unit/rpa/test_foundations.py:35` includes `retro`, `retro_emu`, `retro_rom` — and `make test` is `-m "unit or rpa or retro"` (`Makefile:28`), which both `CLAUDE.md:244` and `docs/rpa/testing.md:21` state as `-m "unit or rpa"`. Also `rpa_cv` *unconditionally* skips when `QT_QPA_PLATFORM == "offscreen"` (`docs/ui-testing.md` §7.1), so the query corpus needs `make test-cv` on a real display and can never be smuggled into `make test`.

**And the gate I had missed entirely, which is why Phase 7 is split into 7a and 7b.** `ui-design-process.md` §5:

> *"Before implementing any visual phase (phases that change what users see), a two-round approval cycle MUST run and the sign-off MUST be recorded in `docs/<feature>/design-approval.md`… **Implementation of visual phases MUST NOT begin before sign-off is recorded.**"*

Phase 7 fixes the notation tab page and the pane captions. **That is a visual phase.** So it splits in two, and the order is not mine to choose:

1. **7a — diagnose and propose.** Run all three queries live, produce the before-reports, render the proposed fix with `tools/design/fritz_mock.py` (§4: offscreen bootstrap MUST reuse `tests/conftest.py::_bootstrap()`; output dir `Path(tempfile.gettempdir())/"caissa-design"` overridable by `CAISSA_DESIGN_OUT`, never a hardcoded `/tmp/`), build the sheet with `tools/design/review.py` — which opens it via `webbrowser.open`, never a shell `open` — and record your sign-off in `docs/features/rpa-design-vision/design-approval.md`.
2. **7b — implement, then re-review.** Edit the QSS, `caissa-eyes verify --baseline`, and **§6's phase-exit `tools/design/review.py --live` against the running app**, which is mandatory for visual phases (only structural ones are exempt).

This is a real conformance gap in my plan rather than a formality: the fix I am proposing changes corner radii, tab margins and a selected-tab fill on a signed-off design, and §5 exists precisely so that does not happen on my judgement alone. It also makes the feature eat its own cooking — `caissa-eyes inspect` produces the *evidence* for the round-2 sheet, which is the use case (a) loop this whole document opens with.

Gate F fixes the PR body's shape (`sdd-workflow.md:171-178`): title ≤ 70 chars, body says what **and why**, `make test` evidence, compatibility notes, `CHANGELOG.md` under `[Unreleased]` in the same commit, branch targets `JohnnyFoulds/caissa`. Gate E adds the real-execution requirement — *"All opt-in real-execution test tiers… have been run and pass — not skipped, not stubbed. Evidence of the run… included in the PR body"* — which is what the five checks in *Verification* below exist to produce. `docs/features/fritz-mode/feature_steps.md:110` gives the heading precedent to copy: `**Real-execution evidence (Gate D requirement):**`.

### Two idiom details from the reference workflow, and one bug in it

Reading `config_roundtrip.py` (the repo's before/after verification workflow) settled three small things:

- **Activity modules import `AppState` constants function-locally**, inside `precondition`, in all four workflow modules (`config_roundtrip.py:49-52`) — keeping the module import-light. `design_verify.py` follows it, which also happens to be what N-RPA-9 wants for `Segment`.
- **`postcondition` always calls `ctx.refresh_snapshot()`** rather than reusing `ctx.snapshot` (`:67`). That *is* the before/after mechanism: `precondition` reads the stale snapshot, `postcondition` re-reads a fresh one. My `DescribeScene` polling loop must use `refresh_snapshot`, not the cached one.
- **A latent bug worth not copying**: `register("config_roundtrip", _build_config_roundtrip())` (`:184`) invokes the factory **once at import time**, so the `uuid.uuid4()` "distinct test name per `rpa_run`" (`:168-170`) is fixed for the process lifetime and repeated runs are not independently verifiable. `design_verify` needs a per-run `report_id`, so it must pass the *callable*, not its result — or read the id from `ctx.run_dir`. Also `classical_invariant.py:68-71` builds its logger inside the method, against `CLAUDE.md:206-208`'s module-level `logging.getLogger(__name__)` rule; new modules follow CLAUDE.md.

### "The verify loop" is three loops, and this feature sits in all three

Worth stating plainly, because I searched for a document defining a single named "verify loop" and **there isn't one** — `verify loop`, `verification loop`, `re-verify` return zero hits repo-wide. What exists is three distinct loops at three scales, and the feature's obligations differ in each:

| Loop | Where it is normative | This feature's place in it |
|---|---|---|
| **The 5-step closed loop** — `CHECK_PRE → (CONVERGE →) ACT → SETTLE → VERIFY → STEP_EXIT` | `docs/rpa/state-machine.md` (`**Status:** Normative`), 14 sub-states at `:54-74`, transition table `:80-143` | the six activities and `design_verify` run inside it; per-phase actuation permissions at `:80-143` say **`VERIFY` may not actuate**, which independently forbids capturing from `postcondition` — a second reason for the `execute`-starts / `postcondition`-polls split |
| **The Render Loop** — edit `.qss` → `fritz_mock` → read the PNG → `compare.py` → repeat, then §6's `review.py --live` at phase exit | `ui-design-process.md:56-67` and `:102-109` | **this is the loop the feature upgrades.** Today its judgement step is "author reads the PNG". `caissa-eyes inspect` replaces reading with measuring, and §2's complaint about an agent that cannot see its own exports is the stated reason it was ever written that way |
| **Real Execution Before Done** — run it, observe the output, verify correctness | `CLAUDE.md:96-127` + `sdd-workflow.md:91-107` | Gate E evidence; the five checks in *Verification* below |

And the closest thing in the repo to a statement of what this feature is *for* is already written down, in `docs/claude_code/working-patterns.md:149-165`:

> *"Your first priority is programmatic control and observability of &lt;the thing&gt;, before any fixes. You must be able to see what I see: navigate, act, read state, capture output. Exhaust your own verification first. Escalate to me only when nothing is left that you can self-check."* — with the observed phrasings *"you take the screenshot"* and *"don't ask me to tell you what is wrong — instrument everything so you can drive it yourself."*

That is the same instruction as *"give you UI Vision… so the agentic workflow has eyes to see what I see"*, and it is the reason the skill's step 1 reads **"Taking the screenshot yourself is normal and expected. Do not ask for one."**

### Five smaller conformance items, one of which would have silently unlinted the new CLI

- **`ruff.toml`'s `include` is an explicit allowlist, and the doc that quotes it is stale.** `coding-standards.md:111` shows four entries; the live `ruff.toml` has **twelve**: `bin/Code/Base/CaissaErrors.py`, `bin/Code/Rpa/**`, `bin/Code/Fritz/**`, `bin/Code/Retro/**`, `bin/Code/Main/LogSetup.py`, `tests/unit/rpa/**`, `tests/unit/fritz/**`, `tests/unit/retro/**`, `tools/caissa-rpa`, `tools/caissa-retro`, `tools/design/**`. Three consequences, all of which shrink the change set: `tools/design/**` is **already** linted, so the `compare.py`/`ribbon_report.py`/`elements.py` edits in Phase 5 must pass ruff on day one rather than arriving unlinted; `tests/unit/rpa/**` is **already** covered, which is the second reason the corpus test belongs there rather than in a new `tests/rpa_cv/` directory; and **the only genuinely missing entry is `tools/caissa-eyes`**, which Phase 4b adds. Correct `coding-standards.md:111` while adjacent — a stale quote of an allowlist is exactly how a new file ships unlinted. E722 is deliberately not suppressed, so the `_sub_rects` / `_paint_overrides` guards use `except Exception`, never a bare `except:`.
- **The RPA purity tiers are numbered 0–3, not the four generalised names** (`feature_spec.md:102-114`): Tier 0 dependency-free, Tier 1 stdlib-only, **Tier 2 cv2/tesseract** (`Vision/{Availability,Template,Ocr,Manifest}.py`), Tier 3 Qt-touching. So `Segment.py`/`Annotate.py` join Tier 2 and the six pure modules are Tier 1 — which is also the second, independent argument for the `.coveragerc` omission, since Tier 2 *is* the omitted tier. RPA modules carry `:spec:` rather than the `:purity:` tag Fritz uses; new modules follow the RPA convention.
- **`compensable` must stay `False` on all six activities.** `activities.md:37` says `compensate` defaults to a no-op, but the code raises `NotImplementedError` (`Activities.py:112-120`) and `extending.md:97` agrees with the code. Since these are read-only observers there is nothing to undo, so leaving `compensable` at its default keeps DECIDE_RECOVERY from ever routing to COMPENSATE. Worth knowing rather than discovering: the doc is wrong, the code is right.
- **`architecture.md` §7 requires `@dataclass(frozen=True, slots=True)`** for dependency-free types. The five primitives add `slots=True`. And §5 forbids `abc.ABC` **and `typing.Protocol`** (the latter because it is `ABCMeta`-based), so the detector registry stays `dict[str, Callable[...]]` with plain functions — no `Protocol` for the detector signature, no ABC for `Activity`.
- **P3 should upgrade, not just patch.** `architecture.md:62-63` records that the RPA purity test *"walks direct imports only. Every new feature must resolve transitively"* — so `bin/Code/Rpa/` is under-enforced against the written standard. P3's fix therefore closes the `Vision/` prune **and** moves the check to transitive resolution, matching `tests/unit/fritz/test_completeness.py`. That is the difference between plugging the hole I need plugged and fixing the guard.

Finally, two doc corrections to make while adjacent, since both are one-liners and both cost the next reader real time: `docs/ui-testing.md:264`, `docs/rpa/README.md:88` and `CLAUDE.md:48` still point at `docs/features/rpa-layer/` (now under `_archive/`), and `_archive/rpa-layer/feature_spec.md:3` still reads `**Status:** Specified — implementation pending` for a layer that shipped and passed Gate E.

### Two governance gaps in the plan, now closed

- **A committed fixture PNG needs a manifest entry.** `Resources/Rpa/Templates/manifest.json` exists (currently `{"templates": []}`) and `test_every_workflow_template_ref_is_in_manifest` enforces coverage; `Manifest.load_and_verify()` checks path + SHA-256. My plan proposed committing one non-synthetic fixture — the `fritz_mock`-rendered ribbon crop. **It goes in `Resources/Rpa/Reference/` with the documented sidecar shape** (`templates_present` / `templates_absent` / `ocr_phrases_present` / `regions`, `vision.md:254-263`), and any template-tier PNG gets a manifest entry with its DPR, theme, ui_mode and translator. Every other CV fixture is drawn at test time and stores nothing, which is why this is one entry rather than a directory.
- **The `0.5`/`2.0` scale addition collides with the staleness warning.** `vision.md:108` — *"When a non-1.0 scale wins, `logger.warning` is emitted — the template is stale."* A pasted Retina crop matching at `2.0` is **not** a stale template, so the naive change makes every use case (b) invocation emit a false staleness warning, which trains everyone to ignore a real signal. Fix: `find_all` takes an explicit `scales=` argument, `Locate(fragment_path=…)` passes the DPR-factor set, and the staleness warning fires only for scales that are *not* a known DPR factor. Separately, `Region.resolve_phrase` must emit the documented non-object-tier warning (`vision.md:184-191`) whenever it falls below `objectname`, and journal `RegionMatch.source` + `confidence` the way CV tier wins already are — the phrase ladder is a new tier and inherits that obligation.

### Two things I found while checking, which strengthen P5 and P4

- **P5 already breaks a shipped regression workflow.** `_AssertClassicalToolbar.postcondition` (`classical_invariant.py:62-66`) iterates `snap.widget_tree` **flatly** for `TB_OPTIONS`/`TB_HELP`. `dump_ui` returns `{"roots": [...]}` with children *nested* (`Driver.py:383-404`) and `snapshot()` assigns `widget_tree = dump_ui(depth)["roots"]` (`:159`). A toolbar item is not a top-level window, so that scan cannot find it — and `docs/rpa/testing.md:90` says this workflow "must pass in CI on every PR that touches toolbar, config, or mode logic." P5 is therefore not a prerequisite my feature happens to need; it is an **existing defect in the primary Classical-Invariant guard**, and fixing it is worth doing on its own account. (`QtDriver.all_visible_widgets()` at `Driver.py:406` is a flat *Qt-side* list — useful to `QtDriver`, no help to the pure tier, which is why `Region.flatten` is still the fix.)
- **The normative N-RPA table now lives under `_archive/`.** `docs/features/_archive/rpa-layer/feature_spec.md:53-64` is the only place the rule texts exist. That is the same directory move that made P4's test-name gate vacuous. Phase 0 should either promote the rule table to `docs/standards/` or have the RPA docs point at it explicitly; a normative table in an archive folder is how the next person cites N-RPA-9 as wrongly as I just did.

Also stale and worth a one-line fix while nearby: `CLAUDE.md` lists `Resources/Rpa/{Templates,Reference,Fixtures}` but only `Templates/` exists — so `extending.md:122`'s `dry_run` path `Resources/Rpa/Fixtures/world.json` names a file that is not there.

---

## How Claude Code reaches for this

Everything above is a library. This section is the part that makes me use it, and it has three jobs — none of which the previous draft had:

1. **A trigger** — something that fires on *your* phrasing, without you naming a tool.
2. **A procedure** — the ordered loop, because the value is entirely in the order. Measuring *before* reading code is what separates a diagnosis from the grep-the-QSS reflex that produced corrections 4, 5 and 6.
3. **Pixels on disk** — because for a pasted image there is no file for cv2 to open.

### 1. The skill — `.claude/skills/design-eyes/SKILL.md`

Repo-local (`/Users/johannes/code/lucaschess/.claude/skills/`), not user-level, because it depends on Caissa's control socket, Caissa's region lexicon and Caissa's spec files. Nothing about it is portable, and pretending otherwise would make it fire in unrelated repos.

The `description` **is** the trigger — it is matched against the conversation, so it must enumerate your actual phrasings rather than a tidy category. All three of your queries are drawn from directly:

```yaml
---
name: design-eyes
description: >
  Diagnose a visual or layout complaint about the Caissa UI by measuring pixels
  locally before reading any code. Use when the user says a UI element "does not
  look right", "looks wrong", "looks off"; that spacing, padding, alignment or
  sizing is uneven or inconsistent between elements; that something "looks like
  disconnected components", "does not look like a group / a tab group / a page",
  or reads as a chip or tag instead of a bar; that a title bar, caption, tab,
  panel, ribbon, toolbar or button looks wrong; or when the user pastes a
  screenshot of the app together with any complaint about its appearance. Also
  use immediately before and after changing a .qss file or a paintEvent, to take
  a baseline and to verify the fix landed.
allowed-tools: Bash, Read, Grep, Glob, Edit
---
```

**Two triggers, not one.** The complaint trigger, and the *before-and-after-a-QSS-change* trigger. The second is what actually causes step 7 to happen; a skill that only fired on complaints would let me fix and never re-measure, which is the half of your loop I am most likely to skip, because a plausible fix feels finished.

The body is the seven-step loop from trace (c), written as imperatives, because every rule in it is one of my corrections:

```markdown
## The loop

1. GET PIXELS. Never reason about the app's appearance from memory, from an
   earlier screenshot, or from the stylesheet.
     user pasted an image  ->  python3 tools/caissa-eyes ingest
     no image provided     ->  python3 tools/caissa-eyes shot --phrase "<their words>"
   Taking the screenshot yourself is normal and expected. Do not ask for one.

2. GROUND their words:  tools/caissa-eyes locate --phrase "<their words>"
   If it returns null, DO NOT GUESS a region. Run `caissa-eyes regions`, show
   the user the list, and ask which one. A wrong region answers a different
   question confidently.

3. MEASURE:  tools/caissa-eyes inspect --phrase "..." --verbosity findings

4. READ THE FINDINGS. DO NOT OPEN A SOURCE FILE YET.
   Report the top finding back in the user's own vocabulary, and say which
   measurements support it. This is the step that shows you saw what they saw.

5. ONLY NOW resolve to code:  tools/caissa-eyes explain <finding_id>
   Findings carry ranked hypotheses, not causes. This step picks between them.

6. FIX with Edit. Ordinary work — the skill itself does not edit anything.

7. VERIFY:  tools/caissa-eyes verify --baseline <report_id>
   PASS requires BOTH: the targeted finding gone, AND no new finding at or
   above `warn` in the region. One without the other is not a pass.

## Hard rules

- A property absent from a node's `measured` set is NOT MEASURED. Say so.
  Never let an unmeasured property read as one that passed.
- Report `hypotheses` as hypotheses. Never state a mechanism as a cause before
  step 5 has confirmed it.
- NEVER edit a style rule reported `loaded_unmatched` (present in the stylesheet
  but matching no widget) or `matched_overridden` (a paintEvent wins). Editing it
  changes nothing. `QTabWidget::pane` in every theme file is the live example.
- If `inspect` finds nothing and the user can plainly see a problem, that is a
  DEFECT IN THIS TOOL. Add a corpus entry under Resources/Rpa/Design/queries/
  and say so. Do not silently fall back to guessing from source — that is the
  behaviour this skill exists to replace.

## Do NOT use this skill for

- non-visual bugs, crashes, or wrong behaviour
- "the code looks wrong" — that is ordinary review
- icon or artwork quality; this measures chrome, not content
- questions about what a control does
```

That last block matters as much as the description. A skill that fires on every mention of the UI is worse than none: it spends a capture and 2 KB of findings answering a question about behaviour, and it teaches me to ignore its output.

### 2. The CLI — `tools/caissa-eyes`

A **new file**, not new subcommands on `tools/caissa-rpa`, and the reason is structural rather than tidiness:

- `tools/caissa-rpa`'s `main()` checks `os.path.exists(_SOCK)` and `_die`s **before dispatch**, for every subcommand. But `ingest`, `inspect --image`, `explain` and `verify` must work with the app closed — that is the entire static-image path. Hosting them there means either weakening that check for the existing `run`/`status`/`cancel` verbs or special-casing inside it. A second entry point is cleaner than either.
- Different vocabulary and audience. `caissa-rpa` is workflow automation (`run`, `status`, `journal`, `cancel`, `workflows`); `caissa-eyes` is diagnosis. Mixing them makes `--help` unreadable, and `--help` is how I discover the commands.
- `tools/caissa-rpa` is mode `-rw-r--r--` — **not executable**, which is why my invocation of it during planning was permission-denied and I drove the socket from Python instead. `caissa-eyes` ships `0755`; a `chmod +x tools/caissa-rpa` goes in alongside as a one-line fix.

Everything else is copied deliberately from `tools/caissa-rpa` so the repo keeps one CLI idiom: module docstring printed as `--help`; `_REPO`/`_TESTS` prepended to `sys.path`; `_SOCK = os.environ.get("CAISSA_SOCK", "/tmp/caissa-control.sock")`; `_die(msg, code=1)`; `_json_out(data)` → `json.dumps(data, indent=2)`; `cmd_*` handlers in a `_COMMANDS` dict; `CaissaRpaClient` from `tests/ui/rpa_client.py` for the live verbs. Plain argv dispatch, no argparse — matching the existing file rather than introducing a rival convention.

The one deviation is the reason for the split: **each command declares whether it needs a running app**, and `main()` only checks the socket when the flag is set.

```python
_COMMANDS = {                      # (handler, needs_live_app)
    "ingest":  (cmd_ingest,  False),
    "shot":    (cmd_shot,    True),
    "locate":  (cmd_locate,  False),   # live preferred, --image accepted
    "inspect": (cmd_inspect, False),   # live preferred, --image accepted
    "explain": (cmd_explain, False),
    "verify":  (cmd_verify,  False),   # live preferred, --image accepted
    "regions": (cmd_regions, True),
    "doctor":  (cmd_doctor,  False),
}
```

| command | needs app | what it does | wraps |
|---|---|---|---|
| `ingest [--index -1] [--transcript P]` | no | decode the newest pasted image out of the session transcript to a PNG | new — §3 below |
| `shot [--phrase P] [--out PATH]` | **yes** | capture, cropped to the resolved region when `--phrase` is given | existing `screenshot [path]` verb + `Region.resolve_phrase` |
| `locate --phrase P \| --fragment F \| --text T` | no\* | ground words or a crop to a `Rect` + `object_name` + `sub_rect` | `Locate` activity |
| `inspect (--phrase P \| --image F \| --object-name N) [--verbosity] [--ocr]` | no\* | ground → describe → cluster → detect; ranked findings | `DescribeScene` + `Inspect` |
| `explain <finding_id>` | no | the step-5 bridge: `file:line` per finding with its three-valued `effective` state | `StyleSource.style_sources_for` |
| `verify --baseline <report_id> [--image F]` | no\* | re-run and diff; exit 0 only on the two-sided pass | `Workflows/design_verify.py` when a socket exists; otherwise `Report.diff` over a re-described `--image` |
| `regions` | yes | list the region names that *are* resolvable | `Region.named_regions` |
| `doctor` | no | cv2 / pytesseract / socket / transcript-dir availability | mirrors `caissa-rpa doctor` |

\* live preferred; a static PNG is accepted via `--image`. When neither a socket nor `--image` is available the command `_die`s naming the specific missing thing — *"no socket at /tmp/caissa-control.sock and no --image; start the app with tools/caissa or pass --image PATH"* — never a generic failure, because a generic failure is how I abandon the tool and go back to grepping the QSS.

**`explain` is a separate command on purpose.** It is `style_sources_for` given a CLI surface, and folding it into `inspect` would defeat the whole steps-4-and-5 discipline: if a `file:line` appeared in the same output as the finding, I would jump straight to editing. That is precisely how I named a dead `::pane` rule three times in a row.

### 3. `ingest` — the pasted-image bridge

Without this, use case (b) does not exist. Verified mechanics, from parsing the transcript rather than from assumption:

- A pasted image is an inline block in the session `.jsonl`: `{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "…"}}`. **There is no filename field.**
- The transcript lives at `~/.claude/projects/<slug>/<session-uuid>.jsonl`, where `<slug>` is the cwd with `/` → `-`. Confirmed present for this repo as `-Users-johannes-code-lucaschess`, with sibling slugs for the git worktrees.
- There is no `CLAUDE_TRANSCRIPT_PATH` in the environment, so the path must be derived.

Resolution order, each step failing loudly rather than guessing:

1. `--transcript PATH` when given.
2. else the newest `*.jsonl` by mtime in `~/.claude/projects/<cwd-slug>/`.
3. Scan lines **from the end**, collecting `content` blocks with `type == "image"`; take `--index` (default `-1`).
4. Decode to `$CAISSA_VISION_OUT/query/<n>.png` (default `~/.caissa/vision`) and print `{"path", "width", "height", "bytes", "assumed_dpr", "warnings"}`.

`assumed_dpr` is the trap that would otherwise bite on the very first use: a macOS screenshot is 2×. When a socket is available, `ingest` compares the image width against the live window's logical width and reports `2.0` when it is ≈2×. Otherwise it reports **`null`** plus `"dpr_unknown"` — it never assumes `1.0`, because assuming 1.0 halves every measurement and yields plausible wrong numbers, which is the failure class this entire document is about. It is also the second reason `Template._MULTI_SCALES` gains `0.5` and `2.0`.

Two constraints, because they bound the blast radius: `ingest` is **read-only on the transcript** and writes only inside `$CAISSA_VISION_OUT`; and the transcript format is not a stable contract, so a line that is not JSON or that lacks `content` is **skipped, not fatal**, and total failure degrades to `_die("no pasted image found in <path>; pass --image PATH")` — an instruction I can act on rather than a stack trace.

### 4. The output budget again — this time for a tool result

The verbosity table earlier governs `scene.txt`. A tool result has a tighter budget, because it enters my context whether or not it was useful. So `caissa-eyes` defaults to `--format agent`:

- findings only, ranked, **≤ 2 KB**;
- one block per finding: `[severity] kind nodes=N`, then `measured:`, `hypotheses:`, `confirmed_by:` (or `(pending)`);
- the `report.json` path, so I can read slices with `Read`/`jq` when a finding needs detail;
- **the last line is a single `NEXT:` instruction** — `NEXT: tools/caissa-eyes explain f1`, or `NEXT: region unresolved — run caissa-eyes regions and ask the user which one`.

`--format json` for machine use, `--format human` for you.

`NEXT:` is not decoration. A seven-step loop stalls at step 4, because step 4 — a ranked finding with measurements attached — already *feels* like the answer. One imperative line at the end of the output is the cheapest available mechanism for getting to step 5, and step 5 is what makes step 4 safe to act on.

### 5. What this deliberately is not

- **It never edits.** Diagnose and verify only; `explain` names the file and line and stops. Four of my seven corrections were wrong *mechanisms* — a tool authorised to act on its own diagnosis would have produced a `setSizePolicy` no-op on a widget that already spans its pane, plus three separate edits to a stylesheet rule that matches no widget in the application. Read-only here is not caution, it is calibration to a measured error rate.
- **No MCP server.** A stdio server would surface these as native tools with schemas, but it duplicates every signature, adds a process and a `.mcp.json`, and takes away your ability to run the same command by hand. The repo's idiom is `tools/*` driven over Bash and this follows it. If invocation reliability turns out to be the real bottleneck, an MCP wrapper *over the same CLI* is a later additive change, with the CLI still the single implementation.
- **Not a slash command as the primary path.** `/design-eyes` would work but requires you to remember it, and the whole point of correction 7 is that *I* recognise the query. A skill description is matched automatically; a slash command is not. A one-line `.claude/commands/design-eyes.md` delegating to the skill is included as an explicit escape hatch, but the skill is the mechanism.

---

## End-to-end traces

### (a) Design against a reference image

```
~/Pictures/fritz-reference/ribbon_home.png        (oracle, uncommitted, §3)
  → Capture: cv2.imread (reference is a file, not a widget)
  → Segment.palette + fill_regions + glyph_boxes + row_bands
  → Scene.from_observations()                      reference scene
  → Report.write_spec()  →  Resources/Rpa/Design/ribbon.spec.json     ← single source of truth
                                                    │
tools/design/fritz_mock.py --scene ribbon_home      │  (PySide6 + real .qss, §1)
  → Capture.grab(widget) → Screenshot               │
  → same Segment/Scene pipeline → candidate scene   │
  → AssertDesignSpec(spec) ←────────────────────────┘
  → Report.emit(): report.json + scene.txt + annotated.png + crops
  → I read scene.txt and report.json — no image needed
  → tools/design/review.py adds a semantic verdict column beside its numeric score
  → docs/fritz/design-approval.md row pre-filled; you sign off
```

### (b) Interactive repair — you paste a crop

```
you paste a crop  →  the skill fires on your complaint
  → tools/caissa-eyes ingest
      decodes the newest {"type":"image"} base64 block out of
      ~/.claude/projects/<cwd-slug>/<newest>.jsonl  →  $CAISSA_VISION_OUT/query/<n>.png
      (there is NO path on a pasted image; without this step cv2 has nothing to open)
      prints assumed_dpr — 2.0 if it is ≈2× the live window, else null, never 1.0
  → Locate(fragment_path=...): Template.find_all(live_capture, crop, 0.80) → Match.rect
      live capture preferred; falls back to a fritz_mock offscreen render
  → Measure.owner_of(rect, snapshot)  → widget dict → "WRibbonTabBar" (_FlatTabBar)
  → Measure.sub_rect_of(widget, rect) → {"index": 1, "role": "tab", "node_id": "tab[1]"}
  → StyleSource.style_sources_for("WRibbonTabBar", "_FlatTabBar", qss, src)
      → fritz-widgets.qss:282  ::tab {padding: 4px 13px}    effective=True   geometry
        fritz-widgets.qss:290  ::tab:first {background-...}  effective=False  INERT
        Fritz.qss:1015         ::tab:first {same}            effective=False  shadowed+INERT
        WRibbon.py:118         _BG_FIRST = #007acc           effective=True   fill
  → DescribeScene on a padded context box around rect
  → MeasureSpacing across all four bases
  → EmitVisionReport → report.json + scene.txt (+ annotated.png as your evidence)
```

<a id="scale-trap"></a>**The scale trap in `Locate`, verified.** This is the single statement of why `_MULTI_SCALES` grows; the file list, the `Locate` ladder and `ingest`'s `assumed_dpr` paragraph all refer back here. Your pasted crop came from a Retina screenshot at DPR 2; the live capture, once `logical()`-converted, is DPR 1. `Template._MULTI_SCALES` is `[0.95, 1.05, 0.90, 1.10]` (`Template.py:~40`) — a ±10% window that **cannot** match a 2× crop, so `find_all` would return nothing and I would wrongly report "I cannot find that in the UI". Fix: add `0.5` and `2.0` to the scale list, and match against `Screenshot.rgb` (physical) as well as `logical()`. Without this, use case (b) fails on the most common input there is: a screenshot taken on this machine.

If you *describe* it in words instead of pasting, `Locate(text=...)` fires instead — with the honest caveat from the Activities section: `find_phrase` matches exact word sequences, so a literal label works and a description like *"the tab next to File"* does not. It degrades to a region description that I then narrow down myself.

The bridge that makes this useful is `pixels → Rect → sub_rect → objectName → governing style source`. That is what turns "this looks wrong" into "edit `WRibbon.py:118` — and note `fritz-widgets.qss:290` looks like the right place but is inert, as does `Fritz.qss:1015`."

### (c) Interactive repair — you describe it in a sentence, and I close the loop

This is the trace the plan was missing, and it is the one your side-panel question needs. Note where the code enters: **fifth**, not first.

```
you: "the title bars in the side panel do not look right to me"  [+ full-window PNG]

 0  RECOGNISE the design-eyes skill description matches "do not look right" +
              "title bars" -> the skill loads and I follow its loop instead of
              reaching for grep. Then: caissa-eyes ingest (you pasted an image)
              or caissa-eyes shot --phrase "the side panel" (you did not).
              WITHOUT THIS STEP EVERYTHING BELOW IS UNREACHABLE.

 1  GROUND    Region.resolve_phrase("the side panel", snapshot, capture)
              lexicon -> #WFritzRightCol -> Rect(748,200,566,720)    source=objectname
              (returns None rather than guessing; then I ask you which region, listing
               named_regions() — a wrong region answers a different question confidently)

 2  DESCRIBE  DescribeScene(target="located", with_pixels=True, with_style=True)
              4 panes, 37 nodes. OCR off by default; on here, to label the captions.

 3  CLUSTER   Measure.peers(scene) -> "pane_caption" n=4, + 2 other clusters
              THIS is what turns your plural "the title bars" into a comparable set.

 4  DETECT    Detectors.run_all(scene, panes.spec.json)
              -> invisible_fill(x4) warn  + 3 ranked hypotheses, confirmed_by=(pending)
                 missing_child(x4) warn, contrast(x4) warn, text_duplication info
              Ranked. Top finding is the SYMPTOM plus candidate mechanisms.
              NO CODE READ YET — and no mechanism asserted yet either.

 5  BRIDGE    StyleSource.style_sources_for("WFritzPaneTitle", "_PaneTitleBar", qss, src)
              -> fritz-widgets.qss:197-214  qproperty-titleTop/{CHROME_SURFACE}   effective
                 Caissa.colors:77-79        CHROME_SURFACE -> #252526             resolved
                 WFritzPane.py:257-272      paintEvent fills self.rect() w/ gradient
              => hypothesis 1 CONFIRMED, hypothesis 3 also true (direction inverted
                 vs. the approved mockup). confirmed_by set. Now it is a cause.
              THIS is the step that makes step 4 safe to act on.

 6  FIX       I edit the governing source — here, the qproperty values in
              fritz-widgets.qss, not the widget. Ordinary work, outside this feature.

 7  VERIFY    Workflows/design_verify.py --baseline <report_id>
              re-capture, re-describe, re-detect, Report.diff(before, after)
              PASS iff the targeted finding is GONE and no new finding appeared.
```

Steps 0, 1, 3, 4 and 7 are all new. Steps 2, 5 and 6 are what the previous draft had — which is to say **the previous draft was the middle of this pipeline with both ends missing.** It could describe a region I had already identified and tell me which file governs it; it could not work out *which* region you meant, *which* elements you meant, *what* was wrong with them, or *whether my fix worked* — and, per correction 7, it had no step 0 at all, so in practice nothing would have started the pipeline.

Note what step 5 does in the corrected version: it **selects among hypotheses**, and it confirms *two* of the three. That is the shape of a real diagnosis — the gradient straddles the background (hypothesis 1) *because* its direction is inverted relative to the mockup (hypothesis 3), and the fix addresses both at once. A pipeline that forced a single mechanism at step 4 would have picked one and been half right at best.

It is also worth being explicit that **step 6 lands somewhere I would not have guessed from step 4**: the fix is in the QSS `qproperty` values, not in the widget. My wrong mechanism pointed at `_PaneTitleBar`'s layout. The right one points at three colour values in a stylesheet and a palette file. Same symptom, entirely different file — which is the whole argument for keeping steps 4 and 5 separate rather than letting a detector name a file.

Step 7 is the one you named explicitly and it deserves its own note, because the naive version is wrong. Asserting only "the targeted finding is gone" passes if I make the captions full-width by deleting them. So the pass condition is **two-sided**: the finding is gone **and** `Report.diff` shows no new finding at or above `warn` anywhere in the region. `Report.diff` joins on `node_id`, which is why `node_id` had to be positional and stable — a text-derived ID would churn the moment a caption changed and every before/after diff would be noise.

---

## The query corpus — the actual acceptance criterion

You said I will need multiple tests like this, and that is the right standard: **this feature is not measured by branch coverage, it is measured by whether it answers questions you have actually asked.** So the corpus is a committed artefact and the suite that gates the feature.

`Resources/Rpa/Design/queries/<slug>.json`, one per query:

```json
{
  "slug": "side-panel-captions",
  "query": "the title bars in the side panel do not look right to me",
  "scene": "full",
  "render": "tools/design/fritz_mock.py --scene full --variant dark",
  "expect_region": {"phrase": "the side panel", "source": "objectname",
                    "object_name": "WFritzRightCol"},
  "expect_cluster": {"cluster_id": "pane_caption", "size": 4},
  "expect_top_finding": {"kind": "invisible_fill", "min_nodes": 4, "severity": "warn"},
  "expect_absent": ["spacing_uniformity", "fill_extent"],
  "expect_hypothesis_ruled_out": "fill is sized to its text",
  "notes": "captions ARE full-width and ARE painted; the gradient #252526->#363636 straddles the pane background #2d2d2d, so the band is invisible. fill_extent MUST NOT fire — see the corrected diagnosis above."
}
```

`tests/unit/rpa/test_query_corpus.py` renders each scene with `fritz_mock`, runs ground→describe→cluster→detect, and asserts the `expect_*` keys. It carries module-level `pytestmark = pytest.mark.rpa` with `@pytest.mark.rpa_cv` per test function — the `test_vision.py:22,110` pattern — so `tests/conftest.py:16-33` skips it automatically when cv2 is missing or the platform is offscreen, and it never needs a `tests/rpa_cv/` directory of its own. It runs under `make test-cv` on a real display; `rpa_cv` skips unconditionally when `QT_QPA_PLATFORM == "offscreen"` (`docs/ui-testing.md` §7.1), so it can never be smuggled into `make test`. Four properties make this worth doing:

- **The renders are ours**, so nothing here trips `ui-design-process.md` §9 — no Fritz reference crop is committed.
- **`expect_absent` is as important as `expect_top_finding`.** A detector suite that fires on everything is useless; asserting that `spacing_uniformity` stays quiet on this scene is what keeps precision honest.
- **Assertions are structural, not pixel-exact** — a `kind`, a cluster size, a minimum node count. Font changes move pixels and must not break the corpus. This is the same synthetic-for-absolutes / real-render-for-relations split as the rest of the test strategy.
- **The corpus grows by one entry every time you ask me something the tool gets wrong.** That is the maintenance model, and it is the only one that keeps a "does this look right?" tool aligned with what actually looks wrong to you.

Seed entries, both of which my earlier drafts failed:

| slug | query | expected top finding | what it guards |
|---|---|---|---|
| `ribbon-tab-spacing` | *"the spacing between File and Home is not the same as the other tabs"* | `spacing_uniformity` basis `perceived`, 6 nodes | the four-basis model; that three bases would say "uniform" |
| `side-panel-captions` | *"the title bars in the side panel do not look right to me"* | `invisible_fill`, 4 nodes | phrase grounding, peer clustering, gradient fills — **and that `fill_extent` stays silent** |
| `notation-tab-group` | *"the tabs in the notation panel look like disconnected components"* | `surface_broken`, corner break first | `Corner`, `Surface`, `Seam.shows_owner`, `orphan_style_rule` — **and that `spacing_uniformity` reports `uniform`** while `QTabWidget::pane` reports `loaded_unmatched` |

The third entry, in full, because its `expect_*` keys are the least obvious:

```json
{
  "slug": "notation-tab-group",
  "query": "the tabs in the notation panel look like disconnected components",
  "expect_region": {"phrase": "the notation panel", "source": "panespec",
                    "pane_key": "pgn"},
  "expect_cluster": {"cluster_id": "notation_tab", "size": 5},
  "expect_top_finding": {"kind": "surface_broken", "min_nodes": 2, "severity": "warn",
                         "breaks": ["corner_tl_radius_8", "corner_tr_radius_8",
                                    "seam_closed", "fill_mismatch"],
                         "first_break": "corner_tl_radius_8"},
  "expect_seams": {"px": 2, "shows_hex": "#1e1e1e", "shows_owner": "ancestor",
                   "closed": true},
  "expect_corners": {"node": "notation_content", "which": "tl", "radius_px": 8,
                     "shows_hex": "#1e1e1e", "shows_owner": "ancestor"},
  "expect_also": ["peer_adjacency", "orphan_style_rule", "invisible_fill"],
  "expect_verdict": {"spacing_uniformity": "uniform"},
  "expect_style_state": {"selector": "QTabWidget::pane",
                         "file": "Resources/Styles/Caissa.qss", "line": 214,
                         "effective": "loaded_unmatched"},
  "expect_measured": ["fill", "ink", "borders", "corners", "seams"],
  "notes": "There is NO QTabWidget in the app (modern_fritz_ui.py:175,184) — a bare QTabBar plus a sibling _FlowingNotation(QTextEdit). The 8px corners come from the generic QTextEdit rule at Caissa.qss:165-173. QTabWidget::pane at Caissa.qss:214-218 matches nothing. spacing_uniformity PASSES this scene, and StyleSource must NOT call the ::pane rule effective — both are the point of the entry."
}
```

`expect_verdict` is a new key and the most valuable one in the corpus: it asserts that a named detector reports a *specific non-finding*. `spacing_uniformity` must return `uniform` here — not be absent, but actively report uniform — because that is the documented false negative, and pinning it stops anyone from later "fixing" `spacing_uniformity` to fire on this scene and losing the distinction between *uneven* and *should-be-zero*.

Along with `expect_absent`, this is the pattern worth carrying forward: **the corpus records the plausible wrong answer and forbids it.** Entry 2 forbids `fill_extent`; entry 3 pins `spacing_uniformity` to its correct-but-unhelpful verdict. A query worth adding is usually one where something confidently misfired, so the misfire is the assertion.

Two entries is not a suite, and I should say so plainly: the corpus is the part of this plan that is **deliberately incomplete at design time**, because I cannot invent the queries. Phase 7 exists to add entries from real use, and the first honest measure of the feature is how many of your next five questions it gets right without me reading code first.

---

## Collapsing the copies of design truth

`Resources/Rpa/Design/ribbon.spec.json` becomes canonical, generated once from the reference by `Report.write_spec()` and reviewed by hand:

```json
{
  "name": "ribbon", "source_ref": "ribbon_home.png", "captured_at": "...",
  "themes": {
    "light": {"chrome": "#efeff2", "separator": "#cccedb", "accent": "#007acc",
              "body_text": "#1e1e1e", "disabled": "#a2a4a5"},
    "dark":  {"chrome": "#252526", "separator": "#9daab8", "accent": "#007acc",
              "body_text": "#d4d4d4"}
  },
  "geometry": {"total_height": 143, "qat_height": 29, "tabrow_height": 21,
               "rule_height": 1, "content_height": 91, "large_btn_height": 66,
               "large_icon_size": 32, "checkbox_indicator_px": 11},
  "elements": {"tab.file": {"fill": "accent", "pad_left": 13, "pad_right": 13}},
  "invariants": [
    {"key": "tabs_perceived_uniform", "kind": "uniformity",
     "nodes": "tabbar/tab[*]", "basis": "perceived", "axis": "x",
     "tolerance_px": 2, "severity": "warn"}
  ],
  "known_deviations": [
    {"key": "tabs_perceived_uniform", "reason": "open defect — only File and Home are painted",
     "issue": "TBD", "expires": "on fix"}
  ]
}
```

`Resources/Rpa/Design/panes.spec.json` is the second one, and it is generated from the **approved mockup** (`tools/design/fritz_mock.py:225-317`) rather than from Fritz, which is why it can carry absolute values honestly — the mockup is our own render and it is what you signed off:

```json
{
  "name": "panes", "source_ref": "fritz_mock.py:render_pane_titlebar",
  "roles": {
    "pane_caption": {
      "height": 22, "pad_x": 8, "fill_extent": "container",
      "fill": {"kind": "gradient_v", "start": "#3a3a3c", "end": "#2d2d2f"},
      "fg": "#d4d4d4", "font_weight": "bold",
      "children": ["title_label", "menu_button", "close_button"],
      "child_size": {"menu_button": [16, 16], "close_button": [16, 16]}
    }
  },
  "invariants": [
    {"key": "caption_fill_visible", "kind": "fill_visible",
     "nodes": "pane/caption", "min_delta": 12, "severity": "warn"},
    {"key": "caption_gradient_darker_than_body", "kind": "ordering",
     "assert": "caption.fill.hex_end is darker than pane.background", "severity": "warn"},
    {"key": "caption_buttons_present", "kind": "children_present",
     "nodes": "pane/caption", "severity": "warn"}
  ],
  "known_deviations": [
    {"key": "caption_fill_visible", "reason": "open defect — Caissa palette gradient straddles pane bg",
     "issue": "TBD", "expires": "on fix"},
    {"key": "caption_buttons_present", "reason": "open defect — QToolButton min-size 32px vs fixed 16px",
     "issue": "TBD", "expires": "on fix"}
  ]
}
```

Note `caption_gradient_darker_than_body`, which is the invariant that would have caught this bug at authoring time. The shipped gradient runs **light-downward** (`#252526 → #363636`, ending *lighter* than the `#2d2d2d` body); the approved mockup runs **dark-downward** (`#3a3a3c → #2d2d2f`, ending at the body colour). That single inverted relation is the whole defect, it is expressible as an ordering invariant with no absolute pixels in it, and it survives any palette change — which is exactly the property hard problem 3 requires of a spec key.

Both spec files start life with `known_deviations` covering the open defects, so the gate is honest on day one rather than red on day one.

`known_deviations` is not bookkeeping — it is what stops this becoming noise. Today the ribbon *does* violate `tabs_perceived_uniform`, so the moment `AssertDesignSpec` runs in a gate every run fails, and a permanently-red check is a check nobody reads. An acknowledged deviation reports `warn` with its reason attached instead of `fail`, and — the important half — **an invariant that starts passing while a deviation is still recorded is itself a finding** (`deviation_stale`). That is how the file cleans itself up rather than accumulating permanent excuses.

Migration order matters, so nothing breaks mid-way:

1. Write the spec file with values **matching today's `ribbon_report.py:49` `TARGET`** exactly — no behaviour change, so the scorecard output is byte-identical and provably so.
2. Repoint `ribbon_report.py` at the spec; delete `TARGET`. Re-run, diff the output against step 1.
3. Repoint `elements.py` targets at the spec; delete its copies.
4. **Only then** reconcile the genuine contradictions as a separate, visible decision recorded in `docs/fritz/decisions.md`. Resolving a real disagreement is a design decision for you, not a refactor I should bury inside a migration.
5. `docs/fritz/ribbon.md` §"Measured reference" prose becomes a pointer to the spec.

### It is six copies, not three

I under-counted in my first draft. The ribbon's design values are currently duplicated across:

| # | Location | Form |
|---|---|---|
| 1 | `docs/fritz/ribbon.md` §Measured reference | prose |
| 2 | `tools/design/ribbon_report.py:49` `TARGET` | Python dict, light palette only |
| 3 | `tools/design/elements.py:52` | Python dict, per-element |
| 4 | `tools/design/compare.py:115` `chrome_mask` `PALETTE` | hardcoded 3-colour tuple |
| 5 | `tools/design/compare.py:166` `row_ink_profile(bg=...)` | hardcoded default arg |
| 6 | `Resources/Styles/fritz-widgets.qss` `{KEY}` + `Code.dic_colors` | the values that actually ship |

Copies 4 and 5 are the ones I missed and they are the most dangerous, because they are **default arguments** — a caller passing a dark-variant image gets a plausible number with no error at all. Your crop is `#252526`; `chrome_mask` would return a nearly empty mask and `masked_mean_diff` would then score "identical" over almost no pixels. **A silently-wrong 4.2 is worse than a crash.**

Copy 6 is the one that cannot be collapsed away — `dic_colors` genuinely is the shipping source of truth for colours, and the spec is the source of truth for the *reference*. The relationship between them is exactly what `AssertDesignSpec` checks, so the target is five copies collapsing into one spec plus the live palette, not six into one.

The dark palette is added to the spec because your crop proved dark-variant input is real and currently unhandled.

---

## Prerequisite fixes (scoped, not silently inherited)

These are **blocking**, and P5 is the one that would have wrecked the whole feature had I not checked. Each is a real bug in the existing layer that this feature merely happens to trip over first.

| # | Defect | Where | Why it blocks |
|---|---|---|---|
| **P5** | **The object tier is blind below the root window.** `Resolve.visible_elements:200` and `_object_candidates:316` iterate `snapshot.widget_tree` **flatly, with no recursion into `children`** — and `QtDriver.snapshot:159` sets `widget_tree = dump_ui(depth)["roots"]`. So the object tier only ever sees **top-level windows**. Nothing anywhere in `bin/Code/Rpa/` flattens that tree. | `Resolve.py:200,316` + `Driver.py:159` | `owner_of`, `named_regions`, `peers` and every activity's precondition are all built on this. Today `visible_elements` on the live app returns roughly *one element*. **This is the single largest prerequisite in the plan and I had not noticed it.** |
| P1 | `_build_activity` passes kwargs that do not exist (`TakeScreenshot(filename=)`, `SwitchTab(tab_name=)`, `GetText(output_key=)`, `TypeInto(text=, clear_before=)`, `ElementExists(output_key=)`) → `TypeError` → `{"error": "cannot build activity"}` for **5 of 9** types. Also passes `Selector` *objects* where activities treat `self.selector` as a **string**, so even `Click` never matches. | `Service.py:565-581` | New activities unreachable over the wire. |
| P6 | `Rect` has exactly `right`, `bottom`, `cx`, `cy`, `contains`, `iou` — **no `intersects`, `intersection`, `area`, `translate`, `inset`, `contains_point`.** Meanwhile `Template.py:46` carries a *second* IoU implementation on raw tuples. | `Types.py:23-101`, `Template.py:46` | `nodes_in`, `to_logical`, region containment and border stripping all need them. Add to `Rect` (dependency-free tier, trivially testable) and repoint `Template._iou` at `Rect.iou` to kill the duplicate. |
| P7 | There is **no `resolve_all`**. A class-only selector produces every match at confidence 0.60, then `_pick_best:390` collapses it and raises `AmbiguousMatchError` unless `index` picks one. | `Resolve.py:367-390` | `peers()` is fundamentally a multi-match query. It needs the list, not the winner. |
| P2 | `Runner.__init__` stores `self._run_dir` but never passes it to `Context` (`:208`), so **`ctx.run_dir` does not exist**. | `Runner.py:208` | `EmitVisionReport(out_dir="")` has nowhere to write. One line. |
| P3 | `test_vision.py:71` prunes the entire `Vision` directory from the cv2 import guard, so top-level `cv2` is legal in *any* `Vision/` module — **and the RPA purity test walks direct imports only**, where `architecture.md:62-63` says every feature must resolve **transitively**. | `tests/unit/rpa/test_vision.py:71`, `test_completeness.py` | The purity boundary that makes the pure-tier logic testable is unenforced twice over: a pure module may import cv2 outright, and may reach it through one hop regardless. Fix closes the prune **and** moves to transitive resolution, matching `tests/unit/fritz/test_completeness.py`. |
| P4 | `test_completeness._planned_test_names` reads a path now under `_archive/`, so it returns `[]` and `test_every_planned_test_name_exists_in_suite` **passes vacuously**. | `tests/unit/*/test_completeness.py` | The SDD gate meant to check my new test names against the spec is a no-op. Fixing it makes Phase 0 binding. |

**On P5.** My plan spent a page on `owner_of` hit-testing a nested tree, and a paragraph insisting the test must use a *deeply nested* widget — while the code it calls cannot see past the root. That is the difference between reading a function's intent and reading its loop. The fix is a `flatten(widget_tree) -> list[dict]` helper in the pure tier that accumulates parent offsets as it descends, and it is genuinely small; what matters is that it is a **prerequisite for four of the eight new modules**, so it moves to the very front of Phase 1 and gets its own test asserting a known 4-deep widget is reachable and its rect is capture-absolute.

P3 and P4 deserve a note of their own, because they are the same failure twice: **a guard that silently stopped guarding.** Both report green today. Both would let this feature ship with the exact class of defect it is built to detect — which would be a poor advertisement for it.

One more, non-blocking but worth fixing while nearby: `Ocr.find_phrase`'s confidence gate is **all-or-nothing** (`Ocr.py:94-96`) — a single word below `confidence_threshold` discards the entire phrase match, and the mean is computed but used only for reporting. Combined with `_UPSCALE_FACTOR = 2` and the default PSM 3, that fully explains why it found nothing on the tab crop. `read_words` sidesteps it by returning everything with per-word confidences; `find_phrase` should additionally forward `Selector.threshold`, which `Resolve.py:460` currently drops on the floor.

`docs/rpa/activities.md` parameter tables are stale across the board — author against `Activities.py`, not the doc, and correct the doc as part of Phase 5.

Deferred as out of scope, noted so they are not forgotten: stale `docs/features/fritz-polish/` path in `CLAUDE.md` and `ui-design-process.md` §10; `fritz_compare.py` reading `FRITZ_REF` instead of `CAISSA_FRITZ_REF` and writing into the oracle dir; missing `tools/design/README.md`; `compare.py`'s documented-but-absent CLI; `ribbon_report.py:319` resizing the candidate with `LANCZOS` before diffing (the same resampling trap as hard problem 4, in the existing tool).

---

## Phase 0a — this document lands in the repo before anything else

**Nothing above starts until this plan itself is committed.** It is currently a planning-session
artefact living outside the repo, and it is the only place four things exist:

- **the seven corrections**, with the wrong answer stated next to the right one. A spec records
  what to build; it does not record that `spacing_uniformity` *passes* query 3, or that
  `fill_extent` was ranked first and was wrong. Those are the constraints that make the design
  make sense, and they are exactly what gets smoothed away when a document is rewritten into a
  spec — at which point someone reintroduces the mistake because the reason not to is gone;
- **the empirical measurements** — the `#007acc` fill box, the four `F-i-l-e` glyph components,
  the 6-tab `perceived` spread of 12/13/24/24/25, the `#1e1e1e` seams, the 8 px corner notch, the
  `dump_ui 12` tree showing no `QTabWidget` — together with **which of them were measured with the
  wrong fonts**. The re-measurement obligation is only legible next to the numbers it applies to;
- **the negative results**: that PSM 3 finds nothing, that a global colour bbox is contaminated,
  that three of the eight speculative detectors have never fired. Nobody re-derives a negative
  result; they just repeat the experiment;
- **the seven prerequisite defects** (P1–P7) with the evidence that found them, including P5,
  which is an existing bug in the shipped Classical-Invariant guard and worth fixing regardless of
  whether this feature is ever built.

So it is committed **verbatim**, first, as its own artefact:

```
docs/features/rpa-design-vision/design-record.md
```

Four decisions about that, each with a reason:

- **It is not `initial_idea.md`.** That artefact has a fixed shape in this repo — ~71 lines of
  Problem Statement, Business Requirements, Confirmed Decisions and Open Questions
  (`_archive/rpa-layer/initial_idea.md` is the template in practice). This is ~2 200 lines of
  design exploration. Forcing it into that filename means losing one of the two documents. The
  conforming `initial_idea.md` is written in Phase 0 and **derives from** this one, the same way
  `feature_spec.md` does.
- **A fifth non-templated artefact has precedent** — `_archive/retro-engine/decisions.md`. And it
  is safe to add: no test asserts the artefact *set*. The only doc-parity test is
  `feature_steps.md` test-name parity (`tests/unit/rpa/test_completeness.py:175-238`), and Sphinx
  never reads it — `docs/conf.py` loads no `myst_parser` and sets no `source_suffix`, so markdown
  under `docs/` is invisible to `make docs -W` and cannot raise a not-in-any-toctree error.
- **Verbatim, in the first person, not rewritten into repo voice.** The value of "my flagship
  detector passes query 3" is that I wrote it about my own work; in the third person it becomes a
  design note nobody weights. `_archive/rpa-layer/initial_idea.md` already sets the precedent for
  origin narrative in a committed artefact. A header block is prepended stating what the file is,
  that it is a verbatim record rather than a live spec, and that **the spec governs on conflict**
  (`sdd-workflow.md:32-34`) — so a stale sentence here can never outrank `feature_spec.md`.
- **No §9 exposure.** The document embeds no image and no reference crop. It quotes *measured
  values* from the Fritz reference (`#efeff2`, `#cccedb`, `#007acc`, band heights), which are
  facts about an observation, not the observation — the same thing `docs/fritz/ribbon.md`
  §"Measured reference" already commits today.

Landing it also has an immediate practical payoff: from that commit on, Phase 0's four artefacts
are a **derivation** rather than a fresh authoring pass, and every `file:line` claim in this
document becomes reviewable in a PR diff instead of in a chat scrollback.

Commit shape: `docs(rpa): add design-record for RPA design-vision feature` on branch
`feat/rpa-design-vision`, PR to `JohnnyFoulds/caissa`. Docs-only, so no `CHANGELOG.md` entry —
per the changelog rule, doc-only commits are excluded unless they change observable behaviour.

---

## Phases and gates

| Phase | Work | Gate |
|---|---|---|
| **0a Land this plan** | Commit this document verbatim as `docs/features/rpa-design-vision/design-record.md`, with the header block described above. Nothing else. | The file is on `main` (or in an open PR) before Phase 0 begins. `make docs` still passes, and `make lint` is unaffected — `ruff.toml`'s `include` allowlist covers no `docs/**` path. |
| **0 SDD** | `docs/features/rpa-design-vision/{initial_idea,feature_spec,feature_steps,implementation_plan}.md`, **derived from `design-record.md`** rather than authored fresh. Number new rules `N-RPAV-*`. | Spec reviewed before code (`sdd-workflow.md`); P4 fixed so the test-name gate is not vacuous. Each of the seven corrections appears as a constraint or a named test in `feature_steps.md`, so none of them survives only in the record. |
| **1 Fix + seam** | **P5 first** (`Region.flatten` + repoint `Resolve.visible_elements`/`_object_candidates` at it), then P6, P7, P1–P4. Six `setObjectName` additions for board / toolbar / notation / main splitter. `QtDriver.widget_info()` emits `sub_rects` + `paint_overrides`; `Types.SubRect`; `FakeDriver` fixtures carry both + a synthetic `screenshot`. | `make test` green; **`visible_elements` on the live app returns nested widgets, not one root** — a test asserts a known 4-deep widget is present with a capture-absolute rect; `resolve_all` returns a list where `resolve_one` raises `AmbiguousMatchError`; `rpa_act` reaches all 9 existing activities; `rpa_state` still <200 ms at real depth. |
| **2 Pure core** | `Scene.py` — the five primitives: gradient `Fill`, `Ink`, `Seam`, **`Corner`**, **`Surface`** + `Hypothesis`, plus `SceneNode.measured` and the per-node measurement inventory. `Measure.py` (four bases, `peers`, `seams`, `seam_owner`, `surfaces`, `surface_breaks`), `Report.py` + `diff()`. | ≥90% branch; the 6-tab literal asserts `perceived=[12,13,24,24,25] non_uniform` **and** `widget=[0,0,0,0,0] uniform`; the 5-tab literal asserts `Seam(px=2, shows_owner="ancestor", closed=True)`; the `tab_page` literal asserts 4 breaks with `corner_tl` first; a `measured`-less literal asserts `indeterminate`, never `ok`; `to_ascii()` golden includes a `not measured:` line; nested-widget hit-test through `flatten`. |
| **2b Five detectors only** | `Region.py` (lexicon, `flatten`, `named_regions`, geometric fallback); `Detectors.py` with **`invisible_fill`, `peer_adjacency`, `surface_broken`, `orphan_style_rule`, `spacing_uniformity`** + `run_all` ranking, `caused_by` and `basis_disagreement`. The other eight are deliberately **not** written yet, but each gets its `xfail(strict=True)` named test now. Also: author the **three seed `Resources/Rpa/Design/queries/*.json` files** here — they are declarations of expected output, they are what the detectors are being written against, and Phase 6 only adds the runner that executes them. | `test_region.py`: `"the side panel"` → `#WFritzRightCol`; `"the notation panel"` → the `pgn` `PaneSpec`; unknown phrase returns `None`, never a guess. `test_detectors.py`: one literal case per detector **plus a no-false-positive case each** — `invisible_fill` on flat *and* gradient literals with the mean-rule companion assertion; `peer_adjacency` firing on `shows_owner="ancestor"` and silent on `"parent"`, **paired with the assertion that `spacing_uniformity` reports `uniform` on the same `Scene`**; `orphan_style_rule` firing on `QTabWidget::pane` and silent on `QTabBar::tab`. |
| **2c Style bridge** | Generalise `QssRules.qproperties()` → `parse_rules()`; `StyleSource.py` consuming `paint_overrides` **and the flattened widget-type set**, with three-valued `effective`. Emits `style_ineffective` and `font_mismatch`. | `test_style_source.py` asserts `WRibbon.py:118` governs the File fill; `fritz-widgets.qss:290` and `Fritz.qss:1015` are `matched_overridden`; and **`Caissa.qss:214` `QTabWidget::pane` is `loaded_unmatched`** — the check that the stylesheet-presence test alone would have failed. |
| **2d Stop and re-aim** | Run your next real query by hand against what 2–2c has built (no runner yet — the CLI arrives in 4b, so this is a Python-driven probe like the ones in this document). Author a **fourth** corpus JSON from it. **Only then** decide which of the eight deferred detectors to write. | A fourth `Resources/Rpa/Design/queries/*.json` exists alongside the three seeds authored in 2b, and the decision about which detectors to build next is recorded in `feature_steps.md` with the query as evidence rather than guessed. **This is a decision gate, not a code gate** — it may legitimately conclude "write none of them yet". |
| **3 CV core** | `Segment.py`, `Annotate.py`; `Ocr.py` psm/upscale + `read_words`; `Template.py` scale list; `.coveragerc` omits. | `make test-cv` green with **real assertions** — no `pytest.skip` placeholders. Fixture tests below. |
| **4 Activities** | 6 activities incl. `Locate(phrase=)` and `Inspect`; `rpa_describe`/`rpa_inspect`/`rpa_report` + `QThreadPool`/deque. | `<200 ms` verb timing asserted (N-RPA-4); a UI-responsiveness check that the main thread is not blocked during OCR. |
| **4b Agent surface** | `tools/caissa-eyes` (0755) with the eight subcommands and per-command `needs_live_app`; `ingest` transcript decode; `--format agent` ≤2 KB with the `NEXT:` line; `.claude/skills/design-eyes/SKILL.md`; `.claude/commands/design-eyes.md`; `chmod +x tools/caissa-rpa`. | **The only gate in this plan that tests me rather than the code** — see below. Plus: `ingest` recovers a known pasted PNG byte-identical to its base64 source; with no socket, `ingest`/`inspect --image`/`explain` all succeed and `shot` dies naming the socket; `--format agent` on the full window is ≤2 KB and its last line starts `NEXT:`. |
| **5 Spec collapse** | `ribbon.spec.json` + `panes.spec.json` + `known_deviations`; repoint `ribbon_report.py`, `elements.py`; theme-parameterise `chrome_mask` **and** `row_ink_profile`; fix docs. | Scorecard output byte-identical to pre-migration (steps 1–3 above). |
| **6 Query corpus runner** | `tests/unit/rpa/test_query_corpus.py` — the runner over every JSON authored in 2b and 2d, plus `Workflows/design_verify.py` and its `Service._load_builtin_workflows()` registration. Also re-measure every absolute pixel value through `tests/conftest.py::_bootstrap()` or the live app before it enters a spec or a golden. | **All four+ corpus queries answered end-to-end from the phrase alone, with no code read before the top finding.** `expect_absent` and `expect_verdict` both hold. `design_verify` passes `dry_run`. |
| **7a Diagnose + propose** | Run all four+ corpus queries against the live app and keep the before-reports. Render the proposed [five-change notation-tab fix](#the-notation-fix) and the caption fix with `tools/design/fritz_mock.py`, build the sheet with `tools/design/review.py`, and record your sign-off. **No QSS is edited in 7a.** | `ui-design-process.md` §5: the two-round approval cycle has run and the sign-off is written into `docs/features/rpa-design-vision/design-approval.md`. **This gate blocks 7b** — a visual phase may not begin before it passes. The normative detail behind both rows — §4's `_bootstrap()` reuse, `CAISSA_DESIGN_OUT` instead of a hardcoded `/tmp/`, `webbrowser.open` instead of a shell `open` — is stated once in [*The SDD side*](#sdd-gates). |
| **7b Implement + re-review** | Apply the five-change notation-tab fix using the report, then `design_verify` to confirm; then the pane captions. Add deferred detectors only as new queries demand them. | Real-execution evidence in the PR body: the before report, the fix, the after report showing all four `surface_broken` breaks gone and nothing new. §6's phase-exit `tools/design/review.py --live` against the running app. **The PR must also record that `Caissa.qss:214-218` was left untouched**, since it matches nothing — evidence the bridge stopped pointing at dead rules. |

Two phases carry the risk. **Phase 2 + 2b are the feature** — pure, no Qt, no cv2, no display — and their gate is that the two literal-driven tests reproduce `perceived == [12,13,24,24,25]` for the ribbon and `invisible_fill` firing on the gradient captions while `fill_extent` stays silent. If those do not hold, nothing downstream is worth building. **Phase 7b is the only thing that proves it**, because it is the only phase where a real question of yours gets a real answer and a fix gets verified. Everything between them is plumbing.

**The Phase 4b gate is unusual and is defined in full elsewhere.** Every other gate in the table asserts something about code; 4b asserts something about *my behaviour*, which is the thing correction 7 says is actually at fault. The procedure — a `claude -p` run with your query verbatim, a `jq` extraction of the tool-call order out of the stream, three positive conditions and one negative — is the [fifth real check in *Verification*](#gate-4b). It is stated there rather than here because it produces Gate E real-execution evidence, and duplicating a four-condition procedure across two sections is how the two copies drift.

**Phase 1 is now bigger than it looks**, and that is the honest cost of P5: the object tier has to actually work before any of the six pure modules has real input. It is still small in lines — a recursive `flatten`, six `Rect` methods, one `resolve_all`, six `setObjectName` calls — but it is a genuine dependency, and it is the sort of thing that turns "week two" into "week three" if it is discovered during implementation instead of now.

Branch `feat/rpa-design-vision`, PR to `JohnnyFoulds/caissa` only, `CHANGELOG.md` updated in the same commit as each behaviour change — Phases 0a and 0 are docs-only and correctly carry no changelog entry.

### Test strategy — what is synthetic, what is a fixture, what is committed

The §9 constraint (no reference crops in the repo) plus the ≥90% branch gate force a three-way split, and getting it wrong means either an untestable feature or a copyright problem.

| Layer | Input | Committed? | Marker |
|---|---|---|---|
| every detector, `gaps`, `perceived_gaps`, `uniformity`, `peers`, `seams`, `seam_owner`, `surfaces`, `surface_breaks`, `to_logical`, `flatten`, `owner_of` | **hand-written literals** — the 6-tab ribbon numbers, a 4-caption gradient `Scene`, a 5-tab seam `Scene`, a `tab_page` `Surface` with an 8 px `Corner`, and a deliberately `measured`-incomplete `Scene` | yes, in the test file | `unit` |
| `orphan_style_rule` | a literal selector list + a literal set of widget class names — **no `Scene` at all** | yes, in the test file | `unit` |
| `Scene.to_ascii`, `Report.diff` | literal `Scene` → golden `.txt` | yes, small golden files | `unit` |
| `StyleSource` | literal QSS strings + a literal `paint_overrides` dict, **plus** the real `fritz-widgets.qss` read from the repo | the QSS is already in the repo | `unit` |
| `Segment.*` | **synthetic PNGs drawn by the test** with `cv2.rectangle`/`putText` — known fill boxes, known glyph positions, one inverted-polarity case, and an **anti-aliased rounded rect of known radius** for `corner_of` | yes, generated at test time, nothing stored | `rpa_cv` |
| `Segment` on real chrome | a Caissa-rendered ribbon crop via `fritz_mock` (our own output, not Fritz's) | yes — it is our own pixels, no §9 issue | `rpa_cv` |
| `AssertDesignSpec` vs the Fritz reference | `~/Pictures/fritz-reference/*.png` | **never** — `tools/design/` only, outside `make test` | n/a |

The key move is that **`Segment` tests draw their own inputs.** A synthetic image with a `#007acc` rect at exactly `(4,5,43,21)` tests `fill_regions` more sharply than any screenshot, because the expected answer is known by construction rather than by measurement. The two empirical findings each get a purpose-built adversarial fixture:

- a `#ffffff` fill adjacent to `#ffffff` glyphs — asserts `fill_regions` returns **two** components, which the global-bbox implementation provably fails;
- a light-on-dark region — asserts `glyph_boxes(polarity="auto")` finds the glyphs, with a companion assertion that a fixed threshold of 150 finds **none**, so the regression is pinned to the cause rather than to a symptom.

The Caissa-rendered ribbon crop is the one non-synthetic fixture, and it is legitimate because it is our own render. It is also the only test whose numbers will shift with fonts, so it asserts **relations** (`perceived` spread > 1.5×, two visible fills, six tabs) and never absolute pixels. That distinction — synthetic for absolutes, real render for relations — is what keeps the suite from becoming a font-version tripwire.

### Boundary to respect

`ui-design-process.md` §9: *"The design harness is a development tool, not a test. Its reference crops MUST NOT be committed... it has no role in `make test`."*

So the split is: `Vision/` is library code with real tests; **the oracle-dependent comparison stays in `tools/design/`** and never enters `make test`. Committed visual assertions stay within the six §9 conditions — template-presence and OCR-location only, never full-window pixel equality (N-RPA-7), each paired with an object-tier assertion, `rpa_cv` marked.

`Resources/Rpa/Reference/` needs creating — only `Templates/` exists today, with an empty manifest. The one committed CV fixture (the `fritz_mock`-rendered ribbon crop) goes there with the documented sidecar shape from `vision.md:254-263`; anything reached by a template-tier selector additionally needs a `manifest.json` entry with its DPR, theme, ui_mode and translator, because `Manifest.load_and_verify()` checks path + SHA-256 and `test_every_workflow_template_ref_is_in_manifest` fails the commit otherwise.

---

## Verification

```bash
make lint                     # ruff --config ruff.toml
make test                     # unit + rpa, no Qt
make test-all                 # markers vs filesystem
make cov                      # ≥90% branch
make test-cv                  # CAISSA_RPA_CV=1, real CV assertions
make docs                      # sphinx -W, zero warnings
make test-ui                  # real app, out-of-process
```

Per CLAUDE.md's Real-Execution rule, green tests with fakes are **not** sufficient evidence. The feature closes only on this observed output:

```bash
nohup tools/caissa > /tmp/caissa.log 2>&1 &
tools/caissa-eyes doctor                # expect cv_available: True, ocr_available: True
tools/caissa-eyes inspect --object-name WRibbonTabBar --ocr --verbosity full
```

That must print the real per-tab `sub_rects` from the live `QTabBar`, the `#007acc` fill box, per-tab glyph ink spans, and the gap list on **all four** bases — and the numbers must **explain** the anomaly you see rather than flatly reporting "uniform". Concretely, the pass condition is: the `perceived` column shows a spread of roughly 2× while `widget` shows all zeros, and the `spacing_uniformity` finding reads `non_uniform`. On the crop you gave me the fill box is `Rect(4,5,43,21)` with padding 13/12; the live run must reproduce that for the File tab and produce the sibling-tab figures the crop was too small to contain.

Second real check, for use case (b): feed your pasted crop back in and confirm the chain resolves end to end.

```bash
tools/caissa-eyes ingest          # decode the pasted crop out of the transcript
tools/caissa-eyes locate --fragment $CAISSA_VISION_OUT/query/1.png
```

That must return the rect, `object_name=WRibbonTabBar`, `sub_rect index=1`, and the ranked style sources — including `fritz-widgets.qss:290` **and** `Fritz.qss:1015` marked inert, and `WRibbon.py:118` marked as the source that actually governs the fill. If it reports either QSS file as effective, the bridge has reproduced my own original mistake and the phase does not pass.

**Third real check, and the one I would actually stake the feature on** — your second query, from the sentence alone, against the live app:

```bash
tools/caissa-eyes inspect --phrase "the side panel" --verbosity findings
```

Pass conditions, all four required:

1. The region resolves to `#WFritzRightCol` with `source: "objectname"` — not geometric, not a guess.
2. A `pane_caption` cluster of **exactly 4** members (not 5 — `eval_bar` is registered in `_PANE_SPECS` but never wrapped in a `WFritzPane`, so a cluster of 5 means `peers` is matching on the wrong signature).
3. The top finding is `invisible_fill`, covering 4 nodes, reporting `kind: gradient_v`, `hex_start: #252526`, `hex_end: #363636`, `background_hex: #2d2d2d`, `visible_delta ≤ 9`.
4. **`fill_extent` does not appear.** This is the assertion that my original wrong answer has not been baked into the tool.

Then close the loop, which is the part you asked for explicitly:

```bash
# edit the qproperty values, then:
tools/caissa-eyes verify --baseline <report_id>
```

That must report the `invisible_fill` finding **gone** and no new finding at or above `warn` inside the region. Both halves are required — making the band visible by any means that introduces a new defect is not a pass.

**Fourth real check — query 3, and the one whose capture path is already proven.** I took this screenshot myself during planning with `screenshot /tmp/q3-notation.png` over the live control socket, so the only new part is the analysis:

```bash
tools/caissa-eyes inspect --phrase "the notation panel" --verbosity findings
```

Pass conditions:

1. Five `notation_tab` cluster members, with four `Seam`s reporting `px=2`, `shows_hex=#1e1e1e`, `shows_owner="ancestor"`, `closed=True`.
2. `notation_content` reports `Corner("tl", radius_px=8, shows_hex="#1e1e1e", shows_owner="ancestor")` and the same for `"tr"` — **the measurement I originally omitted entirely.**
3. Top finding `surface_broken` on the `tab_page` surface, listing **four** breaks with the `tl` corner **first**.
4. `orphan_style_rule` fires on `QTabWidget::pane`, and `StyleSource` reports `Caissa.qss:214` as `loaded_unmatched` — **not** `effective`. If it says effective, the bridge has reproduced the mistake for the third time.
5. **`spacing_uniformity` reports `uniform`** — present in the report and explicitly not a finding. If it fires, the wrong-predicate distinction has been lost.
6. Every node's `measured` set contains `corners`. A node missing it fails the check even if no finding is wrong, because that is exactly the state in which this defect was invisible.

The fix is then the five-change set in [*The fix is therefore not the four QSS lines I proposed*](#the-notation-fix) above — **not** the four QSS lines I previously proposed, and correcting that is part of the demonstration. What is specific to this check rather than to the fix itself: **the fix must be applied and re-measured, and the PR must record that `Caissa.qss:214-218` was left untouched.** An after-report showing all four `surface_broken` breaks gone while the dead `::pane` rule is still exactly as it was is the strongest single piece of evidence that the bridge stopped pointing at rules that match nothing.

This is still the best close-the-loop demonstration of the four, because the whole causal chain — bare `QTabBar` + `QTextEdit` sibling → generic 8 px radius → notch under the selected tab → "disconnected components" — is now measured, confirmed in source, and fixable in one file.

<a id="gate-4b"></a>**Fifth real check — the one that tests whether I reach for any of the above.** All four checks so far assume the command already got typed. Correction 7 says that assumption is the weakest link, so it gets its own evidence. **This is also the Phase 4b gate — one procedure, stated once here, referred to from *Phases and gates*.** It is the only gate in the plan that asserts something about my behaviour rather than about code, which is why it is a transcript inspection rather than a pytest:

```bash
# app running; fresh session; the query verbatim, nothing else
claude -p 'The tabs in the notation panel does not look like a tabgroup to me,
           it lools like disconnected components' \
       --output-format stream-json > /tmp/gate4b.jsonl

jq -r 'select(.type=="assistant") | .message.content[]?
       | select(.type=="tool_use") | .name + " " + (.input|tostring)' /tmp/gate4b.jsonl
```

The typo is deliberate: that is your query **verbatim**, and matching on how you actually type is the entire point of a description-based trigger.

Pass conditions:

1. `design-eyes` loads without being named in the prompt.
2. `caissa-eyes shot` (or `ingest`) **and** `caissa-eyes inspect` both appear **before** any `Read` or `Grep` of a `.qss` or `.py` file.
3. The reply leads with the corner break, in your vocabulary, not with a QSS line number.
4. **The negative case**, run the same way: `claude -p 'Why does the engine crash when I start a new game?' ...` — the skill must **not** load. If it fires on that, its description is too broad and it will burn a capture on every UI-adjacent question until I learn to ignore its output.

Condition 2 is the substantive one. If I `Grep` first and `inspect` second, the tool is decoration: I will have formed the hypothesis from the stylesheet and used the measurement to confirm it, which is the exact order that produced three edits to a dead rule. Both the positive and negative transcript excerpts go in the PR body; neither is automatable inside `make test`, so they are Phase 4b evidence rather than a test.

Together these five are the only evidence in the plan that the whole recognise → see → understand → read code → fix → re-measure loop actually closes, and they are what Phases 4b and 7 exist to produce.

### Risks, and what would make me stop

Stating these as kill criteria rather than caveats, because three of them would mean the feature is not worth its maintenance cost:

| Risk | Signal | Response |
|---|---|---|
| **I state a confident wrong mechanism and act on it** — the failure that already happened once, on the pane captions | a fix produces a no-op diff: the code changed, the report did not | this is what `hypotheses` / `confirmed_by` / `ruled_out_by` exist for, and why `confirmed_by: (pending)` must render. **The mitigation is structural, not diligence** — I was diligent and still got it wrong, because two mechanisms were pixel-identical. If a finding's mechanism turns out wrong again *despite* being labelled a hypothesis, that is acceptable; if it turns out wrong while labelled a cause, the reporting rule has been violated and that is a defect in the feature. |
| **`perceived` is a heuristic I invented** and it disagrees with your eye on the *next* widget | you report unevenness that `perceived` calls uniform | the basis is wrong, not the widget. Re-derive it from that case before adding features. **This is the one I most expect to happen.** |
| **`Scene` needs yet another primitive** — four queries, five primitives, and the last two arrived from *re-reading a capture I had already analysed* | your next query cannot be expressed with `Fill` / `Ink` / `Seam` / `Corner` / `Surface` | **this has now happened four times, so it is a certainty, not a risk.** It is why Phase 2d exists: stop after the primitives and five evidenced detectors, run a real query, and extend from evidence. The cost is bounded because primitives are frozen dataclasses in the pure tier — adding one is a field, a `Segment` function and a test. The thing that would kill the feature is *not noticing* and shipping all thirteen detectors over a model that cannot express the next defect. |
| **An unmeasured property reads as a passing one** — the defect that hid the corners | a report is confidently silent about something you can see | `SceneNode.measured` plus the `not measured:` line in `to_ascii()`, and the rule that a detector may only conclude about a property in `measured`. This is the highest-value mitigation added since the first draft, because it is the only one that makes *my own blind spots* visible in the output rather than absent from it. If a future correction turns out to be another omission rather than a wrong answer, the inventory was incomplete and the fix is to widen it, not to add a detector. |
| **The style bridge names a rule that matches nothing** | I edit QSS and the screenshot does not change | already happened, on `QTabWidget::pane`. Three-valued `effective` with `loaded_unmatched` is the fix, and `orphan_style_rule` promotes it to a finding. Note the original single-valued check *passed* this rule — so the mitigation is a new predicate, not more care. |
| **A detector's predicate is right but irrelevant** — the query-3 failure | `spacing_uniformity` reports `uniform` and passes a scene you say is broken | the sharpest failure mode, because nothing errors and coverage is green. `expect_verdict` in the corpus is the mitigation: it pins the known false negative in a test. If a *second* detector turns out to have the wrong predicate rather than a missing case, the model is being designed from too few examples and Phase 2d should extend until the corpus has five entries. |
| **The speculative detectors are dead weight** — 3 of 8 have never fired on any query, and a 4th fired wrongly | Phase 7 arrives and they still have not | already acted on: they are deferred out of Phase 2b entirely. If they never fire, they are never written, which is the correct outcome and costs nothing. |
| Font/theme drift makes the numbers unreproducible between your machine and CI | `rpa_cv` fixture tests fail on font updates | already mitigated (relations, not absolutes) — but if the *relations* drift, the feature reports noise and should be cut back to `findings` verbosity only |
| `paint_overrides` pushes `snapshot()` over 200 ms | Phase 1 timing gate fails | move it behind `snapshot(depth=…)` opt-in; the feature survives, `DescribeScene` just requests it explicitly |
| The worker thread destabilises the live app | crashes or hangs during OCR under `--live` | `with_ocr=False` default already makes OCR opt-in; worst case the feature ships geometry-only and loses labels, which the `node_id` design was built to survive |
| **Nobody uses it, including me** | I answer a visual complaint by grepping the QSS, or ask you to describe the UI in words, instead of running `inspect` | **the real kill criterion, and correction 7 is evidence it was already happening.** Mitigations, in order of strength: the skill description matched against your actual phrasings; the `NEXT:` line; `findings` as the default verbosity; and the Phase 4b gate that measures the tool-call *order* in a real transcript. If the 4b gate fails twice, the trigger is not the problem — the loop is too long, and it should collapse to a single `caissa-eyes inspect` that prints everything including `explain` output |
| **The skill fires too often** | it loads on behaviour questions, icon questions, or any sentence containing "button" | the negative half of the 4b gate. Cost is a wasted capture and 2 KB per false fire, and the real damage is that I learn to skim its output. Response is to narrow the description toward the *complaint* verbs ("does not look right", "uneven", "disconnected") and away from the *noun* list |
| **The transcript format changes and `ingest` breaks** | `ingest` finds no image block in a session where you plainly pasted one | it is an undocumented internal format and this is a when, not an if. Mitigation is that `ingest` skips unparseable lines rather than dying, and that `--image PATH` is a first-class alternative on every command — so the fallback is you saving the screenshot yourself, which costs one step and loses nothing |

The honest summary of the risk profile: **the geometry is solid and empirically verified; the `perceived` basis is a well-motivated invention with exactly one confirming data point.** The plan is structured so that the invention is isolated in one pure function (`perceived_gaps`) with one literal-driven test, so revising it costs a function rather than a rewrite. That isolation is deliberate and it is the main thing protecting this from the failure mode of my first draft.

### What is verified, and what is not

Verified on your crop, by hand, locally: the `#007acc` File fill box `Rect(4,5,43,21)`; the four `F-i-l-e` glyph components and the 13/12 px padding that matches `padding: 4px 13px` at `fritz-widgets.qss:282`; the `#ffffff` Home fill box `Rect(48,6,52,20)` and its `#9daab8` border; the **1 px seam** between the two; that default PSM 3 finds nothing; that a global colour bbox is contaminated and CC labelling fixes it. Verified on the 6-tab probe: that only two of six tabs are painted, and that `perceived` separations are 12/13/24/24/25 while `widget` gaps are all 0.

**Measured with the wrong fonts, and Phase 6 must re-measure:** every absolute pixel value from the 6-tab probe. That probe bypassed `tests/conftest.py::_bootstrap()` and emitted `missing font family "Sans Serif"`. The 2× relative spread is font-independent and will hold; the individual numbers will move, so **none of them may be committed to `ribbon.spec.json` or to a golden file until re-measured through the live app.**

**Not verified at all, and Phase 6 must settle it:** whether `_FG_NORMAL = #1e1e1e` on the dark theme's `palette().window()` is a genuine contrast bug for *unselected* tabs. The plan carries this as `severity: info` / `UNVERIFIED`, and the honest outcome may be that it is an unrelated defect — or nothing.

**Verified from source, and the correction that matters most:** `_PaneTitleBar.paintEvent` (`WFritzPane.py:257-272`) fills `self.rect()` — the captions are full-width. My pixel-only diagnosis said their fill was text-width. The symptom was right, the mechanism was wrong, and no measurement of that screenshot could have told the two apart.

**Verified from source on query 3, where the process worked:** `Caissa.qss:226` `margin-right: 2px` is the gap; `:224`'s four-sided `border` is the closed box; `:235`'s `border-bottom: 2px solid #228df2` keeps the selected tab's bottom *closed* instead of opening it into the pane; `:233` declares the selected background identical to `:222`. Every pixel measurement maps onto one declaration. That mechanism held because I checked the source before asserting it — the discipline added after correction 4 changed the outcome on the very next query.

**Verified from the live widget tree, and the correction that reframes query 3 entirely:** `dump_ui 12` shows **no `QTabWidget` anywhere in the application.** The notation tab group is `modern_fritz_ui.py:168-188` — a bare `QTabBar` (`:175`, `setDrawBase(False)` at `:178`) and a sibling `_FlowingNotation`, which `:109` declares as a `QTextEdit`. Every pixel boundary I measured maps onto a widget edge in that tree (right splitter `x=716`; container `y=485`; content `y=516..859`). The 8 px corner radius is the generic `QTextEdit` rule at `Caissa.qss:165-173`. `QTabWidget::pane` at `Caissa.qss:214-218` — and in seven other theme files — **matches nothing at all.**

**Measured only after you pointed at it:** the content surface's corner radii. `Corner("tl", radius_px=8, shows_hex="#1e1e1e", shows_owner="ancestor")`, and the same at `"tr"`. The notch spans `x=716..723, y=516..523`, filled with the window background, directly beneath the selected first tab at `x=717..796`.

I corrected myself seven times, and every correction is baked into the design above rather than smoothed over:

1. The OCR-first architecture I first proposed was **inverted** — geometry from colour is deterministic, OCR is not.
2. My "Home is low-contrast dark-on-dark" diagnosis was wrong; it is the *selected* tab, and an inverted-polarity segmentation failure.
3. My three-basis model would have told you the ribbon spacing was uniform — agreeing with the naive measurement and contradicting your eye. That is why `perceived` exists.
4. My pane-caption mechanism was wrong, and the wrong fix it implied (`setSizePolicy` on a widget that already spans its pane) would have been a no-op I could have spent an hour on. That is why `hypotheses` / `confirmed_by` / `ruled_out_by` exist.
5. **My flagship detector passes query 3.** `spacing_uniformity` measures gaps of 2, 2, 2, 2 and reports `uniform` — correctly, and uselessly. Uniformity cannot express "should be zero". That is why `Seam` exists, why `peer_adjacency` is separate from `spacing_uniformity`, and why eight speculative detectors are now deferred.
6. **I never measured corners, so no detector could have fired on the actual main problem.** You had to tell me. And the structural fact behind it — that there is no `QTabWidget`, so the one QSS rule whose job is to merge a tab bar into its content matches nothing — would have been reported by my bridge as `effective: true`, sending me to edit dead code for the third time. That is why `Corner`, `Surface`, `SceneNode.measured`, three-valued `effective` and `orphan_style_rule` exist.
7. **I designed the library and never designed the moment of reaching for it.** The whole invocation layer was one row in a file list, so given your query my default behaviour is still to grep the stylesheet — the behaviour that produced corrections 4, 5 and 6. And a pasted screenshot has **no path on disk**: it is inline base64 in the session transcript, so use case (b) as you stated it had no route into cv2 at all. That is why `.claude/skills/design-eyes/SKILL.md`, `tools/caissa-eyes`, `ingest`, the `NEXT:` line and Phase 4b exist.

Corrections 3 through 6 shaped the architecture, and they say the same thing from four directions: **a measurement layer's job is to be honest about what it does and does not know.** Do not report uniform when you have measured one basis. Do not report a cause when you have measured a symptom. Do not assume the predicate you built for the last query is the right question for the next one. **And do not let a property you never measured render as a property that passed.** All four would have produced confident, well-formatted, wrong answers — which for a tool whose only output is text I am going to act on is the sole failure mode that actually matters.

Correction 7 is different in kind from all of them, and it is the one that would have wasted the most work: corrections 1–6 are about being wrong, 7 is about **never being asked**. A measurement layer that is never invoked has a defect rate identical to no measurement layer at all, so every page above it is contingent on one `SKILL.md` and one `ingest` command working. That is an uncomfortable amount of weight on the two smallest files in the plan, and it is why Phase 4b's gate reads a real transcript rather than asserting anything about code.

Correction 6 is the worst of the *measurement* corrections and worth naming as such. The others were wrong answers; this one was an **absent** answer that looked complete. My query-3 write-up was internally consistent, pixel-accurate, source-confirmed — and silent about the thing you identified as the main problem, because nothing in my pipeline measured it. A wrong answer invites argument. A confidently incomplete one does not, which is why `measured` is now a required field and why `describe` enumerates a fixed inventory per node rather than reporting whatever it happened to find.

The uncomfortable summary is that **each of your queries broke the design I had just finished defending** — the basis set, then the data model plus my own reasoning, then the flagship detector's predicate, then the measurement inventory itself twice over on a capture I had already analysed, and finally the invocation layer, which was not a question about pixels at all. I do not think the next one will fit either. What I have changed in response is not to add more detectors but to invert the build order: five primitives, five evidenced detectors, then **stop at Phase 2d** and ask you for another query before writing anything else.

If only two parts of this were approved, they would be: **`invisible_fill`**, because it fires on all three queries via three unrelated paint paths and is the one piece of genuine convergent evidence in the document; and **the skill plus `ingest`**, because without them the other part never runs.

So the distinction between *measured* and *inferred* has to survive into the JSON. That is why `SceneNode.sources` and `label_confidence` exist, why `None` and `indeterminate` are first-class, why `Finding.hypotheses` is separate from `Finding.measurements`, and why findings carry a severity instead of all reading as facts. And it is why the acceptance criterion is a corpus of your real queries rather than a coverage number: coverage would have been green for both of my wrong answers.
