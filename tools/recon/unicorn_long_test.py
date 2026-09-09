"""Test Unicorn's behavior with LONG-size immediate instructions (8-byte encoding).

ADDI.L #imm32, (d16,An) = 8 bytes: opcode(2) + imm32(4) + d16(2)
Does Unicorn advance PC by 8 (correct) or 4/6 (bug)?
"""
import unicorn, unicorn.m68k_const as M68K, struct, capstone

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

def make_uc():
    uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(M68K.UC_CPU_M68K_M68000)
    uc.mem_map(0, 0x100000)
    return uc

def dis(data, addr):
    ins = list(md.disasm(data, addr))
    return (ins[0].mnemonic + ' ' + ins[0].op_str + ' [%d bytes]' % ins[0].size) if ins else '???'

# Test 1: ADDI.L #$1234, $10(A0) at address 0x1000
# Expected encoding: 06 A8 00 00 12 34 00 10
# b0=0x06 (ADDI), b1=0xA8 (LONG, d16,A0), imm32=0x00001234, d16=0x0010
print('=== Test 1: ADDI.L #$1234, $10(A0) ===')
code1 = bytes([0x06, 0xA8, 0x00, 0x00, 0x12, 0x34, 0x00, 0x10])
print('Instruction bytes:', code1.hex())
print('Expected disasm:', dis(code1, 0x1000))
print()

# After ADDI.L, memory[$10+A0] should be 0x00001234 (assuming was 0)
# RTS at 0x1008 to end
uc1 = make_uc()
# A0 = 0x2000; memory at 0x2010 = 0
uc1.reg_write(M68K.UC_M68K_REG_A0, 0x2000)
uc1.mem_write(0x2010, b'\x00\x00\x00\x00')
# Trap instruction if trailing bytes would execute wrongly
# After ADDI.L: byte 8 should be RTS. Before that: byte 8-9 = d16 = 0x0010
# If PC doesn't advance 8 but only 4: PC = 0x1004, next executes bytes from 0x1004
# bytes at 0x1004 = 12 34 00 10 (imm32 lo + d16)
# 12 34 = move.b d2, (a2)
# So we put a marker to detect if this executes
uc1.reg_write(M68K.UC_M68K_REG_A2, 0x5000)
uc1.reg_write(M68K.UC_M68K_REG_D2, 0xAB)
uc1.mem_write(0x5000, b'\x00')  # start = 0
uc1.mem_write(0x1000, code1 + b'\x4E\x75')  # ADDI.L + RTS

sp = 0xF000 - 4; uc1.mem_write(sp, struct.pack('>I', 0x9000)); uc1.reg_write(M68K.UC_M68K_REG_A7, sp)

trace = []
def hook1(e, addr, sz, _):
    try:
        raw = bytes(e.mem_read(addr, 8))
        d = dis(raw, addr)
    except: d = '???'
    trace.append('  PC=0x%04X  %s' % (addr, d))

uc1.hook_add(unicorn.UC_HOOK_CODE, hook1)
try:
    uc1.emu_start(0x1000, 0x9000, count=10)
except: pass
final_pc = uc1.reg_read(M68K.UC_M68K_REG_PC)
mem2010 = struct.unpack('>I', bytes(uc1.mem_read(0x2010, 4)))[0]
mem5000 = uc1.mem_read(0x5000, 1)[0]
print('Execution trace:')
for t in trace: print(t)
print('Final PC=0x%X' % final_pc)
print('[0x2010] = 0x%08X (expected 0x1234 if correct)' % mem2010)
print('[0x5000] = 0x%X (expected 0x00 if no trailing; 0xAB if "move.b d2,(a2)" fired)' % mem5000)

print()

# Test 2: CMPI.L #$0, $14(A0) at 0x1000
# From scan: 0x05310 cmpi.l #$10, $14(a0) → trail=[ori.b #$14, (a0)]
# Bytes: 0C A8 00 00 00 10 00 14
print('=== Test 2: CMPI.L #$10, $14(A0) at 0x1000 ===')
code2 = bytes([0x0C, 0xA8, 0x00, 0x00, 0x00, 0x10, 0x00, 0x14])
print('Instruction bytes:', code2.hex())
print('Expected disasm:', dis(code2, 0x1000))
print()

uc2 = make_uc()
uc2.reg_write(M68K.UC_M68K_REG_A0, 0x2000)
uc2.mem_write(0x2014, struct.pack('>I', 0x10))  # [A0+$14] = 0x10, equal to #$10
uc2.mem_write(0x1000, code2 + b'\x4E\x75')
sp = 0xF000 - 4; uc2.mem_write(sp, struct.pack('>I', 0x9000)); uc2.reg_write(M68K.UC_M68K_REG_A7, sp)

trace2 = []
def hook2(e, addr, sz, _):
    try:
        raw = bytes(e.mem_read(addr, 8))
        d = dis(raw, addr)
    except: d = '???'
    trace2.append('  PC=0x%04X  %s' % (addr, d))

uc2.hook_add(unicorn.UC_HOOK_CODE, hook2)
try:
    uc2.emu_start(0x1000, 0x9000, count=10)
except: pass
final_pc2 = uc2.reg_read(M68K.UC_M68K_REG_PC)
sr2 = uc2.reg_read(M68K.UC_M68K_REG_SR)
print('Execution trace:')
for t in trace2: print(t)
print('Final PC=0x%X' % final_pc2)
print('SR=0x%04X (Z-flag=%d, expected Z=1 since #$10 == [$14])' % (sr2, (sr2>>2)&1))
print('PC after CMPI.L should be 0x1008 if correct, 0x1004 if bug (4-byte advance)')

print()

# Test 3: ADDI.L with A4-relative — check if it actually corrupts memory
# 0x01850: addi.l #$9c40, -$3556(a4)
# bytes: 06 AC 00 00 9C 40 CA AA
# Correct: adds 0x9C40 to memory[A4-0x3556]
# If bug: trail bytes 9C40 CAAA execute as:
#   9C40 = sub.w d0, d6
#   CAAA = and.l -(a2), d5 -- wait is that right?
print('=== Test 3: ADDI.L #$9C40, -$3556(A4) at 0x1000 ===')
code3 = bytes([0x06, 0xAC, 0x00, 0x00, 0x9C, 0x40, 0xCA, 0xAA])
print('Instruction bytes:', code3.hex())
print('Expected disasm:', dis(code3, 0x1000))
print()

# Trail bytes if PC advances only 4:
# 0x1004: 9C 40 CA AA
# 9C40 = sub.w d0, d6
# CAAA = and.l -(a2), d5 ??? or something
# Let's see what actually happens
A4_VAL = 0x7FFE
uc3 = make_uc()
uc3.reg_write(M68K.UC_M68K_REG_A4, A4_VAL)
ea = (A4_VAL - 0x3556) & 0xFFFFFFFF
uc3.mem_write(ea, struct.pack('>I', 0))  # [A4-0x3556] = 0
uc3.mem_write(0x1000, code3 + b'\x4E\x75')
sp = 0xF000 - 4; uc3.mem_write(sp, struct.pack('>I', 0x9000)); uc3.reg_write(M68K.UC_M68K_REG_A7, sp)
# Marker registers
uc3.reg_write(M68K.UC_M68K_REG_D6, 0x1234)

trace3 = []
def hook3(e, addr, sz, _):
    try:
        raw = bytes(e.mem_read(addr, 8))
        d = dis(raw, addr)
    except: d = '???'
    trace3.append('  PC=0x%04X  %s' % (addr, d))

uc3.hook_add(unicorn.UC_HOOK_CODE, hook3)
try:
    uc3.emu_start(0x1000, 0x9000, count=10)
except: pass
final_pc3 = uc3.reg_read(M68K.UC_M68K_REG_PC)
d6_after = uc3.reg_read(M68K.UC_M68K_REG_D6)
mem_ea = struct.unpack('>I', bytes(uc3.mem_read(ea, 4)))[0]
print('Execution trace:')
for t in trace3: print(t)
print('Final PC=0x%X' % final_pc3)
print('[A4-0x3556] = 0x%08X (expected 0x9C40 if correct; 0 if wrong operation)' % mem_ea)
print('D6 = 0x%08X (expected 0x1234 if no trailing; changed if sub.w fired)' % d6_after)
print()
print('PC after ADDI.L should be:')
print('  0x1008 if correct (advances 8 bytes)')
print('  0x1004 if PC-advance bug (advances 4 bytes, leaving 4 trailing)')
print('  0x100A if PC-advance bug (advances 6 bytes, leaving 2 trailing)')
