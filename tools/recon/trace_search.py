#!/usr/bin/env python3
"""Trace first N distinct PC values after outer driver starts, to find where it gets stuck."""
import sys, importlib.util, types, struct, collections

_code_pkg = types.ModuleType('Code')
_code_pkg.__path__ = ['bin/Code']
sys.modules['Code'] = _code_pkg
for sub in ['Code.Retro', 'Code.Retro.Cpus']:
    m = types.ModuleType(sub)
    m.__path__ = [sub.replace('.','/').replace('Code','bin/Code')]
    sys.modules[sub] = m

def _load(dotpath, filepath):
    spec = importlib.util.spec_from_file_location(dotpath, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotpath] = mod
    spec.loader.exec_module(mod)
    return mod

_load('Code.Retro.Types',    'bin/Code/Retro/Types.py')
_load('Code.Retro.Errors',   'bin/Code/Retro/Errors.py')
Manifest = _load('Code.Retro.Manifest', 'bin/Code/Retro/Manifest.py')
Rom = _load('Code.Retro.Rom', 'bin/Code/Retro/Rom.py')

import unicorn, unicorn.m68k_const as M68K
import capstone

rom_data = open(Manifest.default_rom_path(), 'rb').read()
regions = Rom.parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE

uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
uc.mem_map(0, 0x200000)
uc.mem_write(0, code)
uc.reg_write(M68K.UC_M68K_REG_A4, A4)
sp = 0x1F0000 - 4
SENTINEL = 0xFFFF0000
uc.mem_write(sp, struct.pack('>I', SENTINEL))
uc.reg_write(M68K.UC_M68K_REG_A7, sp)
# Clear abort flag
uc.mem_write(A4 - 0x35B4, struct.pack('>H', 0))

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

_max_unique = 200  # stop after this many unique PCs
_seen = set()
_ordered = []
_counts = collections.Counter()
_insn_count = [0]
_stop = [False]

BYPASS_NOOP = {0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}

def _hook_code(uc_, addr, size, _):
    if _stop[0]:
        uc_.emu_stop()
        return
    _insn_count[0] += 1
    if addr not in _seen:
        _seen.add(addr)
        _ordered.append(addr)
        if len(_seen) >= _max_unique:
            _stop[0] = True
    _counts[addr] += 1
    # NOOP stubs
    if addr in BYPASS_NOOP:
        a7 = uc_.reg_read(M68K.UC_M68K_REG_A7)
        try:
            ret = struct.unpack('>I', bytes(uc_.mem_read(a7, 4)))[0]
            uc_.reg_write(M68K.UC_M68K_REG_A7, a7 + 4)
            uc_.reg_write(M68K.UC_M68K_REG_PC, ret)
        except Exception:
            pass
    # Loop check
    if addr == 0x820C:
        a4_ = uc_.reg_read(M68K.UC_M68K_REG_A4)
        flag = struct.unpack('>H', bytes(uc_.mem_read((a4_ - 0x35A4) & 0xFFFFFFFF, 2)))[0]
        uc_.reg_write(M68K.UC_M68K_REG_PC, 0x8214 if flag == 2 else 0x8228)
    # Player check
    if addr == 0x8220:
        a0_ = uc_.reg_read(M68K.UC_M68K_REG_A0)
        d0_ = uc_.reg_read(M68K.UC_M68K_REG_D0)
        d0s = d0_ if d0_ < 0x80000000 else d0_ - 0x100000000
        val = struct.unpack('>H', bytes(uc_.mem_read((a0_ + d0s) & 0xFFFFFFFF, 2)))[0]
        uc_.reg_write(M68K.UC_M68K_REG_PC, 0x81E4 if val == 1 else 0x8228)

uc.hook_add(unicorn.UC_HOOK_CODE, _hook_code)

# Set player type = 1 (Human) to make outer driver loop
uc.mem_write(A4 - 0x782A + 1 * 2, struct.pack('>H', 1))  # player_type[1] = 1

try:
    uc.emu_start(0x81DC, SENTINEL, count=10_000_000)
except unicorn.UcError as e:
    print(f"Unicorn error: {e} at PC=0x{uc.reg_read(M68K.UC_M68K_REG_PC):05X}")

print(f"\nTotal instructions: {_insn_count[0]}")
print(f"Unique PCs seen: {len(_seen)}")
print("\nFirst 60 unique PCs (in visit order):")
for i, addr in enumerate(_ordered[:60]):
    insns = list(md.disasm(code[addr:addr+8], addr))
    disasm = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else "???"
    count = _counts[addr]
    print(f"  [{i:3d}] 0x{addr:05X}  ({count:5d}x)  {disasm}")

# Show top hottest addresses
print("\nTop 20 hottest addresses:")
for addr, cnt in _counts.most_common(20):
    insns = list(md.disasm(code[addr:addr+8], addr))
    disasm = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else "???"
    print(f"  0x{addr:05X}  {cnt:8d}x  {disasm}")
