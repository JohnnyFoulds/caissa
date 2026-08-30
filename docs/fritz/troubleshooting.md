# Fritz Mode — Troubleshooting

**Status:** Stub — content delivered in Phase 6  
**See also:** `docs/fritz/concepts.md`, `docs/fritz/decisions.md`

---

## Common symptoms

| Symptom | Likely cause | Where to look |
|---|---|---|
| Pane checkboxes do nothing | `pane_api` captured before `main_window` assigned | `bin/Code/Fritz/Ribbon.py:57-70` — FR-10 (Phase 1) |
| Eval bar pane checkbox is missing / no-op | `eval_bar` has no `PaneSpec` entry | `modern_fritz_ui.py` `_PANE_SPECS` — FR-12 (Phase 1) |
| `▼` button does nothing | `WDropdownPanel` not yet implemented | Phase 2 deliverable |
| Flip Board skips coordinate relabelling | Uses `redraw()` instead of `Board.rotate_board()` | `caissa:flip_board` action — FR-15 (Phase 3) |
| Levels button does nothing | `TB_LEVEL` unhandled in `run_action` | `ManagerPlayAgainstEngine.py:628` — FR-13 (Phase 3) |
| Hint / Suggestion always greyed out | `WFritzNewGame` sets `"HINTS": 0` | `WFritzNewGame.py` — FR-14 (Phase 3) |
| Pane sizes reset on restart | `GeometryStore` not wired | Phase 1 deliverable |
| macOS crash on mode enter | Analysis bar drop-shadow before `manager.start()` | `modern_fritz_ui.py:330-334` — keep `force_hidden` before `activate_analysis_bar` |

*Full troubleshooting documentation will be expanded in Phase 6.*
