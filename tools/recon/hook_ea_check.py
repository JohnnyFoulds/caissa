"""Check which cmpiw hooks could write to critical code addresses (A4-relative)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
from Code.Retro.Bridge import A4 as _A4_VALUE
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Think import _scan_cmpiw

A4 = _A4_VALUE  # 0x7FFE

rom_bytes = (Path(__file__).parents[2] / 'Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_bytes)
code_r = next(r for r in regions if r.label == 'HUNK_CODE' and r.size > 0)
code = rom_bytes[code_r.offset:code_r.offset + code_r.size]

scan = _scan_cmpiw(code, base=code_r.load_address)
print('Total hooks:', len(scan))
print()

# For 'd16' hooks with an_reg=4 (A4-relative): ea_addr = A4 + d16
# Check which write to addresses in the code area (0x0000-0x11D1C)
CODE_END = code_r.size  # 0x11D1C
print('Hooks with an_reg=4 (A4-relative d16) writing to CODE area [0..0x%X]:' % CODE_END)
for addr, info in sorted(scan.items()):
    op, mode, an_reg, imm16, d16_or_ext = info
    if op == 'cmp':
        continue  # read-only, can't corrupt
    if mode == 'd16' and an_reg == 4:
        ea_addr = (A4 + d16_or_ext) & 0xFFFFFFFF
        if 0 <= ea_addr <= CODE_END:
            print('  Hook 0x%05X: %s #0x%04X, (0x%X, A4) → ea=0x%X' % (
                addr, op, imm16, d16_or_ext & 0xFFFF, ea_addr))

print()
print('All write hooks with d16 ea in 0x7900-0x7A00 (critical loop area):')
for addr, info in sorted(scan.items()):
    op, mode, an_reg, imm16, d16_or_ext = info
    if op == 'cmp': continue
    if mode == 'd16' and an_reg == 4:
        ea_addr = (A4 + d16_or_ext) & 0xFFFFFFFF
        if 0x7900 <= ea_addr <= 0x7A00:
            print('  Hook 0x%05X: %s #0x%04X, (d16=%d, A4) → ea=0x%05X' % (
                addr, op, imm16, d16_or_ext, ea_addr))
