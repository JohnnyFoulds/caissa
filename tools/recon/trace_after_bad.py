"""Trace all instructions after second ??? at 0x79BC until A4 changes."""
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
cpu.hook_add(HOOK_MEM_INVALID, mi)

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

cpu.hook_add(HOOK_CODE, lc, begin=0x820C, end=0x820C)
cpu.hook_add(HOOK_CODE, pc_hook, begin=0x8220, end=0x8220)
for _a in _BYPASS_NOOP:
    cpu.hook_add(HOOK_CODE, noop, begin=_a, end=_a)

_cmpiw_info = _scan_cmpiw(code, base=code_r.load_address)
def _hook_cmpiw(_emu, addr, _sz, _u=None):
    info = _cmpiw_info.get(addr)
    if info is None: return
    op, mode, an_reg, imm16, d16_or_ext = info
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
            if not xn_long:
                xn_raw = xn_raw & 0xFFFF
                if xn_raw >= 0x8000: xn_raw -= 0x10000
            ea_addr = (an_val + xn_raw + disp8) & 0xFFFFFFFF
        raw = bytes(cpu.mem_read(ea_addr, 2))
        ea_u = (raw[0] << 8) | raw[1]
        result_u = (ea_u - imm16) & 0xFFFF
        n_flag = 1 if result_u >= 0x8000 else 0; z_flag = 1 if result_u == 0 else 0
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
    if caddr not in {0x820C, 0x8220} and info[0] == 'cmp':
        cpu.hook_add(HOOK_CODE, _hook_cmpiw, begin=caddr, end=caddr)

md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

_qcount = [0]
_tracing = [False]
_trace = []
_prev_a4 = [A4]
_stop = [False]

uc = cpu._uc

def global_trace(emu, addr, sz, _u):
    if _stop[0]:
        return
    a4_ = emu.reg_read(M68K.UC_M68K_REG_A4)

    if _tracing[0]:
        try:
            b = bytes(emu.mem_read(addr, 8))
            ins = list(md.disasm(b, addr))
            dis = (ins[0].mnemonic + ' ' + ins[0].op_str + f'[{ins[0].size}]') if ins else f'???[{sz}]'
        except:
            b = b'\x00' * 8
            dis = f'???[{sz}]'
        _trace.append((addr, a4_, dis))
        if a4_ != _prev_a4[0] or len(_trace) >= 50:
            print(f"Trace ({len(_trace)} steps until A4 change or 50-step limit):")
            for i, (pc_, a4v, d) in enumerate(_trace):
                marker = " <-- A4 CHANGE" if a4v != A4 else ""
                print(f"  [{i:3d}] PC=0x{pc_:08X} A4=0x{a4v:08X} {d}{marker}")
            _stop[0] = True
            emu.emu_stop()
            return
        _prev_a4[0] = a4_
    else:
        if addr == 0x79BC:
            try:
                b = bytes(emu.mem_read(addr, 8))
                ins = list(md.disasm(b, addr))
                if not ins:
                    _qcount[0] += 1
                    a7_ = emu.reg_read(M68K.UC_M68K_REG_A7)
                    print(f"??? #{_qcount[0]} at 0x79BC bytes={b[:6].hex()} A7=0x{a7_:08X} A4=0x{a4_:08X}")
                    if _qcount[0] >= 2:
                        print("  --> Arming trace for next 50 instructions")
                        _tracing[0] = True
            except:
                pass

uc.hook_add(unicorn.UC_HOOK_CODE, global_trace)

print("Running...")
sys.stdout.flush()
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000_000)
    print(f"Done PC=0x{uc.reg_read(M68K.UC_M68K_REG_PC):X}")
except Exception as e:
    if not _stop[0]:
        print(f"Exception: {e}")
