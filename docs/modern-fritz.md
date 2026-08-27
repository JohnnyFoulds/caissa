# Modern Fritz Retro Skin — Specification

## Purpose

Modern Fritz is a Caissa UI mode that delivers a Fritz-inspired chess GUI aesthetic:
deep navy backgrounds, the iconic Fritz-blue accent, and a focused game environment.
It is the first of the retro skin suite (Phase 8) and demonstrates that the
mode `style` + `icons` fields fully drive appearance with zero new Python code.

## Design

| Role | Value | Rationale |
|---|---|---|
| Background | `#0c1624` | Deep navy — distinctly Fritz, darker than Midnight |
| Surface | `#13223c` | Panel blue |
| Border | `#2d5080` | Steel blue hairline |
| Text | `#c8dae8` | Cool white |
| Text-dim | `#6c8fb0` | Muted blue |
| **Accent** | `#1976d2` | **Fritz signature blue** |
| Accent hover | `#42a5f5` | Lighter blue |
| Success | `#43a047` | Green |
| Danger | `#e53935` | Red |

Geometry (radius, padding, margins) is byte-identical to Midnight so the parity
check passes and no new layout logic is needed.

## Files

| File | Role |
|---|---|
| `Resources/Styles/Modern Fritz.qss` | QSS widget styles derived from Midnight.qss |
| `Resources/Styles/Modern Fritz.colors` | Color values for all 88 keys (same set as Midnight) |
| `Resources/Modes/modern-fritz.json` | Mode definition: pins theme + icon pack |

## Mode JSON fields used

- `style`: `"Modern Fritz"` — forces this theme when the mode is active
- `icons`: `"MIDNIGHT"` — uses the midnight (light-on-dark) icon pack
- `toolbar`/`menu_keys`: `null` — full Classical feature set (no filtering)

## QSS authoring rules compliance

- **Q1**: No `#RRGGBB` on a line with more than one colon
- **Q2**: No new keys added to `colors.template` or other `.colors` files —
  Modern Fritz uses the identical 88-key set as Midnight
- **Q3**: All selectors on their own line, `{` on the next line

## `InitApp.py` integration

`init_app_style` checks `active_mode().get("style")` and, if set and the corresponding
`.qss` exists, uses it as the effective `style_mode` for the current session.  The user's
`x_style_mode` preference is not overwritten — the mode pinning is session-scoped.

`apply_live_style` resolves `active_mode().get("icons")` as an attribute name on
`IconosBase.Icons` and passes the resulting int to `icons.reset()`, falling back to
`x_style_icons` if the name is absent or unrecognised.
