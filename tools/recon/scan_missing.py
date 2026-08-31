"""Scan for 6-byte instructions NOT in the current cmpiw scan that have dangerous trailing bytes."""
import sys, capstone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Think import _scan_cmpiw

rom_bytes = (Path(__file__).parents[2] / 'Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_bytes)
code_r = next(r for r in regions if r.label == 'HUNK_CODE' and r.size > 0)
code = rom_bytes[code_r.offset:code_r.offset + code_r.size]
base = code_r.load_address

# Already-scanned addresses
existing = _scan_cmpiw(code, base=base)
print('Existing scan entries:', len(existing))

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

# BYTE-size immediate instructions with (d16,An): b0 in immediate set, b1 in 0x28-0x2F
# ORI.B=0x00, ANDI.B=0x02, SUBI.B=0x04, ADDI.B=0x06, EORI.B=0x0A, CMPI.B=0x0C
# For byte size: imm is in 1 byte padded to 2 bytes (next word = 0x00nn or 0xnn00 padded)
# Total encoding: opcode(2) + padded_byte_imm(2) + displacement(2) = 6 bytes
BYTE_OP_MAP = {0x00, 0x02, 0x04, 0x06, 0x0A, 0x0C}

print('\nByte-size immediate instructions with (d16,An) or (An,Xn):')
n = len(code)
found_byte = {}
i = 0
while i < n - 5:
    b0 = code[i]; b1 = code[i+1]
    if b0 in BYTE_OP_MAP:
        if 0x28 <= b1 <= 0x2F:  # byte-size, (d16,An) mode
            an_reg = b1 & 0x07
            imm8 = code[i+3]  # byte immediate (padded word at i+2,i+3)
            raw_d16 = (code[i+4] << 8) | code[i+5]
            d16 = raw_d16 if raw_d16 < 0x8000 else raw_d16 - 0x10000
            trailing = code[i+4:i+6].hex()
            # Check if trailing bytes look like a MOVEA instruction (sets address reg)
            trail_word = (code[i+4] << 8) | code[i+5]
            is_movea = (trail_word & 0xF000) == 0x2000 and ((trail_word >> 6) & 0x7) == 1
            is_movea_dangerous = is_movea and ((trail_word >> 9) & 0x7) == 4  # sets A4
            found_byte[base+i] = ('b', an_reg, imm8, d16, trailing, is_movea_dangerous)
            if is_movea_dangerous:
                print('  DANGER 0x%05X: CMPI/ADDI.B A%d,d16=%d trailing=%s (MOVEA to A4!)' % (
                    base+i, an_reg, d16, trailing))
            i += 6; continue
        elif 0x30 <= b1 <= 0x37:  # byte-size, (An,Xn) mode
            an_reg = b1 & 0x07
            imm8 = code[i+3]
            ext = (code[i+4] << 8) | code[i+5]
            trailing = code[i+4:i+6].hex()
            trail_word = ext
            is_movea_dangerous = ((trail_word & 0xF000) == 0x2000 and
                                   ((trail_word >> 6) & 0x7) == 1 and
                                   ((trail_word >> 9) & 0x7) == 4)
            found_byte[base+i] = ('b_xn', an_reg, imm8, ext, trailing, is_movea_dangerous)
            if is_movea_dangerous:
                print('  DANGER 0x%05X: CMPI/ADDI.B A%d,anXn trailing=%s (MOVEA to A4!)' % (
                    base+i, an_reg, trailing))
            i += 6; continue
    i += 2

print('Total byte-size (d16,An)/(An,Xn) 6-byte instructions found: %d' % len(found_byte))

# Also scan for trailing bytes that are "movea.l" instructions setting A4
# movea.l (Am), A4 = 0x28+mode*8+reg (various)
# movea.w #imm, A4 = 0x28FC (but this is 4 bytes)
# The dangerous 2-byte trailing: anything that changes A4

# Look for ALL 6-byte immediate instructions (including those already in scan)
# that have trailing 2 bytes = MOVEA instruction targeting A4
print('\nAll 6-byte instructions with trailing bytes that modify A4:')
ALL_IMM_OPS = {0x00, 0x02, 0x04, 0x06, 0x0A, 0x0C}
i = 0
dangerous = []
while i < n - 5:
    b0 = code[i]; b1 = code[i+1]
    matched6 = False
    sz = None
    if b0 in ALL_IMM_OPS:
        if 0x28 <= b1 <= 0x2F: sz = 'B'; matched6 = True
        elif 0x68 <= b1 <= 0x6F: sz = 'W'; matched6 = True
        elif 0x30 <= b1 <= 0x37: sz = 'B'; matched6 = True
        elif 0x70 <= b1 <= 0x77: sz = 'W'; matched6 = True
    if matched6 and i + 5 < n:
        trail = (code[i+4] << 8) | code[i+5]
        # Check if trail_word decodes as something that writes A4
        # movea.l or movea.w: `0010 100 001 EA` = 0x28..
        # Also: adda.l / adda.w: `1101 100 0 11 EA` = 0xD8..
        # For our purposes: just list instructions where trailing 2 bytes look like
        # they could modify A4 or A2 (since we saw movea.l d2, a2 at 0x79C0)
        addr = base + i
        if addr not in existing:  # NOT already handled
            dis_list = list(md.disasm(code[i+4:i+6], addr+4))
            trail_dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
            # Check if trailing instruction modifies A4 or could corrupt things
            if 'a4' in trail_dis or trail == 0xFFFF or trail == 0x28BC or 0x28 <= (trail>>8) <= 0x2F:
                dangerous.append((addr, sz, b0, b1, trail, trail_dis))

for addr, sz, b0, b1, trail, trail_dis in dangerous[:20]:
    dis_list = list(md.disasm(code[addr-base:addr-base+6], addr))
    full_dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
    print('  0x%05X: [%-35s] trail=0x%04X [%s]' % (addr, full_dis, trail, trail_dis))

if not dangerous:
    print('  (none found — dangerous bytes could be from other instruction types)')

# Let's specifically look for trailing = movea.l instruction or "movea" family
print()
print('Byte-size (d16/anXn) instructions with trailing = any MOVEA-like (0x2xxx):')
count = 0
i = 0
while i < n - 5:
    b0 = code[i]; b1 = code[i+1]
    if b0 in ALL_IMM_OPS and (0x28 <= b1 <= 0x37):
        trail = (code[i+4] << 8) | code[i+5]
        if (trail & 0xF000) == 0x2000:  # looks like MOVE.L or MOVEA.L
            addr = base + i
            dis_list = list(md.disasm(code[i:i+6], addr))
            ins_dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
            trail_dis_list = list(md.disasm(code[i+4:i+6], addr+4))
            trail_dis = trail_dis_list[0].mnemonic + ' ' + trail_dis_list[0].op_str if trail_dis_list else '???'
            print('  0x%05X: %-35s   trail=0x%04X [%s]' % (addr, ins_dis, trail, trail_dis))
            count += 1
    i += 2
if count == 0:
    print('  (none)')
