**Status:** Finalised against `Resources/Ribbons/modern-fritz.json` (Phase 7)  
**Implements:** `bin/Code/Fritz/RibbonModel.py`, `bin/Code/Fritz/WRibbon.py`, `bin/Code/Fritz/Ribbon.py`  
**Audience:** contributors adding a new ribbon or extending the Fritz mode  
**See also:** `docs/fritz/concepts.md`, `docs/features/fritz-polish/feature_spec.md §2.2`

---

# Fritz Ribbon

The ribbon is an Office-style tab bar hosted inside `WBase.tb` as a single `QWidgetAction`.
It replaces the flat button row in Fritz modes while leaving the `QToolBar` API intact for all
other callers (`pon_toolbar`, `get_toolbar`, `closeEvent`, etc.).

---

## Schema (`Resources/Ribbons/<name>.json`)

```jsonc
{
  "$schema_version": 1,          // must be exactly 1
  "default_tab": "home",          // tab id shown on startup
  "missing_key_policy": "disable",// "disable" = grey out absent keys; only policy supported
  "quick_access": ["TB_CLOSE", …], // always-visible icon strip in the tab bar header row
  "overflow": { "tab": "home", "group": "more", "label": "More" },
  "tabs": [
    {
      "id": "home",               // unique within the file
      "label": "Home",            // display text
      "groups": [
        {
          "id": "home.game",      // unique within the file
          "label": "Game",        // caption shown *below* the controls
          "kind": "slots",        // "slots" (default) or "panes"
          "slots": [
            { "key": "caissa:fritz_level", "size": "large", "label": "New Game" },
            { "key": "TB_RESIGN",          "size": "small" }
          ]
        },
        {
          "id": "home.panes",
          "label": "Panes",
          "kind": "panes",        // renders QCheckBox widgets, not slots
          "panes": [
            { "pane": "player_header", "label": "Players" }
          ]
        }
      ]
    }
  ]
}
```

### Key types

| Pattern | Meaning |
|---|---|
| `"TB_RESIGN"` (string) | Resolved via `getattr(Constantes, key)` at ribbon-install time |
| Integer | Used directly as a `Constantes.TB_*` value (less common) |
| `"caissa:<name>"` | A caissa-namespaced action registered through `Actions` plugins |

### Slot sizes

| `size` | Button dimensions | Style |
|---|---|---|
| `"large"` | 56×56 px | Icon + text below |
| `"small"` | auto × 20 px | Icon + text beside |

### Panes groups (`kind: "panes"`)

Renders a vertical stack of `QCheckBox` widgets wired to `pane_api["set"](pane_key, checked)`.
The mode hook exposes `pane_api` via a `pane_api(mw)` function; absent → group renders disabled.

---

## How a mode gets a ribbon

Add `"ribbon": "<name>"` to the mode JSON:

```json
{ "name": "Modern Fritz", "ribbon": "modern-fritz", … }
```

`WBase.__init__` reads the active mode's `"ribbon"` key and calls `Ribbon.install()`.
Modes without a `"ribbon"` key get the plain toolbar unchanged.

---

## Overflow

A key in `li_acciones` not covered by any slot or QAT entry goes to the overflow group.
`RibbonModel.overflow(spec, li_acciones)` returns the list; it should be empty in normal
operation (verified by T-RMAP-05 and T-RIB-05).

---

## Group assignments — inferred vs documented

The group assignments below are **inferred** from Fritz 18 screenshots (the ChessBase documentation
pages for `ribbon.htm`, `home.htm`, `menu.htm` and `mainwindow.htm` all return 404; only
`anaboard.htm` resolves).  Where assignment is a judgement call it is flagged **(inferred)**.

| Key | Tab | Group | Notes |
|---|---|---|---|
| `caissa:fritz_level` | Home | Game | **(inferred)** — no direct Fritz equivalent |
| `TB_RESIGN` | Home | Game | Documented |
| `TB_DRAW` | Home | Game | Documented |
| `TB_REINIT` | Home | Game | **(inferred)** |
| `TB_RESIGN`, `TB_TAKEBACK` | Home | Game | Documented |
| `TB_PAUSE`, `TB_CONTINUE` | Home | Game | **(inferred)** |
| Pane checkboxes | Home | Panes | Documented (Fritz "Panes" group) |
| `TB_OPEN`, `TB_SAVE*`, `TB_READ_PGN`, `TB_PASTE_PGN` | File | PGN | Documented |
| `TB_VARIATIONS`, `TB_TOOLS`, `TB_CONFIG` | Board | View | **(inferred)** |
| `TB_ADVICE`, `TB_HELP` | Training | Coach | **(inferred)** |
| `TB_UTILITIES` | Analysis | Engine | **(inferred)** |
| `TB_REPLAY`, `TB_PGN_REPLAY` | Opening | Replay | **(inferred)** |
| `TB_SETTINGS`, `TB_ENGINES` | Engine | Settings | **(inferred)** |

---

## Adding a new tab or group

1. Edit `Resources/Ribbons/modern-fritz.json` — add the tab/group/slots.
2. Run `make test` — T-RMAP-01..08 validate schema, uniqueness, key resolution and coverage.
3. If the new key is in `modern-fritz.json`'s `toolbar` allowlist it must appear in a slot or
   QAT or T-RMAP-05 fails.

---

## Measured reference (Fritz 18 — `ribbon_home.png` / Board tab)

Measured from `~/Pictures/fritz-reference/ribbon_home.png` (820×242) by pixel analysis.
This file is the Board tab of Fritz 18 (the filename is a misnomer). The file lives outside
the repo — ChessBase copyright, GPL-3.0 repo — see `docs/standards/ui-design-process.md` §3.

### Band geometry — total ribbon height 143 px

| Band | y range | Height |
|---|---|---|
| QAT row | 5..33 | 29 |
| Tab row | 34..54 | 21 |
| Rule under tabs | 55 | 1 |
| Content | 56..146 | 91 |
| Bottom border | 147 | 1 |

Content breakdown: 4 px top pad → large buttons y=60..125 (66 px) → 6 px gap → caption text
y=132..139 (8 px) → 7 px bottom pad.

The QAT is its own row **above** the tab row — not side-by-side with the tabs.

### Palette

| Role | Hex |
|---|---|
| Chrome background (all bands) | `#efeff2` |
| Separators, rules, borders | `#cccedb` |
| Accent | `#007acc` |
| Body / caption / tab / button text | `#1e1e1e` |
| Selected-tab text | `#005b99` |
| Disabled text + checkbox border | `#a2a4a5` |
| Checkbox indicator fill | `#ffffff` |

The entire ribbon is one uniform `#efeff2` — no banding, no tint variation between bands.

### Tab strip

- 10 tabs: File, Home, Insert, Board, Training, Analysis, Opening, Engine, View, Help.
- **File tab**: solid `#007acc` fill, white text — always blue.
- Unselected tabs: transparent on `#efeff2`, `#1e1e1e` text, ~13 px horizontal padding, 8 pt.
- **Selected tab** (Board, w=58 px): fill `#efeff2` (same as background), 1 px `#cccedb` border
  on top/left/right only, no bottom border — the "tab opens into content" look. Text `#005b99`.
  The tab-row rule is `#cccedb` across the full width *except* below the selected tab.

### Content groups

Vertical `#cccedb` group separators span ~86/91 px of the content height
(`margin: 2px 4px`, not `6px 4px`). **No group box outlines — groups are delimited by hairline
separators only.**

### Large-button anatomy (measured on "Square", w=36 px)

| Part | Extent |
|---|---|
| Icon | 32×32, y=63..94 |
| Gap | 5 px |
| Text (1-2 lines, 8 pt) | y=100..109 |
| Gap | 6 px |
| Dropdown chevron (where applicable) | y=115..117, 5×3 px centred |
| Total height | ~66 px |

Active/toggled large button ("Flip Board") is filled solid `#007acc`.

### Checkbox

Indicator: 11×11 px, 1 px `#a2a4a5` border, `#ffffff` fill, `#1e1e1e` check mark.
Labels: left-aligned vertical column, `#1e1e1e` text, disabled variant `#a2a4a5`.

---

## Fritz Home tab — group inventory (from manual)

Source: Fritz 18 manual pages 31, 34–35, 63, 73.  The Board tab (p.31) is the most photographed
ribbon; the Home tab content was inferred from manual text and the reference screenshot.

### Fritz Home tab groups

| Group | Buttons | Notes |
|---|---|---|
| **New Game** | New Game ▼ (dropdown) | Opens a level/opponent selection panel (see Dropdown pattern below) |
| **Level** | Levels ▼ (dropdown) | Opens a time-control selection panel (Blitz, Rapid, Classical, Custom…) |
| **Game** | Resign, Offer Draw, Abort | Flat icon buttons. **NOT radio buttons** — confirmed manual p.63 |
| **Game** | Takeback | Small flat button |
| **Coaching** | Hint, Suggestion | Plain action buttons in the Help tab (manual p.63). **NOT radio buttons, NOT toggles** |
| **Panes** | Players, Engine analysis, Eval profile, Notation, Eval bar | QCheckBox column; checked = pane visible |

### Dropdown panel visual pattern (manual p.34–35)

When a button with a ▼ chevron is clicked, a floating panel opens **directly below the button**:

- **No arrow/caret** connecting button to panel
- **Blue header bar** (same blue as File tab, `#005b99` / `#007acc`) with white label text
- **White background** panel body with a thin `#b0b0b8` border
- **Vertical list of items**, plain text, 8 pt, ~20 px row height
- **Highlighted row** on hover: solid blue tint fill, e.g. `#cce4ff`
- **Drop shadow** visible on right/bottom edges
- Panel dismisses on selection or outside click

Example: "Levels" dropdown shows time-control options (Blitz 5min, Rapid 15min, etc.)

---

## Caissa Home tab — design choices (D12, D13)

These are our specific design decisions for the Caissa Fritz Home tab, recorded so future changes
have context. See also `docs/fritz/decisions.md` D12 and D13.

### Group layout

| Group caption | Contents | Rationale |
|---|---|---|
| **Play** | New Game ▼ (large), Levels ▼ (large) | Category name "Play" covers both launch actions; matches Fritz naming pattern of grouping by category not action |
| **Game** | Resign, Offer Draw, Abort, Takeback (2×2 small grid) | Four mid-game controls logically belong together |
| **Coaching** | Hint (small), Suggestion (small) | Plain action buttons — confirmed NOT radio buttons (manual p.63); `?` / lightbulb icon |
| **Panes** | Players ✓, Engine analysis ✓, Eval profile ✓, Notation ✓, Eval bar ☐ | Matches Fritz Panes group; last pane defaults unchecked |

### Caption styling

- **No separator line** above caption row — Fritz reference shows none
- **Caption text `#444444`** — dark, not grey (`#888888` was too light)
- Caption is centred over its group's full width

### Buttons

- Large buttons (New Game, Levels): icon + text + `▼` dropdown chevron at bottom
- Small buttons: icon left, text right, flat — no border at rest
- Resign = flag icon (red), Offer Draw = half-circle (green), Abort = king (dark), Takeback = back-arrow (dark)
- Hint / Suggestion: `?` icon (not a circle/radio indicator)
