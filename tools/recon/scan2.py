"""Standalone scan for LONG-size (8-byte) immediate instructions Unicorn might mis-decode."""
import sys, struct
from pathlib import Path

# Parse Amiga hunk manually
rom = (Path(__file__).parents[2] / 'Resources/Retro/BattleChess.amiga').read_bytes()

# Find HUNK_CODE: type 0x3E9
i = 0
code = None
base = 0
while i < len(rom) - 4:
    htype = struct.unpack_from('>I', rom, i)[0]
    i += 4
    if htype == 0x3E9:  # HUNK_CODE
        size_lw = struct.unpack_from('>I', rom, i)[0] & 0x3FFFFFFF
        i += 4
        n = size_lw * 4
        code = rom[i:i+n]
        base = 0  # will set after we know load address
        i += n
        break
    elif htype == 0x3E8:  # HUNK_HEADER
        # skip
        cnt = struct.unpack_from('>I', rom, i)[0]; i += 4
        i += cnt * 4 + 8
    elif htype in (0x3EA, 0x3EB):  # DATA/BSS
        size_lw = struct.unpack_from('>I', rom, i)[0] & 0x3FFFFFFF; i += 4
        i += size_lw * 4
    else:
        break

# Find the load address from HUNK_HEADER
i2 = 0
load_base = 0
while i2 < len(rom) - 4:
    htype = struct.unpack_from('>I', rom, i2)[0]
    i2 += 4
    if htype == 0x3F3:  # HUNK_RELOC32
        break
    if htype == 0x3E8:  # HUNK_HEADER
        cnt = struct.unpack_from('>I', rom, i2)[0]; i2 += 4
        i2 += 4  # skip first_hunk
        i2 += 4  # skip last_hunk
        load_base = struct.unpack_from('>I', rom, i2)[0] & 0x3FFFFFFF
        i2 += 4
        break
    i2 += 4

# Use capstone for disassembly
import capstone
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)
md.detail = True

print('Code base=0x%X, size=0x%X' % (load_base, len(code)))

# Scan for LONG-size immediate instructions with (d16,An) EA
# b0 in {0x00,0x02,0x04,0x06,0x0A,0x0C}, b1 in 0xA8-0xAF
# These are 8-byte instructions: opcode(2) + imm32(4) + d16(2)
# Unicorn likely executes only 4 bytes (opcode + low 16 of imm32), leaving 4 trailing bytes.
# LONG (d8,An,Xn): b1 in 0xB0-0xB7

ALL_IMM_OPS = {0x00, 0x02, 0x04, 0x06, 0x0A, 0x0C}

print('\n=== LONG-size (d16,An) 8-byte immediate instructions (NOT hooked): ===')
found_long = []
n = len(code)
i = 0
while i < n - 7:
    b0 = code[i]; b1 = code[i+1]
    if b0 in ALL_IMM_OPS and 0xA8 <= b1 <= 0xAF:
        an_reg = b1 & 0x07
        imm32 = struct.unpack_from('>I', code, i+2)[0]
        raw_d16 = struct.unpack_from('>H', code, i+6)[0]
        d16 = raw_d16 if raw_d16 < 0x8000 else raw_d16 - 0x10000
        addr = load_base + i
        # Get disassembly
        dis_list = list(md.disasm(code[i:i+8], addr))
        dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
        # What are the 4 trailing bytes (positions i+4 to i+7)?
        trail4 = code[i+4:i+8]
        trail_dis_list = list(md.disasm(trail4, addr+4))
        trail_dis = []
        ti = 0
        while ti < len(trail4):
            tl = list(md.disasm(trail4[ti:], addr+4+ti))
            if tl:
                trail_dis.append('%s %s' % (tl[0].mnemonic, tl[0].op_str))
                ti += tl[0].size
            else:
                trail_dis.append('???(%02X%02X)' % (trail4[ti], trail4[ti+1]) if ti+1 < len(trail4) else '???')
                break
        found_long.append((addr, an_reg, imm32, d16, dis, trail_dis, trail4.hex()))
        i += 8; continue
    i += 2

print('Found %d LONG-size (d16,An) immediate instructions' % len(found_long))
for addr, an_reg, imm32, d16, dis, trail_dis, trail_hex in found_long[:30]:
    print('  0x%05X: %-40s  trail=[%s] (%s)' % (addr, dis, ' | '.join(trail_dis), trail_hex))

# Also scan for LONG-size (An,Xn): b1 in 0xB0-0xB7
print('\n=== LONG-size (An,Xn) 8-byte immediate instructions (NOT hooked): ===')
found_long_xn = []
i = 0
while i < n - 7:
    b0 = code[i]; b1 = code[i+1]
    if b0 in ALL_IMM_OPS and 0xB0 <= b1 <= 0xB7:
        an_reg = b1 & 0x07
        imm32 = struct.unpack_from('>I', code, i+2)[0]
        ext = struct.unpack_from('>H', code, i+6)[0]
        addr = load_base + i
        dis_list = list(md.disasm(code[i:i+8], addr))
        dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
        trail4 = code[i+4:i+8]
        trail_dis = []
        ti = 0
        while ti < len(trail4):
            tl = list(md.disasm(trail4[ti:], addr+4+ti))
            if tl:
                trail_dis.append('%s %s' % (tl[0].mnemonic, tl[0].op_str))
                ti += tl[0].size
            else:
                trail_dis.append('???'); break
        found_long_xn.append((addr, dis, trail_dis, trail4.hex()))
        i += 8; continue
    i += 2

print('Found %d LONG-size (An,Xn) immediate instructions' % len(found_long_xn))
for addr, dis, trail_dis, trail_hex in found_long_xn[:30]:
    print('  0x%05X: %-40s  trail=[%s] (%s)' % (addr, dis, ' | '.join(trail_dis), trail_hex))

# Also scan for BYTE-size (b1 in 0x28-0x37) — these are also NOT hooked
print('\n=== BYTE-size immediate instructions with (d16/An,Xn) EA (NOT hooked): ===')
found_b = []
i = 0
while i < n - 5:
    b0 = code[i]; b1 = code[i+1]
    if b0 in ALL_IMM_OPS and 0x28 <= b1 <= 0x37:
        an_reg = b1 & 0x07
        mode = 'd16' if b1 <= 0x2F else 'anXn'
        imm8 = code[i+3]
        addr = load_base + i
        dis_list = list(md.disasm(code[i:i+6], addr))
        dis = dis_list[0].mnemonic + ' ' + dis_list[0].op_str if dis_list else '???'
        trail2 = code[i+4:i+6]
        tl = list(md.disasm(trail2, addr+4))
        trail_dis = ('%s %s' % (tl[0].mnemonic, tl[0].op_str)) if tl else '???'
        # Dangerous: modifies address register
        dangerous = ('movea' in trail_dis or 'adda' in trail_dis or 'suba' in trail_dis)
        found_b.append((addr, dis, trail_dis, dangerous, trail2.hex()))
        i += 6; continue
    i += 2

print('Found %d byte-size (d16/An,Xn) 6-byte instructions' % len(found_b))
for addr, dis, trail_dis, dangerous, trail_hex in found_b[:30]:
    flag = ' <== DANGEROUS (modifies An)' if dangerous else ''
    print('  0x%05X: %-40s  trail=[%s] (%s)%s' % (addr, dis, trail_dis, trail_hex, flag))

# Special: find long-size instructions whose trailing 4 bytes contain MOVEA or SUBA modifying A4
print('\n=== LONG-size instructions with A4-modifying trailing bytes: ===')
for addr, an_reg, imm32, d16, dis, trail_dis, trail_hex in found_long:
    if 'a4' in ' '.join(trail_dis).lower():
        print('  DANGER 0x%05X: %s  trail=%s (%s)' % (addr, dis, trail_dis, trail_hex))

print('\n=== All instructions (any size) that appear to write to A4 via trailing bytes: ===')
for addr, dis, trail_dis, dangerous, trail_hex in found_b:
    if 'a4' in trail_dis.lower():
        print('  0x%05X: %s  trail=[%s]' % (addr, dis, trail_dis))
