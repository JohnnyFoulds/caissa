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
