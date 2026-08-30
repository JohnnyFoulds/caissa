"""Test if UC_HOOK_MEM_WRITE fires at all in Unicorn 2."""
import unicorn, unicorn.m68k_const as mc, struct

uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_M68K_000)
uc.mem_map(0, 0x10000)
# clr.w $5000 (absolute address), then jmp back to halt via $FFFF
code = bytes([0x42, 0x78, 0x50, 0x00,   # clr.w $5000.w
              0x4e, 0x75])               # rts
uc.mem_write(0x1000, code)
uc.reg_write(mc.UC_M68K_REG_A7, 0x8000)
uc.mem_write(0x8000, b'\x00\x00\xFF\xFE')

writes = []
def wh(uc, access, addr, sz, val, ud):
    writes.append((addr, sz, val))
    print(f'  WRITE [0x{addr:04X}] sz={sz} val=0x{val:X}')

from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
def ch(uc, addr, sz, ud):
    print(f'  insn PC=0x{addr:04X}')

uc.hook_add(UC_HOOK_MEM_WRITE, wh)
uc.hook_add(UC_HOOK_CODE, ch)

print('Running...')
try:
    uc.emu_start(0x1000, 0xFFFE, count=5)
except Exception as e:
    print(f'exc: {e}')
print(f'Total writes: {len(writes)}')
