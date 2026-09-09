"""Minimal test: does Unicorn mis-decode D48B or corrupt A4 in this code sequence?"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
import unicorn, unicorn.m68k_const as M68K, struct, capstone

CODE_BASE = 0x79B4

# Exact ROM bytes at 0x79B4 (from the ROM dump)
# tst.l d6 / beq / moveq / move.b / lsl.w / add.l a3,d2 / movea.l d2,a2 / moveq / move.b (a2)+,d2
rom_bytes = bytes.fromhex(
    '4a8667de74001400e54ad48b24427400141a672612da53869242b27c00086d04'
)

SENTINEL = 0x80000
# Layout: 0x79B4 = code, 0x80000 = sentinel (RTS)

uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(M68K.UC_CPU_M68K_M68000)
uc.mem_map(0, 0x200000)  # single 2MB region
uc.mem_write(CODE_BASE, rom_bytes)
uc.mem_write(SENTINEL, b'\x4E\x75')  # RTS

# Set up registers
A4 = 0x7FFE
A3 = 0x1000   # dummy A3 — table base
D6 = 1        # D6 != 0 so tst.l d6 doesn't branch
D0 = 0        # piece index 0
uc.reg_write(M68K.UC_M68K_REG_A4, A4)
uc.reg_write(M68K.UC_M68K_REG_A3, A3)
uc.reg_write(M68K.UC_M68K_REG_D6, D6)
uc.reg_write(M68K.UC_M68K_REG_D0, D0)

sp = 0x1F0000 - 4; uc.mem_write(sp, struct.pack('>I', SENTINEL))
uc.reg_write(M68K.UC_M68K_REG_A7, sp)

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)
prev = {r: uc.reg_read(r) for r in [M68K.UC_M68K_REG_A0, M68K.UC_M68K_REG_A1, M68K.UC_M68K_REG_A2,
                                      M68K.UC_M68K_REG_A3, M68K.UC_M68K_REG_A4, M68K.UC_M68K_REG_A5,
                                      M68K.UC_M68K_REG_D0, M68K.UC_M68K_REG_D1, M68K.UC_M68K_REG_D2]}

def hook(e, addr, sz, _u):
    regs = {r: e.reg_read(r) for r in [M68K.UC_M68K_REG_A0, M68K.UC_M68K_REG_A1, M68K.UC_M68K_REG_A2,
                                         M68K.UC_M68K_REG_A3, M68K.UC_M68K_REG_A4, M68K.UC_M68K_REG_A5,
                                         M68K.UC_M68K_REG_D0, M68K.UC_M68K_REG_D1, M68K.UC_M68K_REG_D2]}
    try:
        raw = bytes(e.mem_read(addr, 6))
        ins = list(md.disasm(raw, addr))
        dis = ins[0].mnemonic + ' ' + ins[0].op_str if ins else '???'
    except: dis = '???'
    changes = []
    for r, v in regs.items():
        name = M68K.uc_reg_name(r).upper() if hasattr(M68K, 'uc_reg_name') else str(r)
        # Map reg IDs to names manually
        names = {
            M68K.UC_M68K_REG_A4: 'A4',
            M68K.UC_M68K_REG_A3: 'A3', M68K.UC_M68K_REG_A2: 'A2', M68K.UC_M68K_REG_A1: 'A1',
            M68K.UC_M68K_REG_D0: 'D0', M68K.UC_M68K_REG_D1: 'D1', M68K.UC_M68K_REG_D2: 'D2',
        }
        rname = names.get(r, 'R?')
        if v != prev.get(r, 0):
            changes.append('%s:0x%X->0x%X' % (rname, prev[r], v))
    if changes:
        print('  0x%X [%-30s] CHANGED: %s' % (addr, dis, ' '.join(changes)), flush=True)
    prev.update(regs)

uc.hook_add(unicorn.UC_HOOK_CODE, hook)

print('Running minimal test with ROM bytes at 0x79B4:')
print('Bytes:', rom_bytes.hex())
print('A4=%X A3=%X D6=%X D0=%X' % (A4, A3, D6, D0))
try:
    uc.emu_start(CODE_BASE, SENTINEL, count=20)
    pc = uc.reg_read(M68K.UC_M68K_REG_PC)
    a4 = uc.reg_read(M68K.UC_M68K_REG_A4)
    print('Done. PC=0x%X A4=0x%X' % (pc, a4))
except Exception as e:
    pc = uc.reg_read(M68K.UC_M68K_REG_PC)
    a4 = uc.reg_read(M68K.UC_M68K_REG_A4)
    print('CRASH %s PC=0x%X A4=0x%X' % (e, pc, a4))
