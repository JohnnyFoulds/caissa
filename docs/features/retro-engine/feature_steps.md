# Retro Engine — Implementation Steps

Living implementation tracker for the Retro Engine feature. Updated after each phase
is completed.

**Spec reference:** [feature_spec.md](feature_spec.md)

---

## Phase 11 — Fidelity Goals (A–D) 🔄

**Goals:** BR-2 bit-exact, FR-6 level fidelity, FR-7 EmuClockRate functional, FR-10 corpus regression net

### Phase A — TC mechanism fix + outer driver + EmuClockRate correction 🔄

**Branch:** `feat/retro-outer-driver`  
**Status:** In progress

**Root cause:** The TC hook at 0x008A immediately redirected PC → sentinel when a valid move was
found, capturing a mid-depth partial result. The fix is to start at AI_OUTER_DRIVER_ADDR (0x81DC),
count TC firings, set the abort flag after the configured threshold, and return normally — letting
the outer driver exit after a complete depth pass.

**Files changed:** `bin/Code/Retro/Think.py`, `bin/Code/Retro/Uci.py`,
`tests/unit/retro/test_think.py`, `tests/unit/retro/test_uci.py`

**Gate D (run for real):**
```bash
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro
# Must produce a move in {e7e5, c7c5, e7e6, c7c6, d7d5} — NOT h7h5 and NOT 0000
```

### Phase B — Live RPA comparison + level calibration ⬜

**Branch:** `feat/retro-live-compare`  
See plan for full description.

### Phase C — Full-game end-to-end ⬜

**Branch:** `feat/retro-full-game`

### Phase D — Speed measurement + EmuClockRate wiring ⬜

**Branch:** `feat/retro-clock-rate`

---

## Status Legend

⬜ Not started / 🔄 In progress / ✅ Complete

---

## Phase 0 — Documentation & Process ✅

**Branch:** `docs/retro-engine`  
**Files:**
- `docs/features/retro-engine/initial_idea.md` (create — FROZEN at scope-lock)
- `docs/features/retro-engine/feature_spec.md` (create — Gate A)
- `docs/features/retro-engine/feature_steps.md` (create — this file)
- `docs/features/retro-engine/implementation_plan.md` (create — Phase 0+1 detail)
- `docs/features/retro-engine/decisions.md` (create)
- `docs/retro/README.md` (create)
- `docs/retro/legal.md` (create — copyright policy)
- `docs/retro/rom-setup.md` (create)
- `docs/retro/uci-options.md` (create)
- `docs/retro/reverse-engineering.md` (create — Phase 1 guide)
- `docs/retro/testing.md` (create)
- `docs/retro/troubleshooting.md` (create)
- `Resources/Retro/.gitkeep` (create — directory placeholder)
- `Resources/Retro/Corpus/.gitkeep` (create)
- `.gitignore` (edit — add `Resources/Retro/Fixtures/`, `UserData/Retro/`)

**What we deliver:**
- All SDD artefacts, Gate A satisfied
- Legal policy documented in `docs/retro/legal.md`
- Phase 1 guide so the spike is methodical
- All Phase 1–10 test names listed below as `xfail(strict=True)` stubs (placeholder file)

**Test names (all `xfail(strict=True)` until owning phase lands):**

*Phase 2 — Foundations (`tests/unit/retro/test_foundations.py`):*
- `test_types_module_has_no_third_party_imports` — ast-parse Types.py; assert no non-stdlib import (N-RETRO-1)
- `test_errors_module_has_no_third_party_imports` — ast-parse Errors.py (N-RETRO-1)
- `test_all_retro_error_types_are_retro_error_subclasses` — walk Errors module; assert all Exception subclasses descend from RetroError
- `test_caissa_error_is_a_single_class_object` — assert Code.Retro.Errors.RetroError.__bases__ contains CaissaError and CaissaError has no duplicate definition
- `test_no_pyside6_import_anywhere_in_retro` — ast-scan every .py under bin/Code/Retro/ (N-RETRO-5)
- `test_ruff_include_covers_retro_paths` — read ruff.toml; assert bin/Code/Retro/** is listed (N-RETRO-14 analogue)
- `test_makefile_has_retro_targets` — read Makefile; assert cov-retro, test-retro-emu, test-retro-rom, retro-doctor targets exist
- `test_pytest_ini_declares_retro_markers` — read pytest.ini; assert retro, retro_emu, retro_rom markers declared

*Phase 3 — ROM manifest + containers (`tests/unit/retro/test_rom.py`):*
- `test_manifest_json_schema_validates` — load manifest.json; assert required fields present (N-RETRO-6)
- `test_manifest_entry_sha256_is_64_hex_chars` — each entry's sha256 field (N-RETRO-6)
- `test_manifest_entry_has_think_entry_offset` — each entry has think_entry integer field
- `test_no_tracked_file_matches_manifest_hash` — hash all git-tracked files; assert none in manifest (N-RETRO-4)
- `test_no_resources_retro_file_exceeds_size_cap` — no file in Resources/Retro/ exceeds 512 KB (N-RETRO-4)
- `test_rom_not_found_raises_rom_not_found_error` — pass a nonexistent path; assert RomNotFoundError
- `test_rom_hash_mismatch_raises_rom_hash_mismatch_error` — pass a zero-byte file; assert RomHashMismatchError with computed hash in message
- `test_amiga_hunk_synthetic_rom_loads` — build synthetic hunk via Fakes.build_synthetic_hunk(); assert MemoryImage with correct entry
- `test_amiga_hunk_relocation_applied` — build hunk with a reloc32 table; assert addresses adjusted
- `test_amiga_hunk_bss_section_zeroed` — build hunk with BSS; assert region data is zeroes
- `test_detect_packer_returns_none_for_plain_binary` — a fresh MemoryImage; assert None
- `test_detect_packer_recognises_powerpacker_header` — synthetic PP20 header; assert "powerpacker"
- `test_dos_mz_raises_unsupported_target_error` — Phase 9 not yet implemented
- `test_manifest_entries_gitignore_check` — Resources/Retro/Fixtures is in .gitignore

*Phase 4 — CPU seam + FakeCpu (`tests/unit/retro/test_cpu.py`):*
- `test_scripted_cpu_replays_memory_reads` — ScriptedCpu returns scripted bytes on read()
- `test_scripted_cpu_replays_register_values` — ScriptedCpu returns scripted register values
- `test_scripted_cpu_run_returns_scripted_result` — ScriptedCpu returns scripted RunResult
- `test_scripted_cpu_records_writes` — ScriptedCpu records write() calls for assertion
- `test_unicorn_import_only_in_cpus_subpackage` — ast-scan; unicorn import not in any other module (N-RETRO-2)
- `test_importing_code_retro_does_not_pull_unicorn` — subprocess fresh import; assert unicorn absent from sys.modules (N-RETRO-3)
- `[retro_emu] test_unicorn68k_loads_synthetic_hunk` — load a 6-byte hunk (NOP + RTS); assert run completes
- `[retro_emu] test_unicorn68k_register_roundtrip` — set D0; run nop; read D0; assert equal
- `[retro_emu] test_unicorn68k_memory_fault_raises_emulation_fault_error` — write to unmapped addr
- `[retro_emu] test_unicorn68k_instruction_budget_raises_budget_error` — budget=1, nop loop
- `[retro_emu] test_unicorn68k_and_x86_share_cpu_seam` — parameterised: same Cpu test over both archs with matching synthetic programs

*Phase 5 — Traps + virtual clock (`tests/unit/retro/test_traps.py`, `test_clock.py`):*
- `test_trap_registered_handler_is_called` — register a handler; assert called on address hit
- `test_unknown_trap_raises_trap_unhandled_error` — jump to unregistered trap address (N-RETRO-10)
- `test_every_profile_trap_has_a_handler` — for each profile, assert every trap entry has a registered handler
- `test_virtual_clock_is_deterministic` — same instruction count → same tick value across 10 resets
- `test_virtual_clock_rate_scales_linearly` — rate=200 gives 2× ticks at same instruction count
- `test_strict_original_rejects_non_default_clock_rate` — EmuStrictOriginal=True, rate=50; assert RetroConfigError (N-RETRO-12)
- `[retro_emu] test_traps_intercept_timer_read_in_synthetic_program` — synthetic prog polls trap addr; assert handler called N times

*Phase 6 — Board bridge (`tests/unit/retro/test_bridge.py`):*
- `test_startpos_encodes_to_expected_struct_bytes` — encode start position; compare to hand-computed expected bytes
- `test_arbitrary_position_encodes_and_decodes_to_same_fen` — property test over legal positions reachable from startpos
- `test_move_decode_returns_legal_uci_string` — decode a valid move encoding; assert it is a legal UCI move in the position
- `test_invalid_move_encoding_raises_move_decode_error` — inject an out-of-range encoding; assert MoveDecodeError
- `test_unrepresentable_position_raises_board_encode_error` — a position with illegal castling state; assert BoardEncodeError with description
- `test_bridge_uses_fake_cpu_not_unicorn` — assert ScriptedCpu is sufficient (no unicorn import needed)

*Phase 7 — Think orchestrator + Oracle (`tests/unit/retro/test_think.py`, `test_oracle.py`):*
- `test_think_session_with_scripted_cpu_returns_move` — ScriptedCpu replaying an observation trace; assert ThinkResult.move_uci is a legal move
- `test_think_session_deterministic_across_two_calls` — same request twice; assert identical ThinkResult
- `test_think_session_without_rom_raises_rom_not_found_error` — no ROM; assert RomNotFoundError with actionable message
- `test_observation_trace_contains_no_code_bytes` — assert committed trace fixtures have kind==observation and no forbidden keys (N-RETRO trace rule)
- `test_oracle_loads_corpus_jsonl_files` — load a fixture corpus; assert CorpusEntry list
- `test_oracle_verifies_entry_against_scripted_cpu` — ScriptedCpu scripted to return a known move; assert verify_corpus_entry True
- `test_oracle_detects_wrong_move` — ScriptedCpu returning wrong move; assert False
- `[retro_rom] test_think_session_with_real_rom_returns_known_move` — real ROM; startpos; level 1; assert matches corpus
- `[retro_rom] test_determinism_across_100_runs` — 100 × same request; assert all identical (N-RETRO-8)
- `[retro_rom] test_determinism_across_two_processes` — two subprocesses; assert identical results

*Phase 8 — UCI shim (`tests/unit/retro/test_uci.py`):*
- `test_uci_handshake_emits_id_name_and_uciok` — send "uci\nquit\n"; assert id name + uciok lines
- `test_uci_handshake_emits_required_options` — assert EmuLevel, EmuClockRate, EmuStrictOriginal, EmuRomPath options
- `test_uci_handshake_succeeds_without_a_rom` — no ROM configured; handshake still completes (FR-2)
- `test_uci_go_without_rom_returns_info_error_and_null_move` — send go; assert info string error + bestmove 0000 (FR-2)
- `test_uci_handshake_matches_is_valid_engine_probe` — reproduce Engines._run_uci_command contract exactly
- `test_uci_handshake_completes_within_two_seconds` — time the handshake; assert < 2 s (N-RETRO-10)
- `test_uci_position_startpos_updates_board` — send position startpos moves e2e4; assert internal board state
- `test_uci_setoption_emuclockrate_accepted` — setoption EmuClockRate value 50; no error
- `test_uci_setoption_strict_original_rejects_nondefault_clock` — EmuStrictOriginal true; then EmuClockRate 50; assert error response
- `[retro_rom] test_uci_go_with_rom_returns_legal_bestmove` — full round-trip; assert legal move

*Phase 9 — DOS x86 target (`tests/unit/retro/test_dos.py`):*
- `[retro_emu] test_unicorn_x86_loads_synthetic_com_file` — 6-byte .COM (NOP + RET); assert run completes
- `[retro_emu] test_unicorn_x86_register_roundtrip` — set AX; run nop; read AX; assert equal
- `[retro_rom] test_dos_rom_hash_matches_manifest` — user's DOS binary; assert in manifest
- `[retro_rom] test_dos_think_returns_legal_move` — DOS target; startpos; level 1; legal move
- `test_amiga_dos_corpus_agrees_except_documented_divergences` — load both corpora; for positions in both, assert moves agree or divergence is documented in docs/retro/divergences.md (N-RETRO-13)

*Phase 10 — Production Readiness:*
- `test_retro_completeness_every_public_callable_has_docstring` — copies tests/unit/rpa/test_completeness.py pattern (N-RETRO-7)
- `test_classical_start_does_not_import_code_retro` — subprocess app bootstrap; assert Code.Retro* absent from sys.modules (N-RETRO-11)
- `test_no_wallclock_call_in_think_path` — ast-scan; time.time/time.monotonic/time.sleep absent from Think.py and deps (N-RETRO-7 analogue)

**Spec refs:** all FR, NFR, §8, §9

---

## Phase 1 — Recon Spike (GO / KILL) ✅

**Branch:** `spike/retro-recon`  
**Docs shipped (Gate H):** `docs/features/retro-engine/recon_findings.md` (new)

**Files:**
- `tools/retro-recon/` (create — throwaway, experimental, deleted Phase 10)
- `docs/features/retro-engine/recon_findings.md` (create — the only durable output)
- `Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl` (create — hand-captured from FS-UAE)

**What we implement:**
- Phase 1-A first: run Battle Chess in FS-UAE; play 10 positions × 2 difficulty levels
  by hand; record `(fen, level, move, observed_seconds, source: "fs-uae-manual")` into
  the corpus file. This is the independent oracle all later phases verify against.
- Phase 1-B: Unicorn + Ghidra headless on the Amiga binary. Hook every memory read
  across the whole address space during a candidate think call to enumerate the full
  dependency surface. Deliver `recon_findings.md` with: binary identification
  (filename/sha256/hunk table), candidate think-entry address, calling convention
  hypothesis, board-struct offset hypothesis, the complete list of memory regions and
  trap addresses accessed during think, the timer-read site (if any), one successful
  think call from the start position whose result matches a Phase 1-A ground-truth entry.

**Kill criteria (fail any → do not proceed to Phase 2 without re-spec):**
1. The binary loads in Ghidra and Unicorn with sane m68k disassembly.
2. A recursive function with an alpha/beta-shaped signature is identifiable.
3. Static evaluation tables (piece values / piece-square) are present and plausible.
4. The board-state struct is mapped well enough to write a table of field offsets.
5. One think call from the start position returns a move that matches a 1-A corpus entry.

**TDD test cases:** N/A — spike produces a document, not test-covered code.  
**Spec refs:** FR-1, FR-2, FR-4, FR-9, §4 Purity, §7 Trace Redaction, D4, D5

---

## Phase 2 — Foundations ✅

**Branch:** `chore/retro-foundations`  
**Docs shipped (Gate H):** `docs/retro/testing.md` (complete)

**Files:**
- `bin/Code/Retro/__init__.py` (create — 0 bytes)
- `bin/Code/Retro/Types.py` (create — N-RETRO-1)
- `bin/Code/Retro/Errors.py` (create — RetroError hierarchy)
- `bin/Code/Retro/Cpus/__init__.py` (create — 0 bytes)
- `bin/Code/Retro/Cpus/Availability.py` (create — unicorn probe)
- `bin/Code/Base/CaissaErrors.py` (create — promote CaissaError, resolves D1)
- `bin/Code/Rpa/Errors.py` (edit — re-export CaissaError from Code.Base.CaissaErrors)
- `tests/unit/retro/__init__.py` (create)
- `tests/unit/retro/test_foundations.py` (create — invariant tests)
- `requirements-retro.txt` (create — unicorn>=2.0)
- `pytest.ini` (edit — add retro, retro_emu, retro_rom markers)
- `ruff.toml` (edit — add bin/Code/Retro/**, tests/unit/retro/**)
- `Makefile` (edit — extend test target, add cov-retro, test-retro-emu, test-retro-rom, retro-doctor)
- `.gitignore` (edit — add UserData/Retro/, Resources/Retro/Fixtures/)
- `CHANGELOG.md` (edit)

**What we implement:**
1. `bin/Code/Base/CaissaErrors.py` — move `CaissaError` here; `Rpa/Errors.py` re-exports it
2. `bin/Code/Retro/Types.py` — `Arch`, `RomId`, `MemRegion`, `MemoryImage`, `Board`, `Level`, `ThinkRequest`, `ThinkResult`, `RunResult`, `CorpusEntry`, `TraceStep`
3. `bin/Code/Retro/Errors.py` — `RetroError(CaissaError)` + all leaf classes from §8
4. `bin/Code/Retro/Cpus/Availability.py` — cached unicorn probe + actionable install message
5. Makefile, ruff, pytest config changes

**TDD test cases (`tests/unit/retro/test_foundations.py`):**
- `test_types_module_has_no_third_party_imports`
- `test_errors_module_has_no_third_party_imports`
- `test_all_retro_error_types_are_retro_error_subclasses`
- `test_caissa_error_is_a_single_class_object`
- `test_no_pyside6_import_anywhere_in_retro`
- `test_ruff_include_covers_retro_paths`
- `test_makefile_has_retro_targets`
- `test_pytest_ini_declares_retro_markers`

**Spec refs:** NFR-1, NFR-2, NFR-3, NFR-5, N-RETRO-1, N-RETRO-2, N-RETRO-5, §8

---

## Phase 3 — ROM Manifest + Containers ✅

**Branch:** `feat/retro-rom`  
**Docs shipped (Gate H):** `docs/retro/rom-setup.md` (complete)

**Files:**
- `bin/Code/Retro/Manifest.py` (create)
- `bin/Code/Retro/Rom.py` (create)
- `bin/Code/Retro/Fakes.py` (create — `build_synthetic_hunk`, `build_synthetic_com`)
- `Resources/Retro/manifest.json` (create — empty registry with correct schema)
- `tests/unit/retro/test_rom.py` (create)

**What we implement:**
1. `Manifest.py` — `load()`, `verify(path)`, `RomEntry` dataclass
2. `Rom.py` — `load_amiga_hunk()`, `detect_packer()`, `load_dos_mz()` (raises UnsupportedTargetError)
3. `Fakes.build_synthetic_hunk()` — assemble a valid minimal hunk with configurable code section
4. `manifest.json` — empty `{"version": 1, "entries": []}` schema stub

**TDD test cases (`tests/unit/retro/test_rom.py`):**
- `test_manifest_json_schema_validates`
- `test_manifest_entry_sha256_is_64_hex_chars`
- `test_manifest_entry_has_think_entry_offset`
- `test_no_tracked_file_matches_manifest_hash`
- `test_no_resources_retro_file_exceeds_size_cap`
- `test_rom_not_found_raises_rom_not_found_error`
- `test_rom_hash_mismatch_raises_rom_hash_mismatch_error`
- `test_amiga_hunk_synthetic_rom_loads`
- `test_amiga_hunk_relocation_applied`
- `test_amiga_hunk_bss_section_zeroed`
- `test_detect_packer_returns_none_for_plain_binary`
- `test_detect_packer_recognises_powerpacker_header`
- `test_dos_mz_raises_unsupported_target_error`
- `test_manifest_entries_gitignore_check`

**Spec refs:** FR-3, NFR-4, NFR-9, N-RETRO-4, N-RETRO-6, §6 ROM/Legal Policy

---

## Phase 4 — CPU Seam + FakeCpu ✅

**Branch:** `feat/retro-cpu`  
**Docs shipped (Gate H):** none (internal architecture; covered by testing.md)

**Files:**
- `bin/Code/Retro/Cpu.py` (create — base seam + UnicornCpu)
- `bin/Code/Retro/Cpus/Unicorn68k.py` (create)
- `bin/Code/Retro/Cpus/UnicornX86.py` (create — stub raising UnsupportedTargetError)
- `bin/Code/Retro/Fakes.py` (edit — add `ScriptedCpu`, `FakeClock`, `TracingCpu`)
- `tests/unit/retro/test_cpu.py` (create)

**What we implement:**
1. `Cpu.py` base class with the seam defined in §5.2
2. `ScriptedCpu` in `Fakes.py` — replays a pre-recorded effect list
3. `Cpus/Unicorn68k.py` — `UnicornCpu(Cpu)` for `UC_ARCH_M68K`
4. Parameterised test confirming both archs share the seam (using the synthetic COM stub for x86)

**TDD test cases (`tests/unit/retro/test_cpu.py`):**
- `test_scripted_cpu_replays_memory_reads`
- `test_scripted_cpu_replays_register_values`
- `test_scripted_cpu_run_returns_scripted_result`
- `test_scripted_cpu_records_writes`
- `test_unicorn_import_only_in_cpus_subpackage`
- `test_importing_code_retro_does_not_pull_unicorn`
- `[retro_emu] test_unicorn68k_loads_synthetic_hunk`
- `[retro_emu] test_unicorn68k_register_roundtrip`
- `[retro_emu] test_unicorn68k_memory_fault_raises_emulation_fault_error`
- `[retro_emu] test_unicorn68k_instruction_budget_raises_budget_error`
- `[retro_emu] test_unicorn68k_and_x86_share_cpu_seam`

**Spec refs:** NFR-4, NFR-6, N-RETRO-2, N-RETRO-3, §4 Purity, §5.2

---

## Phase 5 — Traps + Virtual Clock ✅

**Branch:** `feat/retro-traps`  
**Docs shipped (Gate H):** `docs/retro/uci-options.md` (`EmuClockRate`, `EmuStrictOriginal`)

**Files:**
- `bin/Code/Retro/Traps.py` (create)
- `tests/unit/retro/test_traps.py` (create)
- `tests/unit/retro/test_clock.py` (create)

**What we implement:**
1. `Traps.py` — address → handler dispatch; `TrapRegistry`; `VirtualClock` (deterministic, instruction-counted); unknown trap → `TrapUnhandledError`
2. Built-in Amiga stubs: `exec.library` base, `AllocMem`, `FreeMem`, `FindTask`, `Forbid`, `Permit` (nop or simple returns)
3. `FakeClock` in `Fakes.py` — scripted tick values for unit tests

**TDD test cases (`tests/unit/retro/test_traps.py`, `test_clock.py`):**
- `test_trap_registered_handler_is_called`
- `test_unknown_trap_raises_trap_unhandled_error`
- `test_every_profile_trap_has_a_handler`
- `test_virtual_clock_is_deterministic`
- `test_virtual_clock_rate_scales_linearly`
- `test_strict_original_rejects_non_default_clock_rate`
- `[retro_emu] test_traps_intercept_timer_read_in_synthetic_program`

**Spec refs:** FR-6, FR-7, NFR-8, N-RETRO-8, N-RETRO-12, §5.5, D4

---

## Phase 6 — Board Bridge ✅

**Branch:** `feat/retro-bridge`  
**Docs shipped (Gate H):** `docs/retro/reverse-engineering.md` updated with struct layout

**Files:**
- `bin/Code/Retro/Bridge.py` (create)
- `tests/unit/retro/test_bridge.py` (create)

**What we implement:**
1. `Bridge.py` — `encode_board(board, profile, cpu)`, `decode_move(cpu, profile)`
2. A `Profiles.py` stub with a placeholder `EngineProfile` for the Amiga target (offsets TBD from Phase 1 findings)
3. Round-trip property tests using `python-chess` for position generation

**TDD test cases (`tests/unit/retro/test_bridge.py`):**
- `test_startpos_encodes_to_expected_struct_bytes`
- `test_arbitrary_position_encodes_and_decodes_to_same_fen`
- `test_move_decode_returns_legal_uci_string`
- `test_invalid_move_encoding_raises_move_decode_error`
- `test_unrepresentable_position_raises_board_encode_error`
- `test_bridge_uses_fake_cpu_not_unicorn`

**Spec refs:** FR-4, FR-5, §5.4, D4

---

## Phase 7 — Think Orchestrator + Oracle ✅

**Branch:** `feat/retro-think`  
**Docs shipped (Gate H):** `docs/retro/README.md` updated with end-to-end flow

**Files:**
- `bin/Code/Retro/Think.py` (create)
- `bin/Code/Retro/Oracle.py` (create)
- `bin/Code/Retro/Trace.py` (create — observation trace record/replay)
- `tests/unit/retro/test_think.py` (create)
- `tests/unit/retro/test_oracle.py` (create)
- `tests/unit/retro/_fixtures/traces/` (create — observation-level trace fixtures)
- `Resources/Retro/Corpus/` (edit — add captured corpus entries from Phase 1 ground truth)

**What we implement:**
1. `Think.py` — `ThinkSession`: ROM verify → memory load (cached) → traps setup → board marshal → run → decode → return `ThinkResult`
2. `Oracle.py` — corpus load, `verify_corpus_entry`
3. `Trace.py` — `TRACE_OBSERVATION` record/replay; redaction enforcement

**TDD test cases:**
- `test_think_session_with_scripted_cpu_returns_move`
- `test_think_session_deterministic_across_two_calls`
- `test_think_session_without_rom_raises_rom_not_found_error`
- `test_observation_trace_contains_no_code_bytes`
- `test_oracle_loads_corpus_jsonl_files`
- `test_oracle_verifies_entry_against_scripted_cpu`
- `test_oracle_detects_wrong_move`
- `[retro_rom] test_think_session_with_real_rom_returns_known_move`
- `[retro_rom] test_determinism_across_100_runs`
- `[retro_rom] test_determinism_across_two_processes`

**Spec refs:** FR-1, FR-4, BR-2, BR-3, NFR-8, N-RETRO-8, §5.6, §7

---

## Phase 8 — UCI Shim ✅

**Branch:** `feat/retro-uci`  
**Docs shipped (Gate H):** `docs/retro/uci-options.md` (complete), `docs/retro/rom-setup.md` updated

**Files:**
- `bin/Code/Retro/Uci.py` (create)
- `tools/caissa-retro` (create — UCI entry point)
- `bin/OS/darwin/Engines/SOURCES.md` (edit — provenance note for retro engine)
- `bin/OS/darwin/OSEngines.py` (edit — `_EXTRA_ENGINES` entry + `li_engines_fixed_elo`)
- `docs/engines.md` (edit — row for retro engine)
- `tests/unit/retro/test_uci.py` (create)
- `tests/unit/retro/_fixtures/uci/` (create — golden UCI transcripts)
- `CHANGELOG.md` (edit)

**What we implement:**
1. `Uci.py` — line-I/O seam, handles uci/isready/setoption/position/go/stop/quit
2. `tools/caissa-retro` — thin wrapper calling `Uci.main()`
3. Darwin registration: one tuple in `_EXTRA_ENGINES`, guarded by `if not os.path.isfile(exe): continue` (already present — engine vanishes when no binary)

**TDD test cases (`tests/unit/retro/test_uci.py`):**
- `test_uci_handshake_emits_id_name_and_uciok`
- `test_uci_handshake_emits_required_options`
- `test_uci_handshake_succeeds_without_a_rom`
- `test_uci_go_without_rom_returns_info_error_and_null_move`
- `test_uci_handshake_matches_is_valid_engine_probe`
- `test_uci_handshake_completes_within_two_seconds`
- `test_uci_position_startpos_updates_board`
- `test_uci_setoption_emuclockrate_accepted`
- `test_uci_setoption_strict_original_rejects_nondefault_clock`
- `[retro_rom] test_uci_go_with_rom_returns_legal_bestmove`

**Spec refs:** FR-1, FR-2, FR-6, FR-7, FR-8, NFR-7, N-RETRO-10

---

## Phase 9 — DOS x86 Second Target ✅

**Branch:** `feat/retro-dos`  
**Docs shipped (Gate H):** `docs/retro/divergences.md` (new); `docs/retro/reverse-engineering.md` updated

**Files:**
- `bin/Code/Retro/Cpus/UnicornX86.py` (edit — implement from stub)
- `docs/retro/divergences.md` (create — cross-port move divergence report)
- `tests/unit/retro/test_dos.py` (create)
- `Resources/Retro/Corpus/groundtruth-dos-manual.jsonl` (create — hand-captured from DOSBox)
- `manifest.json` (edit — add DOS entry once hash confirmed)

**What we implement:**
1. `Cpus/UnicornX86.py` — `UnicornCpu` for x86-16 (UC_ARCH_X86 + UC_MODE_16)
2. DOS installer unpacking (LZEXE/PKLITE detection + extraction in `Rom.py`)
3. DOS engine profile in `Profiles.py`
4. Ground-truth capture from DOSBox; divergence analysis vs Amiga corpus

**TDD test cases:**
- `[retro_emu] test_unicorn_x86_loads_synthetic_com_file`
- `[retro_emu] test_unicorn_x86_register_roundtrip`
- `[retro_rom] test_dos_rom_hash_matches_manifest`
- `[retro_rom] test_dos_think_returns_legal_move`
- `test_amiga_dos_corpus_agrees_except_documented_divergences`

**Spec refs:** FR-9, §2.4 Constraints, D1 (two-target seam)

---

## Phase 10 — Production Readiness ✅

**Branch:** `chore/retro-production`  
**Docs shipped (Gate H):** all `docs/retro/` pages complete; `production_readiness.md`

**Files:**
- `tests/unit/retro/test_completeness.py` (create — docstring invariant)
- `docs/features/retro-engine/production_readiness.md` (create — Gate E)
- `tools/retro-recon/` (delete — spike removed)
- All living docs: front matter `**Status:** Completed YYYY-MM-DD`

**What we implement:**
1. Docstring completeness test (N-RETRO-7)
2. Classical invariant test (N-RETRO-11)
3. Wall-clock-call audit (no `time.time/monotonic/sleep` in think path)
4. `caissa-retro audit-tree` sub-command confirming no committed code bytes
5. Delete throwaway spike tools

**TDD test cases:**
- `test_retro_completeness_every_public_callable_has_docstring`
- `test_classical_start_does_not_import_code_retro`
- `test_no_wallclock_call_in_think_path`

**Spec refs:** NFR-2, N-RETRO-7, N-RETRO-11, Gate E

---

## Verification

```bash
# Fast suite — no ROM, no unicorn (always runs)
make test   # marker: unit or rpa or retro — must pass green

# Lint
make lint   # zero findings; confirm bin/Code/Retro/ is linted

# Coverage
make cov-retro   # ≥ 90% branch for Code.Retro (Cpus/ omitted)

# Capability probe
make retro-doctor   # unicorn availability + ROM verification status

# Emulator tier (pip install -r requirements-retro.txt)
make test-retro-emu

# Bit-exactness tier (user-supplied verified binary)
export CAISSA_RETRO_ROM=/path/to/BattleChess
make test-retro-rom   # replays Resources/Retro/Corpus/*.jsonl, all moves match

# Protocol smoke test — confirm handshake works without a ROM
printf 'uci\nquit\n' | tools/caissa-retro   # must emit id name + uciok within 2 s

# Speed claim
time (printf 'uci\nposition startpos\ngo\nquit\n' | tools/caissa-retro)   # ms not minutes
```
