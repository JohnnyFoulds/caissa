"""Dump the raw bytes at 0x79BC every time the instruction there fires, plus surrounding context."""
import sys, struct, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
logging.basicConfig(level=logging.CRITICAL)

import unicorn, unicorn.m68k_const as M68K, capstone

from Code.Retro.Bridge import A4 as _A4_VALUE, AI_OUTER_DRIVER_ADDR, PLAYER_TYPE_BASE, Bridge
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Think import _scan_cmpiw, _BYPASS_NOOP
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Traps import ALLOC_POOL, ALLOC_POOL_SIZE, AmigaTraps
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID

ROM_PATH = Path(default_rom_path())
rom_bytes = ROM_PATH.read_bytes()
regions = parse_amiga_hunk(rom_bytes)
code_r = next(r for r in regions if r.label == 'HUNK_CODE' and r.size > 0)
code = rom_bytes[code_r.offset:code_r.offset + code_r.size]

cpu = Unicorn68k()
cpu.map_region(0, 0x200000)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_bytes[r.offset:r.offset + r.size])
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()

A4 = _A4_VALUE; SENTINEL = 0xFFFF0000
bridge = Bridge(cpu)
bridge.clear_best_move()
bridge.write_position('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1')
bridge.set_computer_color(1)
cpu.mem_write(PLAYER_TYPE_BASE + 2, struct.pack('>H', 1))
sp = 0x1F0000 - 4; cpu.mem_write(sp, struct.pack('>I', SENTINEL))
cpu.reg_write('A4', A4); cpu.reg_write('A7', sp)
cpu.mem_write(A4 - 0x35B4, struct.pack('>H', 0))
cpu.mem_write(A4 - 0x782C, struct.pack('>H', 0))

_lc = [0]
def lc(_e, a, _s, _u=None):
    try:
        a4_ = cpu.reg_read('A4')
        raw = bytes(cpu.mem_read((a4_ - 0x35A4) & 0xFFFFFFFF, 2))
        flag = (raw[0] << 8) | raw[1]
        cpu.reg_write('PC', 0x8228 if flag != 2 or _lc[0] >= 1 else 0x8214)
        if flag == 2: _lc[0] += 1
    except: cpu.reg_write('PC', 0x8228)

def pc_hook(_e, a, _s, _u=None):
    try:
        a0_ = cpu.reg_read('A0'); d0_ = cpu.reg_read('D0')
        d0s = d0_ if d0_ < 0x80000000 else d0_ - 0x100000000
        val = struct.unpack('>H', bytes(cpu.mem_read((a0_ + d0s) & 0xFFFFFFFF, 2)))[0]
        cpu.reg_write('PC', 0x81E4 if val == 1 else 0x8228)
    except: cpu.reg_write('PC', 0x8228)

def noop(_e, a, _s, _u=None):
    try:
        a7 = cpu.reg_read('A7'); ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu.reg_write('A7', a7 + 4); cpu.reg_write('PC', ret)
    except: pass

_mapped = set()
def mi(_e, _a, addr, _s, _v, _u=None):
    page = addr & 0xFFFF0000
    if page not in _mapped:
        try:
            cpu.map_region(page, 0x10000)
            cpu.mem_write(page, bytes(0x10000))
            _mapped.add(page)
        except Exception: pass
    return True

cpu.hook_add(HOOK_CODE, lc, begin=0x820C, end=0x820C)
cpu.hook_add(HOOK_CODE, pc_hook, begin=0x8220, end=0x8220)
for _a in _BYPASS_NOOP:
    cpu.hook_add(HOOK_CODE, noop, begin=_a, end=_a)
cpu.hook_add(HOOK_MEM_INVALID, mi)

# CMP-only hooks
_cmpiw_info = _scan_cmpiw(code, base=code_r.load_address)
_CMPIW_SKIP = frozenset({0x820C, 0x8220})

def _hook_cmpiw(_emu, addr, _sz, _u=None):
    info = _cmpiw_info.get(addr)
    if info is None: return
    op, mode, an_reg, imm16, d16_or_ext = info
    if op != 'cmp': return
    try:
        an_val = cpu.reg_read(f'A{an_reg}')
        if mode == 'd16':
            ea_addr = (an_val + d16_or_ext) & 0xFFFFFFFF
        else:
            ext = d16_or_ext
            xn_is_an = (ext >> 15) & 1; xn_reg = (ext >> 12) & 0x07
            xn_long = (ext >> 11) & 1; disp8 = ext & 0xFF
            if disp8 >= 0x80: disp8 -= 256
            xn_name = f"A{xn_reg}" if xn_is_an else f"D{xn_reg}"
            xn_raw = cpu.reg_read(xn_name)
            if xn_long:
                if xn_raw >= 0x80000000: xn_raw -= 0x100000000
            else:
                xn_raw = xn_raw & 0xFFFF
                if xn_raw >= 0x8000: xn_raw -= 0x10000
            ea_addr = (an_val + xn_raw + disp8) & 0xFFFFFFFF
        raw = bytes(cpu.mem_read(ea_addr, 2))
        ea_u = (raw[0] << 8) | raw[1]
        result_u = (ea_u - imm16) & 0xFFFF
        n_flag = 1 if result_u >= 0x8000 else 0
        z_flag = 1 if result_u == 0 else 0
        c_flag = 1 if ea_u < imm16 else 0
        ea_s = ea_u if ea_u < 0x8000 else ea_u - 0x10000
        imm_s = imm16 if imm16 < 0x8000 else imm16 - 0x10000
        v_flag = 1 if not (-0x8000 <= ea_s - imm_s <= 0x7FFF) else 0
        sr_old = cpu.reg_read('SR')
        new_sr = ((sr_old & ~0x0F) | (n_flag << 3) | (z_flag << 2) | (v_flag << 1) | c_flag) & 0xFFFF
        cpu.reg_write('SR', new_sr)
        cpu.reg_write('PC', addr + 6)
    except Exception:
        cpu.reg_write('PC', addr + 6)

for caddr, info in _cmpiw_info.items():
    if caddr not in _CMPIW_SKIP and info[0] == 'cmp':
        cpu.hook_add(HOOK_CODE, _hook_cmpiw, begin=caddr, end=caddr)

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

# Targeted hook at 0x79BC: dump bytes and register state
_pass_count = [0]
_stop = [False]

def dump_79bc(emu, addr, sz, _u):
    if _stop[0]:
        return
    try:
        raw8 = bytes(emu.mem_read(addr, 8))
        raw12 = bytes(emu.mem_read(addr - 4, 12))  # 4 bytes before too
    except:
        raw8 = b'\x00' * 8; raw12 = b'\x00' * 12
    # Disassemble
    ins = list(md.disasm(raw8, addr))
    dis = (ins[0].mnemonic + ' ' + ins[0].op_str + ' [%d bytes]' % ins[0].size) if ins else '???'

    a4 = emu.reg_read(M68K.UC_M68K_REG_A4)
    a2 = emu.reg_read(M68K.UC_M68K_REG_A2)
    a3 = emu.reg_read(M68K.UC_M68K_REG_A3)
    d2 = emu.reg_read(M68K.UC_M68K_REG_D2)
    d0 = emu.reg_read(M68K.UC_M68K_REG_D0)

    _pass_count[0] += 1
    print('Pass %d at 0x79BC:' % _pass_count[0])
    print('  Bytes at 0x79B8..0x79C4: %s' % raw12.hex())
    print('  Bytes at 0x79BC: %s' % raw8.hex())
    print('  Disasm from 0x79BC: %s' % dis)
    print('  Registers: A4=0x%X A2=0x%X A3=0x%X D0=0x%X D2=0x%X' % (a4,a2,a3,d0,d2))

    # Also disassemble 4 bytes before
    prev4 = bytes(emu.mem_read(addr-4, 4))
    ins_prev = list(md.disasm(prev4, addr-4))
    dis_prev = (ins_prev[0].mnemonic+' '+ins_prev[0].op_str) if ins_prev else '???'
    print('  Disasm at 0x79B8: %s' % dis_prev)
    print()

    if _pass_count[0] >= 3:
        _stop[0] = True
        emu.emu_stop()

uc = cpu._uc
uc.hook_add(unicorn.UC_HOOK_CODE, dump_79bc, begin=0x79BC, end=0x79BC)

print('Dumping raw bytes at 0x79BC (CMP-only hooks)...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000_000)
    pc_ = uc.reg_read(M68K.UC_M68K_REG_PC)
    print('Stopped at PC=0x%X' % pc_)
except Exception as e:
    pc_ = uc.reg_read(M68K.UC_M68K_REG_PC)
    a4_ = uc.reg_read(M68K.UC_M68K_REG_A4)
    if not _stop[0]:
        print('CRASH %s PC=0x%X A4=0x%X' % (e, pc_, a4_))
