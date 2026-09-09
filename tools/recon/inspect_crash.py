"""Inspect crash site and hooks for a given address."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
import capstone
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Think import _scan_cmpiw

CRASH_PC = 0xB210

_REPO = Path(__file__).parents[2]
rom_bytes = (_REPO / 'Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_bytes)
code_r = next(r for r in regions if r.label == 'HUNK_CODE' and r.size > 0)
code = rom_bytes[code_r.offset:code_r.offset + code_r.size]
base = code_r.load_address

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

start = CRASH_PC - 0x30
end = CRASH_PC + 0x30
print('Disassembly 0x%X-0x%X:' % (start, end))
for ins in md.disasm(code[start-base:end-base], start):
    marker = '<-- CRASH' if ins.address == CRASH_PC else ''
    print('  0x%05X: %-20s %-30s %s' % (ins.address, ins.mnemonic, ins.op_str, marker))

scan = _scan_cmpiw(code, base=base)
print()
print('Hooks in 0x%X-0x%X:' % (start, end))
for addr in range(start, end, 2):
    if addr in scan:
        print('  0x%05X: %s' % (addr, scan[addr]))
