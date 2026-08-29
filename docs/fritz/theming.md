# Fritz Mode — Theming Guide

**Status:** Stub — content delivered in Phase 6  
**See also:** `docs/fritz/qss-contract.md`, `docs/fritz/decisions.md` D3, D4

---

Fritz mode ships in two themes:

- **`Fritz`** (light) — the default, matches real Fritz 18 chrome
- **`Modern Fritz`** (dark) — the sibling dark variant

Both themes share `"hook": "modern_fritz"` and differ only in their `.qss` and `.colors` files.

## Adding a new Fritz colour theme

*This section will be filled in Phase 6 when the full theming pipeline is validated.*

Until then, see:
- `Resources/Styles/Fritz.qss` and `Resources/Styles/Fritz.colors` for the light theme
- `Resources/Styles/Modern Fritz.qss` and `Resources/Styles/Modern Fritz.colors` for the dark theme
- `docs/fritz/qss-contract.md` for the `qproperty-` contract used by custom-painted widgets
- `docs/fritz/decisions.md` D3 (design values in QSS, not a sidecar) and D4 (light default)
