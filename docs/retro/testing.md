# Testing Guide

The Retro Engine test suite is structured so that the full logic of the subsystem
can be tested without a copyrighted binary present and without `unicorn` installed.

---

## Four test tiers

### Tier 1 — `retro` (always runs, no ROM, no unicorn)

The workhorse. Uses `ScriptedCpu` from `bin/Code/Retro/Fakes.py` to replay pre-recorded
boundary events against the full logic stack (`Think.py`, `Uci.py`, `Bridge.py`, etc.).
Also covers structural invariants (import purity, manifest schema, docstring completeness).

```bash
make test   # includes -m "unit or rpa or retro"
```

### Tier 2 — `retro_emu` (needs `unicorn`)

Tests that load a synthetic machine-code program under real Unicorn and verify that
the CPU seam works correctly: memory mapping, register access, fault handling,
trap dispatch, instruction budgets. The synthetic programs are assembled by the test
suite from raw opcode bytes — no copyrighted code.

```bash
pip install -r requirements-retro.txt
make test-retro-emu
```

### Tier 3 — `retro_rom` (needs unicorn + user-supplied binary)

The bit-exactness regression net. Replays the committed corpus against the real engine
and asserts every move matches. Also includes the 100-run determinism test and the
two-process determinism test.

```bash
export CAISSA_RETRO_ROM=/path/to/BattleChess
make test-retro-rom
```

### Tier 4 — dev/lab (not in CI)

`tools/retro-recon/` — Phase 1 spike tooling. Used for binary identification, memory
tracing, and ground-truth capture. Deleted in Phase 10.

---

## Running without a ROM

`make test` passes with no ROM and no `unicorn`. This is a hard requirement (NFR-6).
The `ScriptedCpu` in `Fakes.py` replays observation traces to drive `Think.py`
end-to-end. Corpus entries from the real engine are committed; the test suite verifies
the shim's replay logic against those entries without re-running the original.

---

## Synthetic ROM builders

`Fakes.build_synthetic_hunk(code_bytes, bss_size=0, relocs=None)` returns bytes
that form a valid minimal Amiga Hunk container around the given code. Tests for
`Rom.py` use this to exercise the parser with no copyrighted content.

`Fakes.build_synthetic_com(code_bytes)` does the same for the DOS .COM format.

---

## Observation traces

Traces committed to `tests/unit/retro/_fixtures/traces/*.json` are
`TRACE_OBSERVATION` level — boundary events only, no code bytes. They are the
inputs to `ScriptedCpu.replay()` and drive the full think path in Tier 1.

Full (`TRACE_FULL`) traces are written to `UserData/Retro/Traces/` (gitignored)
by `tools/caissa-retro capture-trace` during corpus capture. They are never committed.

---

## Coverage

```bash
make cov-retro   # ≥ 90% branch coverage for Code.Retro (Cpus/ omitted)
```

`Cpus/Unicorn68k.py` and `Cpus/UnicornX86.py` are in `.coveragerc-retro`'s omit list,
exactly as `Driver.py` is omitted from the RPA coverage target. Their coverage comes
from Tier 2 tests, which run separately.

---

## Marker reference

| Marker | Requires | In `make test`? |
|---|---|---|
| `retro` | nothing | yes |
| `retro_emu` | `unicorn` package | no |
| `retro_rom` | unicorn + `CAISSA_RETRO_ROM` | no |
