# Retro Engine — Software Design Document

**Status:** Specified — implementation pending  
**Branch:** phases `docs/retro-engine`, `spike/retro-recon`, `chore/retro-foundations`, … (one per phase; see feature_steps.md)  
**Initial idea:** [initial_idea.md](initial_idea.md)  
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## 1. Problem Statement

Battle Chess (Interplay, 1988) contains a chess engine with a distinctive personality:
historically weak, predictable, nostalgic. There is no UCI-compatible, legally
redistributable version of it. Running the engine today requires a full Amiga emulator
and the whole game UI.

This spec defines the **Retro Engine** subsystem (`bin/Code/Retro/`): a UCI shim that
wraps the original machine code under a CPU emulator, calling only the isolated think
function. The result is a standalone UCI executable, bit-exact to the original, that
responds in milliseconds and integrates with Caissa and any modern chess tool.

---

## 2. Requirements

### 2.1 Business Requirements

| ID | Requirement |
|---|---|
| BR-1 | Expose the Battle Chess (1988) chess engine as a UCI-compatible engine. |
| BR-2 | Move selection **MUST** be bit-exact: same position, same level, same virtual-clock state → same move. |
| BR-3 | Move generation **MUST** complete in under 5 seconds at any difficulty level on modern hardware. |
| BR-4 | **No original binary, disk image, or extracted code segment may be committed.** User supplies their own copy, sha256-verified. |

### 2.2 Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | The shim **MUST** speak the UCI protocol over stdin/stdout and pass `Engines.is_valid_engine` as defined in `bin/Code/Engines/Engines.py:629`. |
| FR-2 | The shim **MUST** answer `uci` without a ROM present; `go` without a verified ROM **MUST** return an informative `info string` error and a null move rather than crashing. |
| FR-3 | The shim **MUST** load a user-supplied binary, verify its sha256 against `Resources/Retro/manifest.json`, and refuse with an actionable error message on mismatch. |
| FR-4 | The shim **MUST** support `position startpos moves …` as the primary position input. |
| FR-5 | The shim **SHOULD** support `position fen …` for arbitrary positions; if the engine cannot accept arbitrary positions (D4), this **MAY** be scoped out of v1 with a documented error. |
| FR-6 | Difficulty levels from the original game **MUST** be exposed as UCI options and map deterministically to original engine parameters. |
| FR-7 | The virtual clock rate **MUST** be exposed as a UCI option (`EmuClockRate`, integer percent, default 100). `EmuStrictOriginal=true` **MUST** reject any value other than 100. |
| FR-8 | `tools/caissa-retro` **MUST** be a standalone executable runnable without Qt or Caissa. |
| FR-9 | The Amiga binary **MUST** be supported as the primary target. The DOS binary **SHOULD** be supported as a second target once the Amiga path is stable (Phase 9). |
| FR-10 | A corpus of recorded (position, level) → move pairs **MUST** be committed and replayed by the test suite to serve as a regression net. |

### 2.3 Non-Functional Requirements

| ID | Constraint |
|---|---|
| NFR-1 | `Types.py` and `Errors.py` **MUST** have zero third-party imports. Enforced by `test_types_module_has_no_third_party_imports` and `test_errors_module_has_no_third_party_imports`. |
| NFR-2 | All public and non-public callables **MUST** have RST/Sphinx docstrings per `docs/standards/docstring-standards.md`. |
| NFR-3 | All signatures **MUST** carry complete type annotations. |
| NFR-4 | `unicorn` **MUST** be imported only by `bin/Code/Retro/Cpus/`. Importing `Code.Retro` **MUST NOT** pull `unicorn` into `sys.modules`. |
| NFR-5 | `Code.Retro` **MUST NOT** import PySide6. The UCI shim must run headless as a standalone process. |
| NFR-6 | `make test` (the `unit or rpa or retro` marker set) **MUST** pass with neither `unicorn` installed nor a ROM present. |
| NFR-7 | Cold start — from process launch to `uciok` — **MUST** complete within 2 seconds on hardware that passes `make test`. |
| NFR-8 | Move generation **MUST** be deterministic (N-RETRO-8): same `(fen, level, clock-rate)` → same move across 100 consecutive runs and across two fresh processes. |
| NFR-9 | No original code bytes **MAY** be committed. Committed corpus files are lists of moves and are factual data, not code. See §8 and `docs/retro/legal.md`. |
| NFR-10 | Every new `pytest.ini` marker **MUST** be declared in `pytest.ini` before the first test that uses it lands. |

### 2.4 Constraints & Assumptions

- The Battle Chess binary is still under copyright. BR-4/NFR-9 are non-negotiable.
- Factual data derived *from* a binary (offsets, struct layouts, move choices) is
  committed; code bytes and memory dumps are not. `docs/retro/legal.md` states this
  explicitly as the legal theory for the maintainer's own records.
- The Amiga binary is Amiga Hunk format, likely unpacked. If it is packed (PowerPacker,
  Imploder), the packer is well-understood and can be stripped in `Rom.py`.
- Unicorn's m68k core is QEMU-derived and targets 68020+. If strict 68000 semantics are
  required (D5), `Cpus/Unicorn68k.py` can be substituted with a Musashi backend without
  changing anything above the `Cpu` seam.
- The DOS binary is packed inside an installer (LZEXE/PKLITE); extracting it is a
  Phase 9 task, not a Phase 1 assumption.
- `CaissaError` is promoted to `bin/Code/Base/CaissaErrors.py` in Phase 2 (D1).
  `bin/Code/Rpa/Errors.py` re-exports it for backward compatibility.

---

## 3. Terminology & Existing Infrastructure

| Term | Definition |
|---|---|
| Think function | The entry-point subroutine in the original binary that accepts a board position and difficulty level and returns a move. The isolated callable called under Unicorn. |
| ROM | The user-supplied original binary (Amiga `BattleChess` executable or DOS extracted `.exe`). Named ROM by analogy with MAME's ROM-handling model. |
| Manifest | `Resources/Retro/manifest.json` — sha256 hashes and metadata for known-good dumps. No bytes; just hashes and offsets. |
| Corpus | `Resources/Retro/Corpus/*.jsonl` — recorded (position, level) → move pairs. Factual; no code bytes. |
| Ground truth | Corpus entries captured from the real game under a full-system emulator (FS-UAE, DOSBox), not from the shim. Used as independent bit-exactness oracle. |
| Virtual clock | Deterministic instruction-counted timer fed to the engine instead of wall time, making timed difficulty levels reproducible. |
| Observation trace | Boundary-level trace: entry state, trap calls, move result, instruction count. No PC stream, no code bytes. Committable. |
| Hunk format | Amiga executable container (HUNK_HEADER / HUNK_CODE / HUNK_END). Flat address space, well-documented. |
| MZ / COM | DOS executable containers. DOS target is Phase 9. |
| `ENG_FIXED` | Engine type constant in `bin/Code/Base/Constantes.py:291`. The appropriate type for a fixed-strength emulated engine in the Caissa registry. |
| Spike | A Phase 1, explicitly spec-exempt exploratory phase producing a findings document and corpus entries. Scratch tooling under `tools/retro-recon/`, deleted Phase 10. |

Existing infrastructure reused:

| Symbol | Location | Role |
|---|---|---|
| `CaissaError` | `bin/Code/Rpa/Errors.py:37` (moved to `bin/Code/Base/CaissaErrors.py` in Phase 2) | Repo-wide exception root |
| `Engines.Engine` | `bin/Code/Engines/Engines.py:15` | Engine descriptor |
| `Engines.is_valid_engine` | `bin/Code/Engines/Engines.py:629` | UCI handshake probe (must pass) |
| `ENG_FIXED` | `bin/Code/Base/Constantes.py:291` | Engine type for registry |
| `_EXTRA_ENGINES` | `bin/OS/darwin/OSEngines.py:208` | Where bundled engine entries go |
| `li_engines_fixed_elo` | `bin/OS/darwin/OSEngines.py:234` | Elo-ladder registration |

---

## 4. Architecture

```text
Purity tiers:

  Tier 0 — zero deps         Types.py, Errors.py
  Tier 1 — stdlib only       Manifest.py, Rom.py, Cpu.py (base seam)
  Tier 2 — unicorn only      Cpus/Unicorn68k.py, Cpus/UnicornX86.py
  Tier 3 — Tier 1+2          Traps.py, Bridge.py, Think.py, Oracle.py
  Tier 4 — Tier 3 + I/O      Uci.py, tools/caissa-retro

  Test infra:                 Fakes.py (Tier 1 — ScriptedCpu, FakeClock, synthetic ROM builders)
  Dev-only:                   Cpus/Recon.py (capstone disasm, deleted Phase 10)
  Resources:                  manifest.json, Corpus/*.jsonl, Fixtures/ (gitignored)
```

Layering invariant: nothing in a lower tier may import anything from a higher tier.
`Oracle.py` and `Fakes.py` depend only on `Types`/`Cpu` (Tier 0–1) and are peers of
`Think.py`, not upstream of it.

`Code.Retro` is lazy-loaded on first use. A plain app start MUST NOT pull it in
(N-RETRO-11 / Classical Invariant).

---

## 5. Module Contracts

### 5.1 `Types.py` (Tier 0)

```python
@dataclass(frozen=True)
class Arch: value: str   # "m68k" | "x86_16"

@dataclass(frozen=True)
class RomId: sha256: str; arch: Arch; title: str; release: str

@dataclass(frozen=True)
class MemRegion: address: int; data: bytes; name: str

@dataclass(frozen=True)
class MemoryImage: regions: tuple[MemRegion, ...]; entry: int; arch: Arch

@dataclass(frozen=True)
class Board: fen: str   # and other position data — struct determined in Phase 1

@dataclass(frozen=True)
class Level: value: int   # 0–n, original game's difficulty

@dataclass(frozen=True)
class ThinkRequest: board: Board; level: Level; clock_rate_pct: int

@dataclass(frozen=True)
class ThinkResult: move_uci: str; instr_count: int; virtual_ms: int
```

### 5.2 `Cpu.py` seam

```python
class Cpu:
    def load(self, image: MemoryImage) -> None: ...
    def read(self, address: int, size: int) -> bytes: ...
    def write(self, address: int, data: bytes) -> None: ...
    def get_reg(self, name: str) -> int: ...
    def set_reg(self, name: str, value: int) -> None: ...
    def hook_code(self, callback) -> None: ...
    def hook_mem_invalid(self, callback) -> None: ...
    def run(self, start: int, until: int, instr_budget: int) -> RunResult: ...
```

`RunResult.reason` is one of: `"until_reached"`, `"budget_exhausted"`, `"trap_exit"`,
`"fault"`. `Fakes.ScriptedCpu` replays an observation trace against this seam.

### 5.3 `Manifest.py`

- `load() -> list[RomEntry]` — parse `Resources/Retro/manifest.json`; schema-validate
- `verify(path: Path) -> RomId` — sha256-check the user's file; raises `RomHashMismatchError` with the computed hash and a note pointing at `caissa-retro identify`
- `RomEntry` fields: `sha256`, `arch`, `title`, `release`, `think_entry`, `board_struct_offset`, `size_bytes`, `notes`

### 5.4 `Rom.py`

- `load_amiga_hunk(path: Path) -> MemoryImage` — parse HUNK_HEADER / HUNK_CODE / HUNK_BSS / HUNK_RELOC32 / HUNK_END; relocate; yield flat MemoryImage
- `load_dos_mz(path: Path) -> MemoryImage` — Phase 9 (raises `UnsupportedTargetError` until then)
- `detect_packer(data: bytes) -> str | None` — recognise PowerPacker / Imploder / LZEXE signatures; returns packer name or `None`

### 5.5 `Bridge.py`

- `encode_board(board: Board, profile: EngineProfile, cpu: Cpu) -> None` — marshal FEN into the engine's native struct in emulated memory
- `decode_move(cpu: Cpu, profile: EngineProfile) -> str` — read the result struct and return a UCI move string
- Round-trip property: for all positions reachable from startpos by legal moves, `decode_move(encode_board(board))` round-trips correctly.

### 5.6 `Think.py`

- `ThinkSession.run(request: ThinkRequest) -> ThinkResult` — orchestrator: verify ROM → load memory image → set up traps → marshal board → call think fn → decode move → return result
- `ThinkSession` is constructed once per process (ROM is loaded once, memory image cached).

### 5.7 `Uci.py`

Line-I/O seam: `Uci(readline, write)`. Pure — no unicorn, no Qt.

- Handles: `uci`, `isready`, `setoption`, `position`, `go`, `stop`, `quit`
- `uci` always succeeds; emits `id name Battle Chess (Retro) 1988`, `id author Interplay`, the standard options (`EmuLevel`, `EmuClockRate`, `EmuStrictOriginal`, `EmuRomPath`), then `uciok`
- `go` without a verified ROM: emits `info string ERROR: no verified ROM loaded …` + `bestmove 0000`
- `go` with a verified ROM: calls `ThinkSession.run`, emits `bestmove <move>`

### 5.8 `Oracle.py`

- `load_corpus(path: Path) -> list[CorpusEntry]` — load `Resources/Retro/Corpus/*.jsonl`
- `verify_corpus_entry(entry: CorpusEntry, session: ThinkSession) -> bool` — run the think and compare
- `source` field is load-bearing: `"shim"` = self-regression; `"fs-uae-manual"` or `"dosbox-manual"` = ground truth

---

## 6. ROM / Legal Policy

See also `docs/retro/legal.md`.

Items that **are** committed:
- `manifest.json` — sha256 hashes, file sizes, and metadata for known-good dumps
- Offset tables and struct layouts in `Profiles.py` — facts about the binary
- `Corpus/*.jsonl` — lists of (position, level, move) records — factual move data
- Observation traces — boundary events with no code bytes

Items that are **never** committed:
- The binary itself
- Any disk image (`.adf`, `.img`, `.dsk`)
- Any verbatim extracted code bytes
- Any full memory dump
- Any trace with `kind != "observation"` (i.e. traces including `code_bytes` or `pc_stream`)

The distinction is: facts *about* a binary vs. the binary itself.

---

## 7. Trace Redaction

Two trace levels:

- `TRACE_OBSERVATION` — boundary events only: entry register set, each trap call (name + args + return), each read of the board-struct region (offset + value), exit registers, total instruction count, virtual-clock ticks. **No PC stream. No opcodes. No code bytes. No raw memory dumps.** Committable.
- `TRACE_FULL` — includes PC stream and fetched bytes. Reproduces the program. Dev-local only; written under `UserData/Retro/Traces/` (gitignored). Never committed.

Enforced by `test_committed_traces_contain_no_code_bytes` — asserts every fixture under `tests/unit/retro/_fixtures/traces/` has `kind == "observation"` and none of the forbidden keys.

---

## 8. Error Semantics

`RetroError(CaissaError)` is the domain base. All errors are raised with
`raise SomeError("message") from exc` at catch sites. Every `logger.error()` at a
catch site includes `exc_info=True`.

| Class | Raised when |
|---|---|
| `RomNotFoundError` | The configured ROM path does not exist |
| `RomHashMismatchError` | sha256 does not match any manifest entry |
| `RomManifestError` | `manifest.json` is missing, malformed, or fails schema validation |
| `RomPackedError` | Binary is packed; includes the detected packer name |
| `CpuUnavailableError` | `unicorn` is not installed; includes the install command |
| `EmulationFaultError` | Unicorn raises a fault (unmapped memory, illegal instruction); includes PC and register dump |
| `EmulationBudgetError` | Think function exceeded the instruction budget |
| `TrapUnhandledError` | CPU jumped to a trapped address with no registered handler |
| `BoardEncodeError` | FEN cannot be represented in the engine's native struct |
| `MoveDecodeError` | The result struct could not be decoded as a legal UCI move |
| `ProfileError` | A Profile entry is internally inconsistent |
| `CorpusError` | Corpus file is malformed or a ground-truth entry disagrees |
| `TraceError` | Observation trace is malformed or contains forbidden keys |
| `RetroConfigError` | Misconfiguration (invalid option value, contradictory options) |

---

## 9. Non-Functional Constraints (N)

| ID | Constraint |
|---|---|
| N-RETRO-1 | `Types.py` and `Errors.py` have zero third-party imports |
| N-RETRO-2 | `unicorn` is imported only by `bin/Code/Retro/Cpus/` |
| N-RETRO-3 | Importing `Code.Retro` must not pull `unicorn` into `sys.modules` |
| N-RETRO-4 | No file tracked by git matches any sha256 in `manifest.json`; no `Resources/Retro/` file exceeds 512 KB |
| N-RETRO-5 | `Code.Retro` imports no PySide6 |
| N-RETRO-6 | Every manifest entry has `sha256` (64 hex chars), `arch`, `think_entry`, `board_struct_offset`, `size_bytes` |
| N-RETRO-7 | Every public callable has RST `:param:`/`:return:` docstrings |
| N-RETRO-8 | Same `(fen, level, clock-rate)` → same move across 100 consecutive runs and across two fresh processes |
| N-RETRO-9 | `make test` (retro marker) passes with no ROM and no unicorn |
| N-RETRO-10 | Cold start to `uciok` < 2 seconds |
| N-RETRO-11 | A plain app start does not import `Code.Retro` (Classical Invariant) |
| N-RETRO-12 | `EmuStrictOriginal=true` rejects `EmuClockRate` ≠ 100 |

---

## 10. Classical Invariant Impact

**Zero in production.** `Code.Retro` is never imported by the main app startup path.
It is loaded lazily when the user explicitly registers `tools/caissa-retro` as an
external engine or when the bundled `ENG_FIXED` entry is first used. The classical
mode + no theme overlay path is unaffected.

The invariant test `test_classical_start_does_not_import_code_retro` asserts no
`Code.Retro*` key appears in `sys.modules` after app bootstrap with classical mode.

---

## 11. Implementation Sequence

| Phase | Branch | Deliverable |
|---|---|---|
| 0 | `docs/retro-engine` | SDD artefacts, product docs, legal policy |
| 1 | `spike/retro-recon` | Recon spike — GO/KILL gate; `recon_findings.md` |
| 2 | `chore/retro-foundations` | `Types.py`, `Errors.py`, tooling config |
| 3 | `feat/retro-rom` | `Manifest.py`, `Rom.py`, ROM verification |
| 4 | `feat/retro-cpu` | `Cpu.py` seam, `Fakes.py`, `Cpus/Unicorn68k.py` |
| 5 | `feat/retro-traps` | `Traps.py`, `VirtualClock` |
| 6 | `feat/retro-bridge` | `Bridge.py` — FEN ↔ native struct |
| 7 | `feat/retro-think` | `Think.py`, `Oracle.py` — first end-to-end move |
| 8 | `feat/retro-uci` | `Uci.py`, `tools/caissa-retro`, Caissa registration |
| 9 | `feat/retro-dos` | `Cpus/UnicornX86.py`, DOS target, divergence report |
| 10 | `chore/retro-production` | Production readiness (Gate E) |

---

## 12. Out of Scope

- Any chess GUI; `tools/caissa-retro` speaks UCI and nothing else.
- Reimplementing the engine in Python or C.
- Shipping the original binary or any extracted code segment.
- Battle Chess II: Chinese Chess, Battle Chess 4000, or any other title.
- Game animations or sound.
- Networked play.
- Difficulty levels that require unemulated hardware (if any; determined in Phase 1).

---

## 13. Changelog

| Date | Author | Notes |
|---|---|---|
| 2026-08-28 | Johannes Foulds / Claude | Initial spec — all R/I/P/Q/N sections, Gate A |
