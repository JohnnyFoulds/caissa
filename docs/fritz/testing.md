# Fritz Mode — Testing Guide

**Status:** Stub — content delivered in Phase 6  
**See also:** `docs/process/sdd-workflow.md`, `docs/features/fritz-mode/feature_steps.md`

---

## Test suites

Fritz mode has three test suites in ascending integration depth:

| Suite | Command | What it covers |
|---|---|---|
| Unit | `make test` (`-m unit`) | Pure-tier modules, RibbonModel validation, GeometryStore, Layouts |
| UI (in-process) | `make test-ui` (`-m ui`) | Ribbon rendering, pane visibility, offscreen Qt |
| Real-execution | `tools/caissa` + manual verification | Boot state, engine reply toggle, layout persistence |

## Key test files

- `tests/test_ribbon_map.py` — T-RMAP-01..09 validate the ribbon JSON schema
- `tests/ui/test_fritz_layout.py` — Fritz mode boot state and pane layout (offscreen Qt)
- `tests/ui/test_fritz_ribbon.py` — T-RIB-01..11 ribbon widget behaviour (offscreen Qt)
- `tests/unit/fritz/test_completeness.py` — purity-tier AST walk for `bin/Code/Fritz/`

## Marker discipline

Every test module must declare exactly one `pytestmark`:

```python
pytestmark = pytest.mark.unit     # fast, no Qt, no I/O
pytestmark = pytest.mark.ui       # in-process Qt, QT_QPA_PLATFORM=offscreen
```

Deferred tests use `@pytest.mark.xfail(strict=True)` — never `skip`.

## Running the design mockup tools

```bash
# Ribbon geometry report vs measured Fritz 18 reference
PYTHONPATH=. .venv/bin/python3 tools/design/ribbon_report.py --variant light
PYTHONPATH=. .venv/bin/python3 tools/design/ribbon_report.py --variant dark
```

*Full testing documentation will be expanded in Phase 6.*
