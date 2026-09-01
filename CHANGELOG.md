# Changelog

All notable changes to **Caissa** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Caissa uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Upstream base: **Lucas Chess R6.0.4** by Lucas Monge (GPL-3.0).

---

## [Unreleased]

### Added
- **RPA design-vision Phase 2c — StyleSource bridge**: `bin/Code/Rpa/Vision/StyleSource.py`
  (new, stdlib-only Tier 1).  `parse_rules()` generalises `QssRules.qproperties()` to all
  CSS properties, handling both Q3-correct `selector\n{...}` and inline `selector { prop: val; }`
  forms, `{KEY}` placeholders, and `::` pseudo-class colons.  `effective()` returns three-valued
  state: `"loaded_unmatched"` (selector in stylesheet but no widget of that type exists),
  `"matched_overridden"` (widget exists but `paintEvent` wins), `"effective"`, or `"unconfirmed"`
  (no live stylesheet).  `paint_colour_constants()` AST-scans a source file for bare
  `QColor("#RRGGBB")` class constants (E1 violations), handling both `QColor(...)` and
  `QtGui.QColor(...)` call forms.  `style_sources_for()` returns all rules from provided QSS
  sources with `effective` classification against the live widget-type set.  28 unit tests
  (27 passing + 1 `xfail(strict=True)` stub for `font_mismatch` detection, Phase 7).
  Gate test: `QTabWidget::pane` in `Caissa.qss` is `loaded_unmatched` — the rule that was
  diagnosed as the wrong fix target three times in a row.
- **Amiga RPA layer (Phase E)**: `bin/Code/Amiga/` — FS-UAE automation module mirroring
  `bin/Code/Dos/`.  `Driver.py` (`FsUaeProcess` + `FsUaeDriver`): Quartz screenshot
  (`screencapture -x -o -l <wid>`), SDL-safe two-step click (MOUSEMOVE→DOWN→UP), raw
  keycode send.  `Activities.py` (`AmigaRunner` + 8 `AmigaActivity` subclasses):
  `EnsureFsUaeRunning`, `WaitForTitle`, `WaitForBoard`, `AdvancePastTitle`,
  `StartNewGame`, `PlayMove`, `WaitForComputerReply`, `ExtractComputerMove`; each with
  precondition/execute/postcondition following the CHECK_PRE→ACT→SETTLE→VERIFY contract.
  `BattleChess.py`: geometry constants stubbed pending calibration.
  `tests/unit/amiga/test_activities.py`: 32 unit tests (all passing) using `FakeDriver`.
- **RPA process documentation**: `CLAUDE.md` adds "RPA Pattern for Automation —
  Non-Negotiable" rule; `docs/rpa/new-target-guide.md` — step-by-step guide for
  creating RPA layers for new application targets; `docs/rpa/uipath-mapping.md` gains
  a "When to Use an Activity vs Ad-Hoc Code" decision tree.
- **DOS corpus collection — reliable multi-move pipeline**: `WaitCpuReply` rewritten to use
  color-based `board_state()` comparison (pink/blue piece classification) instead of pixel-diff
  heuristics.  Two-phase detection: wait for first movement sign → 0.8s animation settle → read
  final board state.  Handles captures correctly (pink square becomes blue).  `MovePiece` gains
  a precondition that verifies a white piece is actually at the source square, catching stale game
  state from previous runs.  Fresh DOSBox-X kill-and-relaunch guarantees startpos.  Pipeline now
  records 5+ consecutive moves including captures without error.
- **Amiga ground-truth corpus (Phase F)**: `Resources/Retro/Corpus/fs-uae-manual.jsonl`
  records 27 unique Battle Chess (Amiga) AI responses via FS-UAE RPA automation.
  Five opening lines (Italian, Four Knights, London, English, King's Indian); AI plays Black.
  `SelectTwoDBoard` activity ensures consistent 2D board geometry before recording.
  `workbench_double_click` uses pure absolute `CGEventPost` (not delta events) so SDL2
  stays in non-captured mode during the Workbench phase.
- **retro_rom test tier — real assertions**: `tests/unit/retro/test_think.py` and
  `tests/unit/retro/test_uci.py` replace `pytest.skip()` stubs with live engine tests.
  Both verify that a corpus FEN produces a legal non-null bestmove from the real ROM.
- **DOS automation — first ground-truth corpus entry**: `Resources/Retro/Corpus/dosbox-manual.jsonl`
  records Battle Chess (DOS) responding `c7c5` (Sicilian Defence) to `1.e4`, verified deterministic
  across two independent fresh-launch runs.  Full pipeline: DOSBox-X launch → 2D board mode →
  two-click `e2e4` → CPU reply detected and verified.
- **DOS automation — two-click move and CPU detection improvements**:
  `DismissTitleScreen` now calls `driver.focus()` + 0.3s delay before ENTER to prevent keypresses
  reaching the user's focused window; `WaitCpuReply` gains `settle_ms=3000` (artefact decay) and
  a double-check (`inner_square_changed` on both CPU squares before accepting); brightness-delta
  direction rule (`Δbright after−before`) replaces the broken "brighter-in-before = FROM" heuristic
  that inverted from/to for black pieces.

- **Retro Engine — Phase A ground-truth attempt (A5 documented negative result)**:
  `docs/retro/reverse-engineering.md` now records two failed boot attempts: `vamos` crashes
  at PC=0xFFFF807C (exec library stubs not mapped); FS-UAE + AROS quits on
  `my_resolvesoftlink` stub before the startup-sequence runs.  Path forward documented:
  licensed Kickstart 1.3 (Amiga Forever), AROS+Workbench HDF, or DOSBox-X+DOS CHESS.EXE.
- **Retro Engine — real-execution reset (Phase A prep)**: `docs/retro/architecture.md`
  (494-line technical deep-dive; §Layout Paradox flags unresolved BSS-clear contradiction);
  `manifest.json` corrected hunk_code_size 72988 (was 84872, confirmed by hunktool); Level
  enum expanded L1-L9 (was NOVICE/EASY/INTERMEDIATE/HARD/EXPERT, 5 levels); `caissa-retro
  identify <path>` subcommand; `tools/caissa-retro` made executable; B1a/B3 recon docs
  (`reverse-engineering.md`, `rom-setup.md`, `uci-options.md`); 67 Phase 1-B recon scripts
  in `tools/recon/`.
- **Engineering standards**: CLAUDE.md and `sdd-workflow.md` add explicit "Mock tests ≠ real
  execution" rule; Gate D and Gate E require evidence of a real run before any feature with
  an opt-in tier (retro_rom, rpa_ui, rpa_cv) is closed.

### Fixed
- **Retro Engine — canonical Black opening response**: `caissa-retro` now returns a
  canonical opening response (e7e5, c7c5, e7e6, c7c6, d7d5, or a7a5) instead of falling
  back to a2a4 after `position startpos moves e2e4 go`.  Root cause: `computer_color` was
  computed after a `python-chess` FEN update that silently fell back to the startpos when
  `chess` was not installed, always producing `computer_color=0` and mirroring the board
  the wrong way.  Fix: compute `computer_color` from move-list parity before the
  `chess` block so it is always correct (`Uci.py`).  Separately, Unicorn M68K
  mis-decoded two 6-byte `CMPI.W` instructions as 4 bytes, leaving `CA 5C` / `08 00`
  trailing bytes executing as `AND.W (A4)+,D5` that corrupted A4 by +2 per outer-driver
  pass; fixed with inline byte patches (MOVEQ+CMP.W) and `ctl_flush_tb()` (`Think.py`).
  Retro oracle test (`test_oracle.py`) corrected to use flipped coordinates (0x44, 0x64)
  for the expected e2e4 raw bytes when `computer_color=0`.
  `pytest.ini` now excludes `tools/` from collection to prevent unrunnable recon scripts
  from aborting the test suite.
- **Retro Engine — decompressor prefetch simulation**: `Think.py` now correctly emulates
  the 68000's 4-byte prefetch buffer for Battle Chess's self-modifying startup decompressor.
  Two per-address hooks (`_hook_prefetch_79bc` at 0x79BC, `_hook_prefetch_79c8` at 0x79C8)
  detect when the decompressor has partially overwritten its own instruction bytes and
  manually execute the original ROM instruction (`lsl.w #2, d2` and `move.b (a2)+, (a1)+`
  respectively) instead of letting Unicorn raise `UC_ERR_EXCEPTION` on the illegal
  partial-write bytes.  Root cause: a zeroing loop writes zeros sequentially over 0x79BC
  producing `ORI.B-to-An` (illegal, but Unicorn OR-applies it corrupting A4 to 0xFFFFFFFF);
  the inner copy loop overwrites its own `12 DA` bytes with a LINE-A opcode.
  Both smokes now return real moves: `bestmove h2h4` and `bestmove h7h5`.
- **Retro Engine — White-to-move support (board-flip technique, Phase G)**: Engine now
  returns a real AI move for both sides.  Root cause: the AI's TC abort mechanism
  requires `PLAYER2_COLOR=1` (Black) and hangs when set to White.  Fix: when
  `computer_color=0`, mirror the board (ranks flipped, colors swapped) so the AI
  always searches as Black; the result move is flipped back to original coordinates.
  `Bridge.flip_sq88()` and `Bridge.flip_fen()` added; 8 new unit tests.  CLAUDE.md
  smoke test (`position startpos go`) now produces `bestmove h2h4` (AI move, not
  fallback).
- **Retro Engine — multi-move robustness (TC-snapshot + write-snapshot)**:
  `Think.py` now uses a two-snapshot strategy to prevent illegal moves across all
  valid positions.  When the TC (time-check) hook fires with a root-valid move
  the PC is redirected to the sentinel, stopping emulation immediately before any
  deeper-search node can overwrite the result slot.  A `_mem_write` fallback
  snapshot (filtered against a pre-emulation root-board snapshot) handles positions
  where TC fires after the result is already overwritten with garbage.  Root-board
  validation rejects pawn-straight-pushes to occupied squares, own-piece captures,
  and moves from squares that don't belong to the computer in the root position.
  Result: engine plays 17+ consecutive legal moves in the game test (was 2 before).
  `tests/unit/retro/test_retro_game.py` assertion raised to ≥10 engine moves.
- **Retro — Traps.py buffer overflow**: `AmigaTraps.install()` was writing
  `b"\x4e\x75" * size` (2×size bytes) into a size-byte region; corrected to `*(size//2)`.
- **Retro — Rom.py silent truncation**: hunk parser now emits one clear warning on the
  Dragon-crack non-standard bytes and stops (was silently dropping them with no count on
  how many times it warned); module-level logger added.
- **Retro — Uci.py**: EmuLevel max corrected 4→9; `default_rom_path()` fallback wired so
  `go` works without explicit `setoption`; `Level.NOVICE` reference removed.

- **Fritz Polish — Phase 9 (Production Readiness)**: Gate E complete; 94.22 % branch
  coverage for `Code.Fritz` per `fritz.coveragerc`; `make docs` clean (zero Sphinx
  warnings); `docs/features/fritz-polish/production_readiness.md` with 8-section
  checklist and 6 resolved findings; feature directory archived to
  `docs/features/_archive/fritz-polish/`.
- **Fritz Polish — Phase 7 (Office-style ribbon)**: `bin/Code/Fritz/RibbonModel.py` (pure:
  `load`, `state`, `overflow`, `best_tab`, `compact`); `bin/Code/Fritz/Ribbon.py` (`install`
  — degrades gracefully to plain toolbar on any failure); `bin/Code/Fritz/WRibbon.py`
  (`WRibbon` + QTabBar + QStackedWidget, `WRibbonPanesGroup` for pane checkboxes);
  `Resources/Ribbons/modern-fritz.json` (7-tab ribbon map: Home, File, Board, Training,
  Analysis, Opening, Engine); `Resources/Modes/modern-fritz.json` gains `"ribbon": "modern-fritz"`;
  `WBase.create_toolbar` installs the ribbon after all QActions are built; `WBase.pon_toolbar`
  routes through `WRibbon.sync` (idempotent, no widget reconstruction after first call);
  T-RMAP-01..08 unit tests all passing; `docs/fritz/ribbon.md` (Gate H).
- **Retro Engine — Phase 6 (Bridge — FEN↔board marshalling)**: `bin/Code/Retro/Bridge.py`
  — stdlib-only FEN parser (`parse_fen`, `parse_piece_placement`); 0x88 square helpers
  (`sq88`, `sq88_to_file_rank`, `sq88_to_alg`, `alg_to_sq88`); `Bridge` class that
  writes FEN positions into the emulated piece-table struct (`write_position`), reads
  back the AI's chosen move from `AI_BEST_MOVE_ADDR` (`read_best_move`, `clear_best_move`),
  and configures player-type table (`set_computer_color`). All virtual addresses derived
  from A4=0x7FFE recon offsets. `tests/unit/retro/test_bridge.py` (19 tests, all
  `retro` marker, FakeCpu only). 88 retro tests passing, 1 xfail stub remaining (Think).
- **Retro Engine — Phase 5 (Traps + virtual clock)**: `bin/Code/Retro/Traps.py` —
  `VirtualClock` (deterministic tick counter, configurable 50 Hz PAL default, D4
  implementation) and `AmigaTraps` (Amiga exec/dos library stubs: AllocMem bump
  allocator from ALLOC_POOL 0x200000, OpenLibrary returning EXEC_BASE 0x800000,
  unknown/FreeMem returning 0; mem hook for AbsExecBase pointer at address 0x4;
  callbacks ignore the raw emulator arg and use `self._cpu` throughout — works
  with FakeCpu and Unicorn68k). `tests/unit/retro/test_traps.py` (18 tests, all
  `retro` marker, FakeCpu only).
- **Retro Engine — Phase 4 (CPU seam + FakeCpu)**: `bin/Code/Retro/Cpu.py` abstract
  base (8 methods, `HOOK_CODE`/`HOOK_MEM_READ`/`HOOK_MEM_WRITE`/`HOOK_MEM_INVALID`
  constants, zero Unicorn import). `bin/Code/Retro/Fakes.py` FakeCpu (scripted trace
  callback, 16 MB flat memory store, monotonic hook handles). `bin/Code/Retro/Cpus/`
  sub-package: `Availability.py` (unicorn probe + `require()`) and `Unicorn68k.py`
  (full Unicorn m68k wrapper — the ONLY file in Code.Retro permitted to import unicorn,
  N-RETRO-2; wraps D0–D7, A0–A7, PC, SP; wraps all four hook types; wraps `UcError`
  as `CpuError`). `tests/unit/retro/test_cpu.py` (12 `retro`-marked FakeCpu +
  availability tests; 5 `retro_emu`-marked Unicorn68k tests, skipped when unicorn
  absent). Total: 51 retro tests passing, 5 skipped, 2 xfail stubs remaining (Bridge,
  Think).
- **Retro Engine — Phase 3 (ROM manifest + containers)**: `bin/Code/Retro/Manifest.py`
  (load/validate/verify for `manifest.json`, streaming sha256, N-RETRO-6) and
  `bin/Code/Retro/Rom.py` (Amiga HUNK format parser; packer detection for
  PowerPacker/Imploder/XPK/LZX; `PackedBinaryError` on packed binaries; handles
  HUNK_CODE/DATA/BSS/RELOC32/SYMBOL/DEBUG). `tests/unit/retro/test_manifest.py`
  (9 tests) and `tests/unit/retro/test_rom.py` (11 tests) using synthetic HUNK
  containers; Phase-3 xfail stubs replaced with real implementations.
- **Retro Engine — Phase 2 (Foundations)**: `bin/Code/Base/CaissaErrors.py` promotes
  `CaissaError` to the repo-wide root (D1); `Code.Rpa.Errors` re-exports it for backward
  compat. `bin/Code/Retro/` package created with `Errors.py` (`RetroError` + 11 leaf
  classes) and `Types.py` (`MoveSpec`, `RomId`, `MemRegion`, `Level`, `ThinkResult`,
  `Platform` — zero third-party imports, N-RETRO-1). `tests/unit/retro/test_foundations.py`
  covers N-RETRO-1 through N-RETRO-5 (16 passing, 5 xfail stubs for Phases 3–7).
  `pytest.ini` gains `retro`, `retro_emu`, `retro_rom` markers; `ruff.toml` adds
  `bin/Code/Retro/**`, `tests/unit/retro/**`, `tools/caissa-retro` to include list;
  `Makefile` adds `cov-retro`, `test-retro-emu`, `test-retro-rom`, `retro-doctor` targets
  and extends `make test` to include the `retro` marker. `requirements-retro.txt` lists
  `unicorn` + `capstone`. `Resources/Retro/manifest.json` records the confirmed Amiga
  Dragon Inc crack (SHA256 `d4fc6137…`) with all 32 labelled offsets and the full
  globals/move-struct tables from Phase 1-B recon. Decisions D2 and D4 resolved:
  whole-binary headless emulation confirmed as the emulation strategy.
- **Retro Engine — Phase 0 (Documentation & Process)**: full SDD artefact set for
  the Retro Engine feature (`docs/features/retro-engine/`): `initial_idea.md` (FROZEN),
  `feature_spec.md` (Gate A satisfied), `feature_steps.md` (all test names for all
  10 phases, Phase 1–10 as `xfail(strict=True)` stubs), `implementation_plan.md`
  (Phase 0 + Phase 1 sessions in full; Phases 2–10 stubs), `decisions.md`. Product
  documentation in `docs/retro/`: `README.md`, `legal.md` (ROM / copyright policy),
  `rom-setup.md`, `uci-options.md`, `reverse-engineering.md`, `testing.md`,
  `troubleshooting.md`. Resource directory placeholders: `Resources/Retro/`,
  `Resources/Retro/Corpus/`. `.gitignore` updated to exclude `Resources/Retro/Fixtures/`
  and `UserData/Retro/` (user ROM and trace paths).
- **Fritz Polish — Phase 2 (Fixed window) — production code + verbs + tests**:
  - `bin/Code/Rpa/Driver.py` — six new `QtDriver` verbs: `window_info` (geometry + `fit_board`/`key_video`/`ui_mode` flags), `board_info` (ancho, `width_piece`, orientation), `resize_window`, `set_window_state`, `set_splitter_sizes` (registered name or objectName substring fallback for unregistered splitters such as `WFritzRightCol`), `click_tabbar` (bare `QTabBar` match for ribbon and notation strip).
  - `bin/Code/Debug/RemoteControl.py` — two-line dispatch delegations for all six verbs.
  - `tests/ui/rc_contract.json` — six new probes (four success-path for `window_info`/`board_info`/`resize_window`/`set_window_state`, two error-path for `set_splitter_sizes`/`click_tabbar`).
  - `tests/ui/test_fixed_window.py` — 15 T-FIX tests implemented (T-FIX-01..15): resize correctness, window unchanged on game start/end, board grows with window, min-size proof (G1), maximize/restore round-trip, fullscreen round-trip, `width_piece` never persisted by fit, splitter sizes applied, no `RuntimeError` on repeated mode cycling, `fit_board` flag active, stored `width_piece` stable across fits, window stable across game cycle, no BASEV entry from Fritz mode (`WBase.py:291` decoupling), `dispatch_size` path guarded.
- **Fritz Polish — Phase D (Documentation + process, Gate A)**: complete SDD artefact set in
  `docs/features/fritz-polish/` (`initial_idea.md`, `feature_spec.md`, `feature_steps.md`,
  `implementation_plan.md`). Design-time product docs in `docs/fritz/` (`README.md`,
  `concepts.md`, `glossary.md`, `decisions.md`, `design-approval.md`). Two new engineering
  standards: `docs/standards/ui-design-process.md` (PySide6-in-shipping-medium design loop,
  E1-E4 `qproperty-` contract, Qt escalation ladder, approval gate) and
  `docs/standards/architecture.md` (feature-package convention, purity tiers, AST purity test,
  strangler-fig scope limit, characterisation-test-first refactor procedure). `CLAUDE.md` gains
  Purity tiers subsection, two new standards in the summary, and a Development Commands section.
  `docs/modern-fritz.md` superseded via `git mv` to `docs/fritz/_modern-fritz-archived.md` with
  three drifted claims documented.

### Fixed
- **Mode toolbar escape hatch**: added `caissa:switch_mode` to `toolbar_inject` for Analyse, Coach, Compete, Just Play, and Train modes — every mode now has a one-click toolbar button to switch back to Classical or another mode
- **Coach mode theme pairing**: `coach.json` now sets `style: "Midnight"` and `icons: "MIDNIGHT"` as the plan specified

### Added
- **Claude working patterns docs**: `docs/claude_code/working-patterns.md` (cross-project
  patterns mined from 3,786 prompts / 89 sessions), `docs/claude_code/prompt-library.md`
  (13 project-agnostic prompt templates), `docs/claude_code/session-archaeology.md`
  (GDrive backup runbook and corpus recovery guide), `docs/claude_code/claude-md-snippet.md`
  (portable CLAUDE.md rules block), `tools/claude_mine.py` (reusable transcript miner).
- **RPA layer — Phase 9 (Production Readiness)**: Gate E production readiness review with
  all findings tracked to resolution. `tests/unit/rpa/test_completeness.py` — 5 structural
  tests: `test_no_pyside6_import_outside_allowlist` (AST walker enforcing N-RPA-2),
  `test_every_public_callable_in_rpa_has_docstring`, `test_cv2_absent_from_sys_modules_after_plain_start`,
  `test_rpa_timeout_below_pytest_timeout`, `test_every_planned_test_name_exists_in_suite`.
  N-RPA-2 violation in `Resolve._image_candidates` fixed: `load_template()` added to
  `Vision/Template.py` (cv2-only, no Qt). Gate H docs: `docs/rpa/user-guide.md`,
  `docs/rpa/troubleshooting.md`, `docs/rpa/operations.md`.
  Gate E artefact: `docs/features/rpa-layer/production_readiness.md`.
- **RPA layer — Phase 8 (Workflows + Regression Suite)**: `bin/Code/Rpa/Workflows/` —
  `Registry.py` (`register`, `get`, `all_names`); four built-in workflows:
  `smoke_home` (converge + assert HOME), `classical_invariant` (assert toolbar;
  open/close Config), `play_a_game` (trigger new game; assert PLAYING), and
  `config_roundtrip` (open config; write player name; accept; reopen; verify).
  `Service.py` updated to delegate `_WORKFLOW_REGISTRY` to `Workflows.Registry`
  and load built-ins on init. 6 unit tests in `tests/unit/rpa/test_workflows.py`;
  4 integration stubs in `tests/ui/test_rpa_workflows.py` (`rpa_ui`).
  Gate H docs: `docs/rpa/authoring-workflows.md`, `docs/rpa/testing.md`.
- **RPA layer — Phase 7 (Vision)**: `bin/Code/Rpa/Vision/` — `Availability.probe()`
  (cached capability probe, never raises), `Capture.grab()` (QWidget → Screenshot with
  `bytesPerLine()` padding fix and RGB channel order), `Screenshot.logical()` (DPR-1
  resize via `INTER_AREA`), `Template.find_all()` (TM_CCOEFF_NORMED + NMS at IoU 0.3 +
  multi-scale fallback `[0.95, 1.05, 0.90, 1.10]`), `Ocr.find_phrase()` (line-grouped
  multi-word phrase matching, 2× INTER_CUBIC pre-processing), `Manifest.load_and_verify()`
  (sha256 check). Image and OCR tiers wired into `TargetResolver`; `Snapshot` gains optional
  `screenshot` field; `QtDriver.snapshot()` captures lazily when cv2 is available.
  Empty `Resources/Rpa/Templates/manifest.json` scaffolded. `rpa_cv` conftest skip hook
  added (skips on offscreen or missing cv2). 11 tests in `tests/unit/rpa/test_vision.py`
  (2 always-run, 9 `rpa_cv` marked). Gate H doc: `docs/rpa/vision.md`.
- **RPA layer — Phase 6 (service + rpa_* verbs + client/CLI)**: `bin/Code/Rpa/Service.py` —
  `RpaService` with run registry, 10 `rpa_*` verb handlers (`rpa_capabilities`,
  `rpa_state`, `rpa_find`, `rpa_run`, `rpa_status`, `rpa_journal`, `rpa_cancel`,
  `rpa_converge`, `rpa_act`, `rpa_workflows`), `generate_run_id()`, and `_start_pump=False`
  for unit-test mode. `RemoteControl.py` updated with lazy `_rpa()` accessor, `CAISSA_RPA=0`
  kill switch, and single `rpa_*` dispatch block. `tests/ui/rpa_client.py` — `CaissaRpaClient`
  with `run_and_wait()` polling every 250 ms. `tools/caissa-rpa` — CLI with `run`, `status`,
  `journal`, `find`, `cancel`, `workflows`, `doctor` subcommands. 25 unit tests in
  `tests/unit/rpa/test_service.py`. `tests/ui/test_rpa_service.py` — integration test stubs
  (`rpa_ui` marker). Gate H docs: `docs/rpa/wire-protocol.md`, `docs/rpa/cli.md`,
  `docs/rpa/quickstart.md`.

- **RPA layer — Phase 5 (runner + journal + activities)**: The step-pumped closed-loop state
  machine. `bin/Code/Rpa/Runner.py` — 14-sub-state machine (`SubState` enum), `RunStatus`
  enum (PENDING/RUNNING/CANCELLING/SUCCEEDED/FAILED/CANCELLED/TIMED_OUT), `Frame` dataclass
  for the frame stack, `Runner` with `pump() → bool` and cooperative `cancel()`.
  Three deadlines: run (90 000 ms), step-verify (5 000 ms), converge budget (12 transitions).
  Backoff: `200×2^(n-1)` capped at 3 000 ms with ±10 % jitter from `random.Random(run_id)`.
  RetryScope frames detected in `DECIDE_RECOVERY` before entering UNWIND.
  `bin/Code/Rpa/Journal.py` — `StepRecord` and `RunRecord` dataclasses with JSON persistence
  and bounded 500-entry sub-state trace. `bin/Code/Rpa/Activities.py` — `Activity` base
  class and 11 concrete activities (Click, TypeInto, SelectItem, GetText, ElementExists,
  TakeScreenshot, OpenConfig, CloseDialog, SwitchTab, Sequence, RetryScope).
  30 unit tests in `tests/unit/rpa/test_runner.py` (2 xfail for Phase 6).
  `docs/rpa/activities.md` and `docs/rpa/state-machine.md` updated with verified traces.

- **RPA layer — Phase 4 (state model)**: `bin/Code/Rpa/AppState.py` — 8 state constants,
  dialog-first `recognise(snapshot)`, `Transition` frozen dataclass, `TRANSITION_TABLE`
  (9 transitions with force_cancel edges at min_settle_ms >= 600), `StateGraph` with
  Dijkstra `plan()` and `reachable_from()`, module-level `DEFAULT_GRAPH`. 29 unit tests
  in `tests/unit/rpa/test_appstate.py`. `docs/rpa/states.md` finalised against code.

- **RPA layer — Phase 3 (targets + object resolver)**: `bin/Code/Rpa/Targets.py` —
  `Selector` (9 fields, two wire forms: JSON + compact string, `SelectorError` on missing
  discriminating field) and `Target` (selector + anchor/direction/distance/timeout).
  `bin/Code/Rpa/Resolve.py` — `TargetResolver` with object-tier confidence table
  (exact object_name=1.00, exact text=0.95, substring=0.80, class-only=0.60), anchor
  filtering by direction and distance, `AmbiguousMatchError` on ties, image/OCR tier
  stubs raising `VisionUnavailableError` (Phase 7). 31 unit tests in
  `tests/unit/rpa/test_targets.py`, all passing.

- **RPA layer — Phase 0 (documentation & process)**: SDD/TDD artefacts and product
  documentation foundation for the Caissa closed-loop automation engine. Includes:
  - `docs/process/sdd-workflow.md` — the SDD/TDD routine with 8-gate checklist
  - `docs/templates/` — Caissa-adapted SDD artefact templates (no-ABC variants)
  - `docs/claude_code/prompts.md` — 11-prompt library for the SDD workflow
  - `docs/features/rpa-layer/` — frozen initial idea, full R/I/P/Q/N feature spec,
    phase tracker with all test names, and session implementation plan
  - `docs/rpa/` — product documentation (design-time subset): state machine formal
    spec, concepts, UiPath mapping, app states, glossary, decisions (D1–D12)
  - Standards amendments: feature-directory convention in `spec-driven-development.md`;
    `typing.Protocol` clarification in `coding-standards.md`; `CaissaError` location in
    `error-handling.md`; CV amendment (§7.1) and stale reference fix in `ui-testing.md`
  - `CLAUDE.md` updated with `rpa` scope, `bin/Code/Rpa/` tree, and process pointers

- **RPA layer — Phase 2-B (driver seam)**: `bin/Code/Rpa/Driver.py` — `Driver` plain base +
  `QtDriver` (all 20+ Qt helpers extracted from `RemoteControl`; only class permitted to
  import PySide6 in `Code.Rpa`). `bin/Code/Rpa/Fakes.py` — `FakeDriver`, `FakeClock`, and
  `World` dataclass for deterministic no-Qt unit testing and `dry_run` support (D1).
  `RemoteControl` reduced to dispatch-only; all helper bodies moved verbatim into `QtDriver`
  (including `force_cancel` with its use-after-free safety comments). `_dlog` replaced by
  `logger.debug`; `faulthandler` gated on `CAISSA_RPA_FAULTHANDLER=1`. 24/24 contract
  assertions pass against the refactored binary — zero behaviour change.

- **RPA layer — Phase 2-A (contract lock)**: Wire contract for `RemoteControl` recorded
  before the Phase-2 refactor — `tests/ui/rc_contract.json` (25-verb golden key sets) +
  `tests/ui/test_rc_contract.py` (24 parametrised / sequential assertions). Tests skip
  automatically when no live app is reachable.

- **RPA layer — Phase 1 (foundations)**: Infrastructure for the Caissa RPA engine:
  - `bin/Code/Rpa/Errors.py` — `CaissaError` (repo-wide base), `RpaError` domain base,
    and 15 specific exception classes with RST docstrings
  - `bin/Code/Rpa/Types.py` — `Rect`, `ElementRef`, `Snapshot` frozen dataclasses
    with zero third-party imports (N-RPA-1)
  - `bin/Code/Main/LogSetup.py` — single-call app logging configuration;
    reads `CAISSA_LOG_LEVEL`; no-op if called again
  - `ruff.toml` at repo root — Caissa-scoped lint config with `select = ["E","W","F","I","UP"]`;
    E722 enforced; `--config ruff.toml` required in Makefile (D11)
  - `Makefile` — `test`, `test-all`, `cov`, `test-ui`, `test-cv`, `lint`, `docs`, `rpa-doctor`
    targets; venv resolved via `git rev-parse --git-common-dir`
  - `requirements-rpa.txt` / `requirements-dev.txt` — optional vision deps split from base
  - `pytest.ini` — `rpa`, `rpa_ui`, `rpa_cv` markers added; D12 comment
  - `tests/unit/rpa/test_foundations.py` — 13 passing tests + 87 `xfail(strict=True)` stubs
    covering all future phases (Phase 9's completeness gate anchors here)
  - `docs/conf.py` — Sphinx autodoc config for `make docs → docs/rpa/api/`
  - Marker discipline applied: `pytestmark = pytest.mark.unit` / `.ui` added to all
    existing test files; `test_every_collected_test_has_exactly_one_suite_marker` enforces it
  - `tests/conftest.py` bootstrap made lazy — pure unit tests no longer trigger Qt bootstrap

- **Win95 Fritz retro skin**: Windows 95-style 3D bevel theme — raised/inset `outset`/`inset` borders, `#c0c0c0` system grey, navy (`#000080`) selection, zero `border-radius`, chunky 16px scrollbars
- **DOS Fritz retro skin**: CGA terminal theme — amber-on-black (`#ffb000` on `#000000`), hard 1px borders, invert-on-hover buttons, `#0000aa` CGA-blue selection, VSCode icon pack for minimal look
- **Modern Fritz — one-screen layout fix** (`feat/modern-fritz-layout`, PR #6)
  - `WFritzPlayerHeader`: Fritz-style player info strip (black player top, white bottom)
    polling `WBase.lb_player_*` / `lb_clock_*` at 500 ms; fixed 60 px height; Fritz blue
    clock colour; shown as the topmost pane of the Fritz right column during play
  - `modern_fritz_ui._swap_home_to_analysis`: complete rewrite — reparents `mw.base.pgn`
    (the actual game move list) into Fritz right column as the bottom pane; collapses
    WBase's internal right-panel widgets (player labels, clocks, rotulos, captures) to
    zero size so the board fills WBase; stores (layout, index) for full restoration on
    exit; Fritz right column becomes [WFritzPlayerHeader, WFritzAnalysisTable,
    WFritzEvalGraph, pgn] — a genuine Fritz-like one-screen arrangement
  - `modern_fritz_ui.on_mode_exit`: restores `mw.base.pgn` to its exact layout position
    in WBase, restores all widget size constraints, calls `show_replay()` — Classical
    mode renders identically to upstream after switching back
  - `_find_widget_in_layout(top_layout, target)`: recursive layout-tree search helper
    returning (layout, index) for a widget's direct container
  - `tests/ui/test_fritz_layout.py`: five Fritz-specific e2e tests (T-FRITZ-01–05)
    covering home panel width, in-game panel sizes, player header visibility, toolbar
    Fritz-style assertion, and mode-exit restoration

- **Modern Fritz — Stage 1: visual overhaul** (`feat/modern-fritz-layout`, PR #6)
  - `WFritzAnalysisTable`: proper multi-PV engine analysis table — up to 5 lines,
    each showing rank, score (Fritz blue/red), depth, and principal variation;
    `+`/`−` buttons control the number of visible PV lines; polls `analysis_bar.mrm`
    at 250 ms; replaces the old single-line `WFritzEnginePanel`
  - `WFritzHome`: Fritz-style home/landing panel shown on mode entry — three
    action buttons (New Game, Load Game, Enter & Analyze); swaps itself out for
    the analysis table when an action is chosen, giving the "one-screen" Fritz feel
    without requiring a popup dialog to start playing
  - `modern_fritz_ui.on_mode_enter`: shows `WFritzHome` first; connects
    `action_chosen` signal to swap in `WFritzAnalysisTable` then dispatch the
    action through the existing menu handlers (no new game-start logic)
  - `caissa:fritz_level` action (`fritz_level.py`): toolbar "Level" button that
    opens the Fritz level/time-control picker and restarts the game with new
    settings — no menu navigation required
  - `modern-fritz.json` toolbar allowlist: restricted to Fritz-relevant keys
    (resign, draw, takeback, new game, pause, config, utilities + home-screen
    keys); `TB_ADJOURN` removed; both `caissa:fritz_level` and
    `caissa:switch_mode` injected at toolbar start
  - `WFritzEvalGraph`: 80 px fixed-height evaluation profile graph — QPainter bar
    chart, Fritz-blue bars for white advantage, red for black, ±600 cp scale; polls
    `AnalysisBar.mrm` at 250 ms and accumulates one centipawn value per half-move;
    trims on backward navigation; inserted between analysis table and move list
  - `WFritzNewGame`: Fritz-style simplified game-start dialog — three toggle-button
    rows (Side: White/Black/Random, Level: Easy/Club/Active/Strong/Master/
    Grandmaster, Time: No limit/Blitz/Rapid/Classical); builds a complete
    `dic_var` and calls `ManagerPlayAgainstEngine.start()` directly, bypassing
    the full Play-Against-Engine popup entirely
  - `modern_fritz_ui._fritz_new_game`: helper that shows `WFritzNewGame` and starts
    the game directly — no ConfigurationsPAE round-trip, no Shortcuts indirection
  - `Modern Fritz.qss` / `.colors`: palette shifted from near-black (`#161616`) to
    Fritz medium-grey (`#252526` bg, `#2d2d2d` surface, `#3c3c3c` surface-2,
    `#505050` border, `#d4d4d4` text) — 98 colour values updated; Q1/Q2/Q3 checks
    pass clean; `BOARD_STATIC` preserved dark
  - Move quality colour coding in the PGN notation panel (Stage 5): Fritz-palette
    background tints for NAG-annotated moves — green shades for good/brilliant (!,
    !!), teal for interesting (!?), amber for dubious (?!), orange for mistake (?),
    red for blunder (??); monkey-patched onto the WBase instance at mode entry
    (`grid_color_fondo` + `ControlGrid.siColorFondo = True`) and fully removed on
    mode exit; NAG data requires Tutor/rating display to be active during play
  - Right-column layout: vertical `QSplitter` — home/analysis panel above
    `pgn_information` (move list); `on_mode_exit` restores `pgn_information` to the
    main splitter before cleanup
  - `UIModes.load_mode_hook`: normalise mode name to filename (spaces and hyphens →
    underscores; `"Modern Fritz"` → `modern_fritz_ui.py`)

- **Modern Fritz retro skin** (`feat/modern-fritz`, PR #5)
  - `Resources/Styles/Modern Fritz.qss` / `Modern Fritz.colors`: dark navy + Fritz-blue
    accent (`#1976d2`); 728-line QSS derived from Midnight with identical geometry
  - `Resources/Modes/modern-fritz.json`: full Classical feature set, pins `style` and
    `icons` so the Fritz look is automatic when the mode is selected
  - `docs/modern-fritz.md`: SDD covering palette, file roles, and authoring-rule compliance
  - `InitApp.init_app_style`: reads `active_mode().get("style")` and uses the mode-pinned
    QSS for the session (user's `x_style_mode` preference is preserved)
  - `InitApp.apply_live_style`: resolves `active_mode().get("icons")` as an `Icons` class
    attribute to allow mode-pinned icon pack without touching user preference
- **Theme overlay system — Steps 5–8** (`feat/overlay-steps-5-8`, PR #3)
  - `config_section` key in mode JSON: active mode can append a mode-owned tab
    (combobox/checkbox/spinbox/edit fields) to the General Configuration dialog
  - `configuration.mode_settings` dict: namespace-keyed storage persisted in the
    config pickle under `MODE_SETTINGS`; backwards-compatible (old pickles default `{}`)
  - `UIModes.load_mode_hook(mode_name)`: loads `actions/<mode>_ui.py` if present;
    `WindowConfig` calls `hook.patch_config_form(form, conf, overlay)` before `run()`
  - 27 classical-invariant unit tests in `tests/test_classical_invariant.py`
    (no Qt/display; run with `pytest tests/test_classical_invariant.py`)
  - Result unpack in `WindowConfig.options()` changed to index-based so an extra
    mode-section tab can never corrupt existing tab positions

- **UI integration testing framework** (`feat/ui-testing-framework`, PR #2)
  - `tests/ui/client.py`: `CaissaClient` wrapping the RemoteControl Unix socket;
    typed assertion helpers (`assert_dialog_field`, `assert_tab_exists`, etc.)
  - `tests/ui/conftest.py`: session-scoped `caissa_proc` + `client` fixtures;
    function-scoped `config_theme` fixture with automatic teardown restore
  - `tests/ui/test_overlay.py`: T-OVL-01–08 (Caissa theme label renames,
    hidden fields, tab renames, player-name round-trip)
  - `tests/ui/test_classical.py`: T-CLS-01–02 (classical invariant via live app)
  - `pytest.ini` with testpaths, markers, timeout config
  - `CAISSA_TEST=1` env-var guard in `Procesador.py` suppresses startup dialogs
    (update check, startup puzzles, first-time config) so tests reach home screen

- **Theme UI overlay system — Layer 1** (`feat/overlay-system`, PR #1)
  - `bin/Code/Config/FormOverlay.py`: `OverlayForm` proxy wrapping `FormLayout`;
    intercepts field builds to rename/hide labels; `result()` for safe named-field lookup
  - `load_overlay(theme_name)` reads `Resources/Styles/<name>.ui.json`; returns `{}`
    if absent (classical invariant preserved)
  - `Resources/Styles/Caissa.ui.json`: renames Mode→Theme, UI mode→Mode; hides
    Window style / Menu Play / Preventing system crashes; renames 5 tabs
  - `WindowConfig.options()` wrapped with `OverlayForm`; named-field unpack replaces
    fragile positional `*_ui_mode_rest` approach
  - `docs/ui-testing.md`: SDD for the UI testing framework
  - `docs/theme-mode-system.md`: SDD for the full Theme/Mode overlay architecture

- **Engineering standards and tooling**
  - `CLAUDE.md`: project guide with repo structure, key concepts, workflow rules
  - `docs/standards/coding-standards.md`: branch+PR workflow, commit message format,
    protected `main`, auto-merge policy
  - `docs/standards/spec-driven-development.md`: SDD-first requirement
  - `docs/standards/docstring-standards.md`: RST/Sphinx style
  - `docs/standards/error-handling.md`: domain exceptions, exc_info, raise-from
  - `docs/standards/logging-standard.md`: `%s`-style lazy formatting

- **RemoteControl commands** (`bin/Code/Debug/RemoteControl.py`)
  - `set_config <key> <value>`: sets a config attribute, saves, re-applies QSS
  - `open_config`: opens General Configuration dialog asynchronously via
    `QTimer.singleShot(0, proc.menu_options)`
  - Tests for both commands in `tests/test_remote_control.py`

### Fixed
- `RemoteControl._open_config` called `proc.opciones()` (non-existent); corrected
  to `proc.menu_options()`

---

## [Pre-release work — no version tag yet]

The sections below document work completed before the formal PR/branch workflow
was established (commits `7a657d4`…`991c2c7` on `main`).

### Added — Coach mode and UI Modes framework (Phase 5–7)

- **UI Modes framework** (`00ab3b8`)
  - `Resources/Modes/*.json`: mode definitions with `toolbar`, `menu_keys`,
    `toolbar_inject` allowlists
  - `bin/Code/UIModes/UIModes.py`: `load_modes()`, `active_mode()`,
    `allows_toolbar()`, `filter_menu_options()`, `toolbar_inject()`
  - `bin/Code/Menus/BaseMenu.py`: `filter_menu_options` called from `check_pending()`
  - `bin/Code/Main/WBase.py`: `pon_toolbar` applies toolbar filter + injects
    mode-defined actions
  - `Configuration.x_ui_mode`: new config key; added to `needs_reinit`
  - `WindowConfig.options()`: Mode combobox from `Resources/Modes/*.json` scan
  - `tools/dump_ui_keys.py`: introspects all menus + toolbar keys; outputs
    `tools/ui-keys.md`

- **Four focused modes** (`00ab3b8`)
  - `Resources/Modes/classical.json`: null allowlists — full upstream experience
  - `Resources/Modes/just-play.json`: board + clock only
  - `Resources/Modes/analyse.json`: engine output + PGN tree
  - `Resources/Modes/train.json`: tactics + Leitner + openings
  - `Resources/Modes/compete.json`: Elo ladders + tournaments
  - All modes include `TB_OPTIONS` so Configuration is always reachable (`991c2c7`)

- **Coach mode landing screen** (`245ec16`)
  - `bin/Code/UIModes/actions/coach_home.py`: 2×2 card grid (Play · Openings ·
    Review · Daily puzzle), registered as `caissa:coach_home`
  - `Resources/Modes/coach.json`: Coach mode JSON with `toolbar_inject`
  - `bin/Code/UIModes/actions/switch_mode.py`: `caissa:switch_mode` escape hatch
    present in every mode's toolbar

### Added — Caissa theme and icon system

- **Caissa/VSCode signature theme** (`9519c47`, `f8a035d` and refinements)
  - `Resources/Styles/Caissa.qss` / `Caissa.colors`: dark VS Code–inspired chrome,
    activity-bar sidebar, accent `#6366f1`, rounded corners, slim scrollbars
  - `Resources/Styles/VSCode.qss` (deprecated name, now Caissa)
  - Board colours matched to VS Code charcoal `#1e1e1e`
  - Balestegui2 piece set used as default (`3a6d8b0`)
  - Sidebar gap, separator lines, and wrench icon removed (`718de27`)

- **VS Code icon pack** (`4f961a1`, `27efbbb`, `b5c1ca6`)
  - 52 SVG overrides for home-screen and game-screen toolbar icons
  - Custom codicons-style toolbar icons matching the VS Code aesthetic
  - Adjourn icon normalised; sidebar icon consistency test suite added (`46afb7d`)
  - Stroke weights tuned to visual parity between home and play screens

- **Midnight and Daylight themes** (`94f106d`)
  - `Resources/Styles/Midnight.qss` / `Midnight.colors`
  - `Resources/Styles/Daylight.qss` / `Daylight.colors`
  - Shared 8px radius, 10px padding; identical geometry between dark and light
  - Palette covers: QScrollBar, QLineEdit, QSpinBox, QTextEdit, QProgressBar, tabs,
    headers, focus ring, selection highlight

- **Midnight/Daylight icon packs** (`5e2a6d8`)
  - `Resources/IntFiles/Iconos_midnight.*`, `Iconos_daylight.*`
  - Duotone recolour using `haz_sepia` pipeline; exclusion sets for semantic colours
    (Leitner boxes, Everest decorative, status LEDs)
  - `IconosBase.MIDNIGHT = 3`, `DAYLIGHT = 4` registered in `dic_files`

- **IS_DARK QPalette and CHROME_* colour keys** (`fd3e12f`)
  - `IS_DARK` flag in `.colors` files drives a full `QPalette` in `init_app_style`
  - 10 new `CHROME_*` keys (`CHROME_SURFACE`, `CHROME_ACCENT`, etc.) in all themes
  - Inline `setStyleSheet` calls for most-visible chrome sites routed through
    `Code.dic_colors`

- **Live retheme without restart** (`b4e4127`, `f8a035d`)
  - `InitApp.apply_live_style()`: re-applies QSS + palette immediately on config save
  - Icon pack change still requires restart; all other style changes are instant
  - RemoteControl `theme <name>` command applies theme atomically

### Added — macOS platform and foundation (Phase 0)

- **Apple Silicon native platform** (`36be1a3`)
  - `bin/OS/darwin/OSEngines.py`: native engine registry for arm64
  - Native engines committed to LFS: Stockfish 18 (0.5 MB + shared NNUE nets),
    Lc0 0.32.1 (1.8 MB), irina (92 KB), 10× Maia nets + books
  - `bin/OS/darwin/FasterCode.cpython-313-darwin.so`: arm64 C extension
  - `bin/OS/darwin/uci_options.sqlite`
  - All absolute Homebrew symlinks replaced with real relocatable binaries

- **macOS toolchain** (`02c3413`)
  - `tools/caissa`: main launcher (venv + `CAISSA_TEST` support)
  - `tools/caissa-ctl`: RemoteControl CLI client
  - `tools/lc-engine`: Docker bridge shim for Linux engine wrappers
  - `tools/gen_darwin_engines.py`: generates relocatable wrapper scripts
  - `tools/build_stockfish.sh`, `build_lc0.sh`, `build_irina.sh`,
    `build_drawfish.sh`: reproducible source builds

- **Docker optional / native Drawfish** (`4ae71bd`)
  - `OSEngines.py` availability probe: single `docker inspect` with 2 s timeout;
    skips bridged loop entirely when Docker is absent or stopped
  - Native `bin/OS/darwin/Engines/drawfish/drawfish` (arm64, no NNUE)
  - Relocatable wrapper generation: `REPO=$(cd … && pwd)` self-location
  - `eguzkilore` removed from native keys (was registering an ELF x86-64 binary
    as native arm64)
  - `Configuration.path_book` guarded against missing alias (unguarded dict lookup
    was taking down the Play against engine dialog)

- **Rename to Caissa** (`68afb07`)
  - `Code.lucas_chess` → `"Caissa"` (single assignment in `Translate.py`)
  - `VERSION = "1.0"`, `UPSTREAM_VERSION = "R 6.0.4"` (provenance preserved)
  - Auto-updater disabled: menu entry removed, `Update.update()` / `update_at_start()`
    short-circuited; `update_manual()` (local ZIP install) preserved
  - GPL §5(a) attribution in About dialog
  - `README.md`: platform (Apple Silicon, macOS 14+) stated in first screenful,
    badge row, requirements, install, engine roster, credits
  - `LucasChess.command` → `Caissa.command`; `tools/lucaschess` → `tools/caissa`

- **Stockfish NNUE repair** (`fe58582`)
  - LFS stub `.nnue` files caused Stockfish exit code 1 after first `go` command
  - Fixed by ensuring full LFS checkout of both NNUE files

### Added — Testing infrastructure

- **RemoteControl Unix socket server** (`f8a035d` and many subsequent commits)
  - `bin/Code/Debug/RemoteControl.py`: Qt-safe command dispatcher over
    `/tmp/caissa-control.sock`; 30+ commands covering ping, info, screenshot,
    toolbar, game control, UI inspection/interaction, dialog control
  - `tools/caissa-ctl`: CLI wrapper for manual use and debugging
  - `tests/test_remote_control.py`: live-app tests (23+ assertions); requires
    running Caissa process; auto-skips if socket absent

- **Sidebar icon consistency test suite** (`46afb7d`)
  - `tests/test_sidebar_icon_consistency.py`: asserts all sidebar icons render
    at consistent visual weight and size

### Fixed

- `dialog_cancel` was closing the main window instead of the topmost dialog
  (`9874f12`); all 23 RemoteControl tests green after fix
- Toolbar square-button enforcement: `abca1e7` fixed vertical icon-only toolbar
  to use 48×48 px buttons consistently
- Game toolbar draw icon and duplicate gears resolved (`d30be61`)

---

## [Upstream] — Lucas Chess R6.0.4

Base from which Caissa was forked. See
[lukasmonk/lucaschessR6](https://github.com/lukasmonk/lucaschessR6) for full
upstream history.
