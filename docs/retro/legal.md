# Retro Engine — Legal Policy

This document records the legal theory under which the Retro Engine feature is built
and what may or may not be committed to the public `JohnnyFoulds/caissa` repository.

---

## The hard rule

**No original binary, disk image, or extracted code segment is ever committed.**

Battle Chess (Interplay, 1988) is under copyright. The binary is not freely
redistributable. This project does not ship it, host it, or embed parts of it.

---

## What IS committed

### sha256 hashes and metadata (`Resources/Retro/manifest.json`)

Cryptographic hashes and file-size metadata are facts about a binary, not the binary
itself. Committing a sha256 is legally equivalent to publishing "I know this file exists
and its fingerprint is X" — not a copy of the file. The same model is used by MAME,
RetroArch's core manifests, and many game preservation projects.

### Offset tables and struct layouts (`bin/Code/Retro/Profiles.py`)

Structural facts about a program (e.g., "at byte offset 0x12A8 there is a 16×16 array
of 16-bit piece-square values") are data derived from reverse engineering, not copies
of the program. This is the basis on which tools like Ghidra and IDA output can be
published: the analysis is your own work.

### Corpus files — (position, level, move) records (`Resources/Retro/Corpus/*.jsonl`)

A list of chess moves in a given position is factual game data, comparable to a game
score or an opening book. It is not code, not an executable, and not a bytecode
representation of the original program. The same distinction separates "what moves did
Kasparov play" (factual) from "here is Kasparov's brain" (not factual, obviously
impossible). The corpus is committed as factual move data.

### Observation traces (`tests/unit/retro/_fixtures/traces/*.json`)

Observation-level traces contain boundary events only: entry register state, trap call
arguments and return values, board-struct read offsets and values, total instruction
count. They contain no PC stream, no fetched opcodes, no code bytes, no raw memory
dumps. They do not reproduce the program. They are the output of watching the program
run, not a recording of the program itself.

---

## What is NEVER committed

| Prohibited | Why |
|---|---|
| The binary (`BattleChess`, any `.exe`) | Copyright; the user supplies their own |
| Any disk image (`.adf`, `.img`, `.dsk`) | Same |
| Verbatim extracted code bytes | Reproduces the copyrighted work |
| Any memory dump | May include code sections |
| Full / `TRACE_FULL` traces | Include `code_bytes` / `pc_stream` — reproduce the program |
| Any file whose sha256 appears in `manifest.json` | Would mean the binary is in the repo |

The test `test_no_tracked_file_matches_manifest_hash` enforces this automatically.

---

## User's responsibility

The user must own a legal copy of Battle Chess. The game is widely available as
abandonware, but Interplay's successor rights are unresolved. Obtain your copy through
legitimate channels.

The shim verifies the binary by sha256 before loading and refuses to run on an
unverified binary. This is a content-integrity check, not a DRM mechanism.

---

## Disclaimer

This policy is the maintainer's own legal theory for their own records. It is not legal
advice. If you are uncertain about your jurisdiction's rules regarding reverse
engineering and game preservation, consult a lawyer.
