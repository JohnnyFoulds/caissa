# RE Toolchain — Amiga M68K Binary Analysis

Reference for anyone setting up the reverse-engineering environment for the Battle Chess Amiga binary (or any Amiga M68K target).

---

## Tier 1 — Primary tools

### IRA v2.09 — M68K reassembler

**Purpose**: Produces a complete, annotated `.asm` listing of an Amiga hunk binary. Code vs data regions identified by PREPROC. Output is reassemblable — byte-for-byte identical to the input when fed back to the vasm assembler.

**Status**: INSTALLED at `~/bin/ira`

**Install on ARM64 macOS** (standard Makefile uses `-m32` which fails on Apple Silicon):
```bash
git clone --depth 1 https://github.com/AmigaPorts/ira /tmp/ira-build
mkdir /tmp/ira-build/obj
sed 's/-m32//g' /tmp/ira-build/Makefile.osx > /tmp/ira-build/Makefile.osx64
cd /tmp/ira-build && make -f Makefile.osx64
cp iraosx ~/bin/ira
ira --version   # → IRA V2.09 ...
```

**Usage for Battle Chess** (Dragon-crack binary requires truncation first):
```bash
# Strip the non-standard Dragon-crack trailing hunk (starts at file offset 73028)
python3 -c "open('/tmp/bc_valid.amiga','wb').write(open('Resources/Retro/BattleChess.amiga','rb').read()[:73028])"

# Disassemble with known entry points (-ENTRY flags critical — PREPROC alone classifies ~100% as data without them)
~/bin/ira -A -KEEPZH -NEWSTYLE -COMPAT=bi \
    -ENTRY=81DC -ENTRY=C198 -ENTRY=DE7A -ENTRY=D6D2 -ENTRY=D400 \
    /tmp/bc_valid.amiga /tmp/bc_entry.asm
# Produces /tmp/bc_entry.asm — ~25k lines, ~22k lines of code
```

**Output format**: `<TAB>MNEMONIC<TAB>operands<TAB>;address: hexbytes`
- Addresses are 5-digit hex: `;081dc:`, `;0d490:`, `;0d8fe:`
- 6-byte instructions show 6 hex bytes: `31adfff40800`
- Labels auto-generated as `LAB_xxxx`

**Reference**: `github.com/AmigaPorts/ira` — Aminet: `dev/asm/ira`

---

### Ghidra 12.x — NSA SRE framework

**Purpose**: Interactive disassembler + **decompiler**. The decompiler produces C pseudocode for each function — critical for understanding algorithm-level logic without hand-tracing assembly. Supports M68K natively; Amiga hunk format via plugin.

**Status**: NOT INSTALLED — install before Step 1 of the BC AI analysis

**Install on macOS**:
```bash
brew install openjdk@21 ghidra
# Ghidra installs to $(brew --prefix ghidra)/libexec/
export GHIDRA_INSTALL_DIR=$(brew --prefix ghidra)/libexec

# Download ghidra-amiga hunk loader plugin
# Match plugin version to installed Ghidra version — check brew info ghidra for exact version
curl -L https://github.com/BartmanAbyss/ghidra-amiga/releases/download/20260128/ghidra_12.0.1_PUBLIC_20260128_ghidra-amiga.zip \
     -o /tmp/ghidra-amiga.zip
# Install via: Ghidra GUI → File → Install Extensions → select zip
# OR headless install: unzip into $GHIDRA_INSTALL_DIR/Ghidra/Extensions/
```

**Version compatibility note** (2026-08-31): brew provides Ghidra 12.1.3; latest `ghidra-amiga` release targets 12.0.1. Ghidra plugins generally load across minor versions. If it fails, install Ghidra 12.0.1 directly from `github.com/NationalSecurityAgency/ghidra/releases`.

**Critical Ghidra settings for Amiga assembly code** (from Tetracorp guide):
- **Untick** "Call-Fixup Installer" — otherwise code after JSR is wrongly marked non-reachable
- **Untick** "Non-Returning Functions" — same reason
- **Untick** "Unicode String References" — Amiga is pre-Unicode

**Reference**: `tetracorp.github.io/guide/intro-amiga-ghidra.html`

---

### PyGhidra — Python API for Ghidra

**Purpose**: Drive Ghidra headlessly from CPython 3. Call the decompiler on specific functions and get C pseudocode programmatically. No GUI. DOD Cyber Crime Center project, now bundled in Ghidra 11+.

**Status**: NOT INSTALLED — install after Ghidra

**Install**:
```bash
/Users/johannes/code/lucaschess/.venv/bin/pip install pyghidra
# Requires GHIDRA_INSTALL_DIR env var set (see Ghidra section above)
python3 -c "import pyghidra; print('ok')"
```

**Batch decompile pattern**:
```python
import pyghidra, os

AI_FUNCTIONS = {
    0x81DC: "outer_driver",
    0xC198: "inner_search",
    0xDE7A: "de7a_handler",
    0xD6D2: "update_best_move_candidate",
    0xC91A: "move_generator",
    0xD490: "init_piece_candidates",
}

with pyghidra.open_program("/tmp/bc_valid.amiga") as flat_api:
    from ghidra.app.decompiler import DecompInterface
    from ghidra.util.task import ConsoleTaskMonitor
    monitor = ConsoleTaskMonitor()
    prog = flat_api.getCurrentProgram()
    decomp = DecompInterface()
    decomp.openProgram(prog)
    for addr, name in AI_FUNCTIONS.items():
        func_addr = flat_api.toAddr(addr)
        func = flat_api.getFunctionAt(func_addr)
        if func is None:
            func = flat_api.createFunction(func_addr, name)
        result = decomp.decompileFunction(func, 60, monitor)
        c_code = result.getDecompiledFunction().getC()
        path = f"/tmp/bc_{name}.c"
        open(path, "w").write(c_code)
        print(f"  {name} → {path}")
```

**SECURITY**: The `.c` output files are LOCAL ONLY — never commit them. Only the documented pseudo-code algorithm (in `ai_engine_map.md`) is committed.

**Reference**: `pypi.org/project/pyghidra`, `ghidradocs.com/.../PyGhidra`

---

### capstone 5.0 — Python disassembly library

**Purpose**: Targeted instruction disassembly in Python. Used in `Think.py` to scan for 6-byte instruction forms and patch them before emulation. Best for byte-level analysis — not for full binary exploration.

**Status**: INSTALLED in `.venv`

```python
import capstone
cs = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
cs.detail = True
```

---

## Tier 2 — Reference resources

| Resource | URL | What it provides |
|---|---|---|
| Chess Programming Wiki — 0x88 | `chessprogramming.org/0x88` | Full 0x88 board representation spec; directly maps to BC board encoding |
| Chess Programming Wiki — Alpha-Beta | `chessprogramming.org/Alpha-Beta` | Algorithm reference for the BC search strategy |
| Chess Programming Wiki — Piece-Square Tables | `chessprogramming.org/Piece-Square_Tables` | Context for 1988-era evaluation functions |
| Unicorn M68K issues | `github.com/unicorn-engine/unicorn/issues/1502` | Known M68K instruction failures; confirms 6-byte MOVE.W class |
| Tetracorp Amiga RE guides | `tetracorp.github.io/guide/` | Best practice for IRA + Ghidra on Amiga binaries |
| IRA config docs | `/tmp/ira-build/ira_config.doc` | SYMBOL/LABEL/COMMENT directives for iterative annotation |
| M68K Programmer's Reference | `m680x0.github.io/doc/official-docs.html` | Official Motorola M68K instruction set reference |

---

## Tier 3 — Evaluated but not used

| Tool | Reason not used |
|---|---|
| **Cutter** (GUI, rz-ghidra) | Not scriptable enough for batch decompilation; Ghidra+PyGhidra is superior |
| **RetDec** | LLVM-based; M68K support unclear; dormant since 2022 |
| **IDA Pro** | Best-in-class per Hex-Rays docs, but commercial (~$3000); Ghidra is equivalent |
| **radare2/rizin** | Amiga hunk support limited; less documented for this workflow |
| **Aira Force** | GUI wrapper around IRA with basic Amiga debugger; not needed since we have Unicorn |

---

## Dragon-crack binary handling

The Battle Chess binary at `Resources/Retro/BattleChess.amiga` is a Dragon Inc crack with a non-standard trailing hunk (type `0x14C` at file offset 73028). This causes IRA and Ghidra to fail on the unmodified file.

**Workaround** (used for all tool invocations):
```bash
python3 -c "
with open('Resources/Retro/BattleChess.amiga', 'rb') as f:
    data = f.read()
with open('/tmp/bc_valid.amiga', 'wb') as f:
    f.write(data[:73028])   # valid code hunk only
"
```

The Dragon-crack bytes (11884 bytes) are loaded separately in `Rom.py` as `DRAGON_CRACK` region. See `bin/Code/Retro/Rom.py` for the full load logic.

**Open question** (Step 0b of plan): empirically verify whether the Dragon-crack ROM vs original ROM produces different AI results under Unicorn. Decision recorded in CLAUDE.md.
