# Theme & Mode System — Software Design Document

**Status:** Specified — not yet implemented  
**Supersedes:** ad-hoc label edits in `WindowConfig.py` (reverted)

---

## 1. Problem statement

The app currently conflates three independent concepts under the word "Mode":

| Config key | What it actually controls | Current label |
|---|---|---|
| `x_style_mode` | Colour / visual theme (QSS + colours file) | **Mode** |
| `x_ui_mode` | Feature-set filter (menus, toolbar, new screens) | **UI mode** |
| `x_style` | Qt widget renderer (`Fusion`, `macOS`, …) | Window style |

The collision between "Mode" and "UI mode" in the same dialog is the symptom of a deeper architectural gap: **neither a theme nor a mode has a sanctioned way to customise dialogs, labels, or the General configuration screen itself**. Ad-hoc `if/else` checks in `WindowConfig.py` are the only current escape valve, and they don't scale.

---

## 2. Terminology — canonical definitions

These terms are fixed for the rest of this document and all implementation work.

### Theme
*What the app looks like and how its dialogs are described.*

A theme controls:
- Visual appearance: colours, fonts, icon pack, border radius, spacing (via `.qss` + `.colors`)
- Dialog labels: human-readable names for settings fields and tabs
- Dialog field visibility: which fields are shown or hidden
- Qt widget renderer (`x_style`) default

A theme is identified by the stem of its `.qss` file in `Resources/Styles/`. Examples: `Caissa`, `Dark`, `By default`.

### Mode
*What features the app exposes and how its surface is structured.*

A mode controls:
- Menu allowlist: which `Option.key` values are visible across all 7 root menus
- Toolbar allowlist: which `TB_*` and action keys survive `pon_toolbar`
- Injected actions: actions prepended to every toolbar (`toolbar_inject`)
- Mode-owned settings: fields appended to the Configuration dialog under a dedicated tab
- Optionally: a Python UI-hook module for structural UI changes beyond data-driven config

A mode is identified by the `"name"` field in its `Resources/Modes/<name>.json` file. Examples: `classical`, `Coach`, `Analyse`.

### The classical invariant
The `classical` mode + the absence of a theme overlay **must reproduce the upstream Lucas Chess R6 experience exactly**, with one permitted addition: the **Mode combobox** (our `x_ui_mode` picker) in the Configuration dialog, so the user can switch to a Caissa mode. Nothing else from our work may be visible or active in classical mode. This invariant is the regression safety net for all development.

---

## 3. Architecture

The system has three layers, each independently optional. All three compose cleanly: classical mode + no overlay = upstream experience. Caissa theme + any mode = fully customised experience.

```
┌─────────────────────────────────────────────────────┐
│  Layer 3 — Mode UI hooks  (Python, optional)        │
│  bin/Code/UIModes/actions/<mode>_ui.py              │
│  patch_config_form / on_mode_enter / on_mode_exit   │
├─────────────────────────────────────────────────────┤
│  Layer 2 — Mode config extension  (JSON)            │
│  Resources/Modes/<name>.json  →  "config_section"  │
│  Appends a new tab + fields to the Config dialog    │
├─────────────────────────────────────────────────────┤
│  Layer 1 — Theme UI overlay  (JSON)                 │
│  Resources/Styles/<name>.ui.json                    │
│  Renames labels, hides fields, renames tabs         │
└─────────────────────────────────────────────────────┘
         ↓ all applied by the dialog builder
  bin/Code/Config/WindowConfig.py  (base definition)
```

Layers are applied in order: base → theme overlay → mode extension → mode hook.

---

## 4. Layer 1 — Theme UI overlay

### File location
`Resources/Styles/<theme-name>.ui.json`

Absence of this file = no overlay applied = upstream behaviour preserved. The `By default` and `Dark` and `Light` and `Mid` themes intentionally have no overlay file.

### Schema

```jsonc
{
  // Rename any dialog label. Key = original English string (before _()
  // translation). Value = new label, or null to hide the field entirely.
  // A null here is equivalent to adding the key to "hide" below.
  "labels": {
    "Mode":         "Theme",
    "UI mode":      "Mode",
    "Window style": null,
    "Menu Play":    null,
    "General configuration": "Settings"
  },

  // Tab renames. Key = original tab name, value = new name.
  "tabs": {
    "Boards 1":     "Pieces",
    "Boards 2":     "Board",
    "Appearance 1": "Layout",
    "Appearance 2": "Colours",
    "Change elos":  "Rating"
  },

  // Fields to suppress entirely (alternative to null in labels).
  "hide": [
    "Preventing system crashes when playing"
  ],

  // Default Qt style to apply when this theme is active.
  // Caissa themes must use "Fusion" — other styles ignore QSS.
  "default_style": "Fusion"
}
```

### Rules
- Keys in `labels` and `hide` match the **original English string** passed to `_()`, not the translated output. This keeps the overlay locale-independent.
- A `null` label hides the field and removes it from `li_gen` unpacking. The dialog builder must adjust the positional unpack accordingly (see §6).
- `tabs` renames apply to `form.add_tab()` calls.
- `default_style` is applied at mode-entry alongside the QSS, not saved permanently.

### Caissa theme overlay (target state)
`Resources/Styles/Caissa.ui.json`:
```json
{
  "labels": {
    "Mode":         "Theme",
    "UI mode":      "Mode",
    "Window style": null,
    "Menu Play":    null,
    "Preventing system crashes when playing": null
  },
  "tabs": {
    "Boards 1":     "Pieces",
    "Boards 2":     "Board",
    "Appearance 1": "Layout",
    "Appearance 2": "Colours",
    "Change elos":  "Rating"
  },
  "default_style": "Fusion"
}
```

---

## 5. Layer 2 — Mode config extension

### New key in `Resources/Modes/<name>.json`: `config_section`

Absent = no extra tab added. When present, a new tab is appended to the Configuration dialog after "Change elos".

### Schema

```jsonc
{
  "name": "Coach",
  // ... existing keys ...
  "config_section": {
    "tab": "Coach",           // Tab label shown in the dialog
    "namespace": "coach",     // Key prefix used in config storage
    "fields": [
      {
        "type": "combobox",
        "label": "Default Maia level",
        "key": "maia_level",              // stored as coach.maia_level
        "options": [[1100,1100],[1200,1200],[1300,1300],[1400,1400],
                    [1500,1500],[1600,1600],[1700,1700],[1800,1800],
                    [1900,1900],[2200,2200]],
        "default": 1500
      },
      {
        "type": "checkbox",
        "label": "Enable Tutor automatically",
        "key": "auto_tutor",
        "default": true
      },
      {
        "type": "checkbox",
        "label": "Disable clock by default",
        "key": "no_clock",
        "default": true
      }
    ]
  }
}
```

### Supported field types (initial set)
`combobox`, `checkbox`, `spinbox`, `edit`

### Storage
Mode-owned settings are stored as `configuration.mode_settings[namespace][key]`, backed by the same pickle. They are never touched by classical mode. If a mode's config_section changes (fields added/removed), missing keys fall back to their `default` values.

---

## 6. Layer 3 — Mode UI hooks (optional Python)

For structural changes that cannot be expressed in JSON — alternative layout, custom panels, new non-dialog UI.

### File location
`bin/Code/UIModes/actions/<mode_name_lowercase>_ui.py`

Absence = no hooks. The file is loaded lazily when the mode activates.

### Interface

```python
def patch_config_form(form, configuration, overlay):
    """Called after the base form and theme overlay are applied,
    before the form is displayed. Can add, remove, or reorder fields."""

def on_mode_enter(main_window):
    """Called once after app restart into this mode."""

def on_mode_exit(main_window):
    """Called before app restart out of this mode."""
```

All three are optional — implement only what the mode needs. Hooks receive a reference to the in-progress form object (same type as in `WindowConfig.py`) and can call the same `form.combobox`, `form.checkbox` etc. methods.

---

## 7. Dialog builder changes (`WindowConfig.py`)

The base form definition in `WindowConfig.py` is **not changed**. The overlay is applied as a thin wrapper around the form builder object.

### Implementation approach

Before calling `options(parent, configuration)`:
1. Load the active theme's `.ui.json` if it exists → build `overlay` dict
2. Wrap the `form` object in an `OverlayForm` proxy:
   - `combobox(label, ...)`: if `label` is in `overlay["labels"]` → use new label; if value is `null` → skip entirely and record as hidden
   - `add_tab(label)`: apply `overlay["tabs"]` rename if present
3. After base form is built, apply `config_section` from the active mode → append new tab
4. Call `patch_config_form` hook if the active mode provides one

### Positional unpack safety

Fields hidden by a `null` overlay are **not added to `li_gen`**, so the positional unpack at lines 342–352 stays correct. The `OverlayForm` proxy must track which base-form fields were suppressed and ensure the unpack width matches what was actually added.

This is the only risky part of the implementation: the current starred `*_ui_mode_rest` approach is fragile. The implementation must replace it with a named-field approach — a dict keyed by the config attribute name — so hidden fields never corrupt the positional unpack.

---

## 8. The `x_menu_play` bug

`x_menu_play` is currently added to the form (line 59) but never saved: it lands in `*_ui_mode_rest[1]` and is silently discarded. The Mode system makes this setting redundant (the Play menu structure is controlled by the active mode's `menu_keys`). The fix is to hide it via the theme overlay and remove it from the form — not to fix the save path. The overlay approach achieves this cleanly; no Python change is needed.

---

## 9. Classical invariant — enforcement

The `classical` mode and the absence of a theme overlay must produce a bit-for-bit identical dialog to upstream Lucas Chess R6. This is enforced by:

1. No `.ui.json` file exists for `By default`, `Dark`, `Light`, or `Mid` themes.
2. `classical.json` has `config_section: null`.
3. No `classical_ui.py` hook file exists.
4. A test (`tests/test_classical_invariant.py`) builds the config form in classical mode and asserts the field list exactly matches the upstream set.

The **only** deliberate deviation: the `UI mode` combobox is present even in classical. This is the escape hatch and is explicitly permitted.

---

## 10. Implementation sequence

| Step | Deliverable | Touches |
|---|---|---|
| 1 | `OverlayForm` proxy class | new `bin/Code/Config/FormOverlay.py` |
| 2 | Overlay loading in `WindowConfig.options()` | `WindowConfig.py` (minimal, ~10 lines) |
| 3 | `Resources/Styles/Caissa.ui.json` | new file |
| 4 | Named-field unpack replacing `*_ui_mode_rest` | `WindowConfig.py` |
| 5 | Mode `config_section` reader + tab appender | `WindowConfig.py` + `UIModes.py` |
| 6 | Mode settings storage (`mode_settings`) | `Configuration.py` |
| 7 | Mode UI hook loader | `UIModes.py` |
| 8 | Classical invariant test | `tests/` |

Steps 1–4 are the minimum viable delivery: Caissa theme gets clean labels, classical is untouched, no structural risk. Steps 5–8 unlock mode-owned settings and drastic UI changes.

---

## 11. Out of scope

- Board appearance (piece sets, square colours) — already handled by the existing `ConfigBoard` system and `.lktheme3` files
- Live hot-reload of theme/mode changes without restart — requires refactoring `init_app_style` callers; deferred
- Per-mode font overrides in the dialog builder — handled via `default_style` in the overlay and existing `x_font_*` config keys
- Translating the `.ui.json` label values — overlay labels are always in English and go through `_()` the same as base labels
