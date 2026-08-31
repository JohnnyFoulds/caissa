# Retro Engine — Production Readiness (Gate E)

**Status:** Completed 2026-08-28

This document records the Gate E (production readiness) checklist for the
Battle Chess Retro Engine feature.

---

## Gate Checklist

### Architecture invariants (N-RETRO-*)

| Invariant | What it enforces | Test |
|---|---|---|
| N-RETRO-1 | `Types.py`, `Errors.py` zero third-party imports | `test_foundations.py` |
| N-RETRO-2 | `unicorn` confined to `Cpus/*` | `test_foundations.py` |
| N-RETRO-3 | Importing `Code.Retro` does not pull in unicorn | `test_foundations.py` |
| N-RETRO-4 | No code bytes in committed trace fixtures | `test_oracle.py` |
| N-RETRO-5 | PySide6 absent from `Code.Retro` | `test_foundations.py` |
| N-RETRO-7 | All public callables have docstrings | `test_completeness.py` |
| N-RETRO-8 | Think calls are deterministic | `test_think.py` (FakeCpu) |
| N-RETRO-11 | Classical mode does not import `Code.Retro` | `test_completeness.py` |

### Functional requirements (FR-*)

| Requirement | Status | Notes |
|---|---|---|
| FR-1: UCI handshake | ✅ | `test_uci.py` — all option lines emitted |
| FR-2: Graceful ROM-less degradation | ✅ | `test_uci.py` — `bestmove 0000` + info |
| FR-4: FEN position injection | ✅ | `test_bridge.py` — write/read round-trip |
| FR-6: EmuLevel option | ✅ | `test_uci.py` — setoption accepted |
| FR-7: EmuClockRate + EmuStrictOriginal | ✅ | `test_uci.py` — strict guard test |
| FR-9: DOS x86 second target | 🟡 | Scaffolding complete; ROM-tier pending |

### Non-functional requirements (NFR-*)

| Requirement | Status | Notes |
|---|---|---|
| NFR-2: No wall-clock calls in think path | ✅ | `test_completeness.py` |
| NFR-7: `caissa-retro audit-tree` | 🟡 | Deferred to Phase 10+ |
| NFR-8: Deterministic replay (FakeCpu) | ✅ | `test_think.py` |
| N-RETRO-10: Handshake < 2s | ✅ | `test_uci.py::test_uci_handshake_completes_within_two_seconds` |

---

## Test Tiers

```text
Tier          Marker       What runs                   Status
──────────────────────────────────────────────────────────────────
Fast unit     retro        FakeCpu, no unicorn, no ROM  ✅ 124 passing
Emulator      retro_emu    Unicorn68k/X86, synthetic    ✅ skipped pending unicorn
Bit-exact     retro_rom    Real ROM, corpus replay      🟡 pending user ROM
```

---

## Residual Gaps

1. **DOS ROM**: `test_dos_rom_hash_matches_manifest` and `test_dos_think_returns_legal_move`
   remain as `retro_rom` stubs until the user supplies the DOS binary and its SHA256
   is added to `Resources/Retro/manifest.json`.

2. **`caissa-retro audit-tree`**: The spec includes a sub-command that confirms no
   committed code bytes across the repo.  This is not yet implemented.

3. **Corpus completeness**: Only one position (`startpos, level=1`) is in the Amiga
   corpus fixture.  Full corpus capture requires running `make test-retro-rom` with
   a verified ROM.

---

## How to Run

```bash
# Fast suite (always works)
make test              # retro marker — 124 passing

# Emulator tier (requires: pip install -r requirements-retro.txt)
make test-retro-emu

# ROM tier (requires: export CAISSA_RETRO_ROM=/path/to/BattleChess.bin)
make test-retro-rom

# Protocol smoke test (no ROM needed)
printf 'uci\nquit\n' | tools/caissa-retro
```
