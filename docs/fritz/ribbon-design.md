**Status:** Design approved (raster mockup phase)  
**References:** `docs/fritz/ribbon.md` (Fritz inventory), `docs/fritz/decisions.md` D12–D13  
**Implements:** `Resources/Ribbons/modern-fritz.json` (to be updated per this spec)  
**See also:** `tools/design/fritz_compare.py` (raster mockup), `tools/design/fritz_mock.py` (PySide6 harness)

---

# Caissa Fritz Ribbon — Full Design

This document is the authoritative specification for every tab, group, button, and icon
in the Caissa Fritz ribbon. It is the reference used during implementation.

Scope: Fritz mode only. Classical mode is unaffected. Where a Fritz feature has no
Lucas Chess equivalent, it is omitted rather than approximated.

---

## Design principles

Caissa Fritz mode is a focused chess-playing experience. It is **not** a full Fritz clone,
and it is also **not** a superset of Classic Lucas Chess mode.

Fritz mode deliberately narrows the feature set in both directions:
- Fritz features without a Caissa implementation (ChessBase Live, opening book browser,
  game database browser, media player, LiveBook, online play) are **omitted entirely**.
- Classic Lucas Chess features that do not fit the Fritz experience (Training puzzles,
  Competition ladder, Resistance mode, Tactics trainer, Leagues, Databases) are also
  **not exposed in Fritz mode**. They remain available in Classic mode.

**Rule:** When in doubt, omit. A clean ribbon with four tabs is better than ten tabs where six are always grey.

Specific authoring rules:

1. **Category names for group captions** — "Play", "Game", not "New Game", "Controls"
2. **No 1:1 Fritz copy** — include only what is relevant to playing chess in Caissa
3. **Plain action buttons for one-shot commands** — never radio buttons (D13)
4. **Dropdowns (▼) for selection panels** — blue-header floating panel pattern (`https://help.chessbase.com/Fritz/18/Eng/000058.htm`)
5. **Checkboxes for pane visibility** — column layout, checked = pane visible
6. **Large buttons (56×56) for primary actions** — icon + text + optional ▼ chevron
7. **Small buttons (auto×20) for secondary actions** — icon left, text right, flat

---

## Tab strip

Order: **File** · Home · Board · Analysis · Engine · View

Omitted from Fritz original:
- **Insert** — diagram/annotation database tool, not relevant in play mode
- **Training** — Fritz training system; Lucas Chess has its own training modes
- **Opening** — ChessBase-specific opening book management
- **Help** — single Help button in QAT is sufficient

---

## Classic Lucas Chess features NOT in Fritz mode

These are available in Classic mode; switching to Classic to use them is by design.

| Classic feature | Included in Fritz mode? |
|---|---|
| Training / puzzles / tactics trainer | ❌ No |
| Resistance mode | ❌ No |
| Competition / leagues | ❌ No |
| Databases / game browser | ❌ No |
| Washing / position practice | ❌ No |
| Mate map | ❌ No |
| EBoard (DGT) | ❌ No |
| Adjournments | ❌ No |
| Play / Compete / Train mode buttons | ❌ No |

---

## Quick Access Toolbar (QAT)

Always-visible strip in the tab-bar row, right of the tab labels.
These are the critical exit/escape controls that must be reachable from any tab.

| Button | Icon | Key | Notes |
|---|---|---|---|
| Home / Close | ☰ | `TB_CLOSE` | Return to home screen / main menu |
| Cancel | ✕ | `TB_CANCEL` | Abort current activity |
| End replay | ⬛ | `TB_END_REPLAY` | End game replay, return home |
| Play Now | ⚡ | `TB_STOP` | Force engine to move (urgent action) |
| Stop Tutor | 🛑 | `TB_TUTOR_STOP` | Abort tutor analysis |
| ← | ← | `TB_PREVIOUS` | Previous move (replay / analysis) |
| → | → | `TB_NEXT` | Next move (replay / analysis) |

*`TB_FLIP` does not exist in Constantes — flip board is in the Board tab, not QAT.*

---

## File tab

Solid `#005b99` blue fill, white text — always blue, never selected-state styling.
Opens a vertical dropdown panel (same floating panel pattern as group dropdowns).

| Item | Icon | Notes |
|---|---|---|
| New | pencil | → sub-panel: New Game, New Position |
| Open | folder | Open PGN |
| Save | floppy | Save current game |
| Save As | floppy+ | Save with name |
| Print | printer | Print scoresheet |
| Options | gear | Opens Configuration dialog |
| Close | × | Close game / exit |

---

## Home tab *(default tab)*

Already fully specified in `docs/fritz/ribbon.md` § "Caissa Home tab — design choices".
Summary for completeness:

### Groups

| Group caption | Kind | Contents |
|---|---|---|
| **Play** | slots | New Game ▼ (large), Levels ▼ (large) |
| **Game** | slots | Resign (small), Offer Draw (small), Abort (small), Takeback (small) — 2×2 grid |
| **Coaching** | slots | Hint (small), Suggestion (small) |
| **Panes** | panes | Players ✓, Engine analysis ✓, Eval profile ✓, Notation ✓, Eval bar ☐ |

### Dropdown contents

**New Game ▼ panel** (blue header "New Game"):
- Play vs computer
- Play vs human (local)
- Set up position

**Levels ▼ panel** (blue header "Levels"):
- Blitz (5 min)
- Rapid (15 min)
- Classical (90 min)
- Custom…

### Icons

| Button | Icon | Color |
|---|---|---|
| New Game | pawn silhouette | `#005a9e` blue |
| Levels | bar-chart (4 bars) | `#444444` dark |
| Resign | flag | `#b33a00` red |
| Offer Draw | half-circle | `#2a7a2a` green |
| Abort | king | `#444444` dark |
| Takeback | back-arrow | `#444444` dark |
| Hint | `?` glyph | `#005a9e` blue |
| Suggestion | `?` glyph (magnifier variant) | `#005a9e` blue |

---

## Board tab

Controls board appearance. No mid-game action buttons here — pure visual settings.

### Groups

| Group caption | Kind | Contents |
|---|---|---|
| **Board** | slots | Flip Board (large, toggle), Coordinates ✓, Always Queen ✓ |
| **Pieces** | slots | Piece style ▼ (large), Square color ▼ (large) |
| **Display** | slots | Show eval bar ✓, Show arrow ✓, Replay slider ✓ |

### Details

**Flip Board** large button: toggle — filled `#007acc` when board is flipped (matches Fritz).

**Piece style ▼ panel** (blue header "Pieces"):
- Classic (default)
- Smooth
- Habsburg
- USCF

**Square color ▼ panel** (blue header "Squares"):
- Green/Cream (default)
- Brown/Tan (Wood)
- Blue/White
- Custom…

**Coordinates** checkbox — show/hide rank/file labels.  
**Always Queen** checkbox — skip promotion dialog, always promote to queen.  
**Show eval bar** checkbox — the side-of-board evaluation bar.  
**Show arrow** checkbox — highlight opponent's last move with arrow.  
**Replay slider** checkbox — show slider + buttons below board for game navigation.

### Icons

| Button | Icon |
|---|---|
| Flip Board | vertical double-arrow ↕ |
| Piece style | chess knight silhouette |
| Square color | chessboard 2×2 grid |

---

## Analysis tab

Controls the engine analysis pane and analysis functions.

### Groups

| Group caption | Kind | Contents |
|---|---|---|
| **Engine** | slots | Analyse (large, toggle), Stop (large) |
| **Depth** | slots | Depth ▼ (small), Lines ▼ (small) |
| **Output** | slots | Copy to notation (small), Clear (small) |

### Details

**Analyse** large button: starts/stops continuous analysis. Toggle state — filled blue when active.  
**Stop** large button: forces the engine to play/stop immediately.

**Depth ▼ panel** (blue header "Depth"):
- 5 ply (fast)
- 10 ply
- 20 ply
- Infinite (until stopped)

**Lines ▼ panel** (blue header "Lines"):
- 1 line (default)
- 2 lines
- 3 lines
- 4 lines

**Copy to notation** — inserts the current engine variation into the game notation.  
**Clear** — clears the analysis output pane.

### Icons

| Button | Icon | Color |
|---|---|---|
| Analyse | magnifier + circuit | `#005a9e` blue |
| Stop | filled square ■ | `#b33a00` red |
| Depth | layers / depth gauge | `#444444` |
| Lines | multiple arrows | `#444444` |
| Copy to notation | clipboard | `#444444` |
| Clear | eraser | `#444444` |

---

## Engine tab

Engine selection and configuration.

### Groups

| Group caption | Kind | Contents |
|---|---|---|
| **Engine** | slots | Select Engine ▼ (large) |
| **Settings** | slots | Engine Properties (small), UCI Options (small) |
| **Kibitzer** | slots | Add Kibitzer (small), Remove Kibitzer (small) |

### Details

**Select Engine ▼** large button + dropdown panel (blue header "Engine"):
- Lists all installed engines by name
- Currently active engine shown with checkmark
- Clicking an engine switches it immediately

**Engine Properties** — opens the engine's native parameter dialog.  
**UCI Options** — opens the Caissa UCI options panel for hash size, threads, etc.

**Add Kibitzer** — adds a second engine window running in parallel (analysis helper).  
**Remove Kibitzer** — removes the kibitzer engine.

Omitted from Fritz original: Contribute Engine, Lists of Honour, Open Positions — these are ChessBase online features.

### Icons

| Button | Icon |
|---|---|
| Select Engine | robot/circuit head |
| Engine Properties | gear |
| UCI Options | sliders |
| Add Kibitzer | `+` + robot |
| Remove Kibitzer | `−` + robot |

---

## View tab

Window layout and pane management.

### Groups

| Group caption | Kind | Contents |
|---|---|---|
| **Layout** | slots | Standard Layouts ▼ (large), Full Screen (large) |
| **Arrange** | slots | Top 2 Vertical (small), Top 2 Horizontal (small), Maximize All (small) |
| **Panes** | panes | Notation ✓, Clocks ✓, Engine analysis ✓, Eval profile ☐, Extra book ☐, Chatter ☐, Status bar ✓ |

### Details

**Standard Layouts ▼ panel** (blue header "Standard Layouts"):
- Standard (default) — board + notation + engine
- Big Board — maximises board, minimises other panes
- Big Notation — maximised notation for game replay
- Big Engine — engine analysis maximised
- Board Only — board alone
- All Windows — all panes open

Matches Fritz standard layouts (`https://help.chessbase.com/Fritz/18/Eng/000078.htm`) but strips the ChessBase-specific ones.

**Full Screen** large button — Ctrl+Alt+F equivalent. Active state: filled blue.

**Top 2 Vertical / Horizontal / Maximize All** — window arrangement shortcuts.

**Panes** group checkboxes — same semantics as Fritz View → Panes (`https://help.chessbase.com/Fritz/18/Eng/000104.htm`):
- Notation: game notation + variations + commentary
- Clocks: chess clock window
- Engine analysis: main engine output window
- Eval profile: graphical eval history
- Extra book: separate openings book tree pane
- Chatter: engine written commentary
- Status bar: info line at bottom of screen

### Icons

| Button | Icon |
|---|---|
| Standard Layouts | layout grid |
| Full Screen | expand arrows ⤢ |
| Top 2 Vertical | two vertical rectangles |
| Top 2 Horizontal | two horizontal rectangles |
| Maximize All | 4-way expand |

---

## Visual spec (shared across all tabs)

These values apply to all tabs and groups. Full geometry + palette in `docs/fritz/ribbon.md`
§ "Measured reference".

| Property | Value |
|---|---|
| Chrome background | `#efeff2` |
| Separators / borders | `#cccedb` |
| File tab fill | `#005b99` |
| Selected tab accent line | `#0060b0` |
| Group caption text | `#444444` |
| Button / tab text | `#1e1e1e` |
| Active/toggled large button fill | `#007acc` |
| Dropdown header fill | `#005b99` |
| Dropdown hover row | `#cce4ff` |
| Tab row height | 21 px |
| Content area height | 91 px |
| Caption row height | 20 px |
| Large button size | 56×66 px (icon 32×32 + text + chevron) |
| Small button height | 20 px |
| Group separator | 1 px `#cccedb` hairline, no box outline |
| No separator line above captions | confirmed from reference |

---

## Fritz features explicitly excluded

| Fritz feature | Reason excluded |
|---|---|
| Insert tab (diagrams, text, variations) | Database/annotation tool — irrelevant to play mode |
| Training tab (tactics, endgames, openings) | Lucas Chess has its own training system |
| Opening tab (opening book management) | ChessBase-specific; Lucas Chess uses its own book |
| DGT Board group | Hardware peripheral not supported |
| Chess Media System | ChessBase online system |
| LiveBook | ChessBase online system |
| Contribute Engine / Lists of Honour | ChessBase online system |
| Open Positions | ChessBase online system |
| 3D board (Board 3d group) | Lucas Chess does not have a 3D board renderer |
| Raytraced board | Same — Lucas Chess 2D only |
| Submit Position (online) | ChessBase online |
| Tournament version | Tournament arbiter feature — out of scope |

---

## Context-visibility matrix

All tabs are always visible. Button enable/disable state within the ribbon follows this matrix.
"–" = irrelevant (button not present in this context).

| Button / Group | Home screen | Human to move | Engine thinking | Tutor thinking | Paused | Replay |
|---|---|---|---|---|---|---|
| New Game (Play) | ✅ enabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | ⬜ disabled |
| Levels (Play) | ✅ enabled | ✅ enabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | – |
| Resign / Draw (Game) | ⬜ disabled | ✅ enabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | – |
| Restart / Takeback (Game) | ⬜ disabled | ✅ enabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | – |
| Hint (Coaching) | ⬜ disabled | ✅ if hints>0 | ⬜ disabled | ⬜ disabled | ⬜ disabled | – |
| Analysis / Play Now (`TB_STOP`) | hidden | hidden | ✅ visible | hidden | hidden | hidden |
| Analysis / Pause (`TB_PAUSE`) | hidden | ✅ visible | ⬜ disabled | ⬜ disabled | hidden | ✅ visible |
| Analysis / Continue (`TB_CONTINUE`) | hidden | hidden | hidden | hidden | ✅ visible | hidden |
| Analysis / Stop Tutor (`TB_TUTOR_STOP`) | hidden | hidden | hidden | ✅ visible | hidden | hidden |
| Analysis / Navigate (Prev/Next) | ⬜ disabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | ⬜ disabled | ✅ enabled |
| Analysis / Tools / Variations / Utilities | ⬜ disabled | ✅ if in allowlist | ✅ if in allowlist | ✅ | ⬜ | ⬜ |

---

## Toolbar key → tab/group/slot mapping

This is the authoritative mapping from Caissa TB_ keys to ribbon placement.
Keys not listed here route to the overflow group.

| Key | Label (WBase) | Tab | Group | Size | Notes |
|---|---|---|---|---|---|
| `caissa:fritz_level` | New Game | Home | Play | large | |
| `TB_RESIGN` | Resign | Home | Game | small | |
| `TB_DRAW` | Offer Draw | Home | Game | small | |
| `TB_REINIT` | Restart | Home | Game | small | |
| `TB_TAKEBACK` | Take Back | Home | Game | small | Hidden when takeback disabled |
| `TB_ADVICE` | Hint | Home | Coaching | small | Hidden when hints=0 |
| `TB_HELP` | Help | Home | Coaching | small | |
| `TB_PAUSE` | Pause | Analysis | Engine | small | |
| `TB_CONTINUE` | Continue | Analysis | Engine | small | |
| `TB_STOP` | Play Now | Analysis | Engine | large | |
| `TB_TUTOR_STOP` | Stop Tutor | Analysis | Engine | small | |
| `TB_PREVIOUS` | Previous | Analysis | Navigate | small | |
| `TB_NEXT` | Next | Analysis | Navigate | small | |
| `TB_VARIATIONS` | Variations | Analysis | Tools | small | |
| `TB_TOOLS` | Tools | Analysis | Tools | small | |
| `TB_UTILITIES` | Utilities | Analysis | Tools | small | |
| `TB_CONFIG` | Configure | Engine | Configuration | large | |
| `TB_SETTINGS` | Options | Engine | Configuration | small | |
| `TB_OPEN` | Open | File panel | — | — | |
| `TB_SAVE` | Save | File panel + QAT | — | — | |
| `TB_SAVE_AS` | Save as | File panel | — | — | |
| `TB_READ_PGN` | Read PGN | File panel | — | — | |
| `TB_PASTE_PGN` | Paste PGN | File panel | — | — | |
| `TB_OPTIONS` | Options | File panel | — | — | |
| `TB_QUIT` | Quit | File panel | — | — | |
| `TB_CLOSE` | Close / Home | QAT | — | — | |
| `TB_CANCEL` | Cancel | QAT | — | — | |
| `TB_END_REPLAY` | End replay | QAT | — | — | |
| `caissa:switch_mode` | Switch mode | File panel | — | — | Lets user return to Classic mode |

**Overflow (deferred — no permanent slot in v1):**
`TB_ACCEPT`, `TB_CHANGE`, `TB_SHOW_TEXT`, `TB_PGN_LABELS`, `TB_ADJOURN`,
`TB_ADJUDICATOR`, `TB_ADJUDICATOR_STOP`, `TB_COMMENTS`, `TB_REPLAY`

---

## Implementation notes

- Ribbon JSON file: `Resources/Ribbons/modern-fritz.json`
- Group kind `"slots"` for all action groups; `"panes"` for checkbox groups
- Large buttons use `"size": "large"` in the slot spec
- Small buttons use `"size": "small"`
- Dropdown panels are implemented as `caissa:dropdown_<name>` actions that open
  `WDropdownPanel` floating windows (to be implemented)
- Toggle buttons (Analyse, Flip Board, Full Screen) use `"toggle": true` in slot spec
- All `caissa:` namespaced actions registered through the `Actions` plugin system
- Key resolution: standard `TB_*` constants via `Constantes` for existing Lucas Chess actions;
  new actions register under `caissa:fritz_*` namespace
