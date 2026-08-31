"""Capture ALL writes to 0x79B0-0x79D0, then show final byte state."""
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

# Track writes to 0x79B0-0x79D0
_writes = {}  # addr -> list of (val, pc_of_writer)
_stop = [False]

uc = cpu._uc

def write_watcher(emu, access, addr, sz, val, _u):
    if _stop[0]: return
    if 0x79B0 <= addr <= 0x79CF:
        pc_ = emu.reg_read(M68K.UC_M68K_REG_PC)
        if addr not in _writes:
            _writes[addr] = []
        _writes[addr].append((val & 0xFF, pc_))

uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_watcher)

# Also: hook the skip-invalid at 0x79BC to prevent A4 corruption so monitoring can continue
def hook_skip_invalid(emu, addr, sz, _u):
    if _stop[0]: return
    try:
        b4 = bytes(emu.mem_read(addr, 4))
        ins = list(md.disasm(b4, addr))
        if not ins:
            emu.reg_write(M68K.UC_M68K_REG_PC, addr + 2)
    except: pass

uc.hook_add(unicorn.UC_HOOK_CODE, hook_skip_invalid, begin=0x79BC, end=0x79BC)

# Stop when A1 is well past 0x79C8 (decompressor has fully overwritten the loop)
# Monitor A1 to detect when it passes 0x79D0
def a1_watcher(emu, addr, sz, _u):
    if _stop[0]: return
    a1 = emu.reg_read(M68K.UC_M68K_REG_A1)
    if a1 > 0x79D0 and a1 < 0x79FF:
        print(f"A1 past 0x79D0: A1=0x{a1:08X} at PC=0x{addr:08X}")
        # Dump current state of 0x79B0-0x79D0
        try:
            region = bytes(emu.mem_read(0x79B0, 0x20))
            print(f"Memory 0x79B0-0x79CF: {region.hex()}")
        except: pass
        _stop[0] = True
        emu.emu_stop()

uc.hook_add(unicorn.UC_HOOK_CODE, a1_watcher)

print("Watching writes to 0x79B0-0x79CF...")
sys.stdout.flush()
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000_000)
    pc_ = uc.reg_read(M68K.UC_M68K_REG_PC)
    a1_ = uc.reg_read(M68K.UC_M68K_REG_A1)
    print(f"Stopped: PC=0x{pc_:08X} A1=0x{a1_:08X}")
except Exception as e:
    pc_ = uc.reg_read(M68K.UC_M68K_REG_PC)
    a1_ = uc.reg_read(M68K.UC_M68K_REG_A1)
    print(f"Exception: {e} PC=0x{pc_:08X} A1=0x{a1_:08X}")

# Show final write sequence per address
print("\n=== Write history for 0x79B0-0x79CF ===")
for addr in sorted(_writes.keys()):
    vals = [f"0x{v:02X}(PC={p:05X})" for v, p in _writes[addr][:5]]
    if len(_writes[addr]) > 5:
        vals.append(f"...({len(_writes[addr])} total)")
    final = _writes[addr][-1][0] if _writes[addr] else -1
    print(f"  0x{addr:05X}: {' '.join(vals)}  final=0x{final:02X}")

# Show final memory state
print("\n=== Final bytes 0x79B0-0x79CF ===")
try:
    b = bytes(uc.mem_read(0x79B0, 0x20))
    print(f"  {b.hex()}")
    for off in range(0, 0x20, 2):
        addr = 0x79B0 + off
        b2 = b[off:off+8]
        ins = list(md.disasm(b2, addr))
        if ins:
            print(f"  0x{addr:05X}: {ins[0].mnemonic} {ins[0].op_str} ({ins[0].size}b) bytes={b2[:ins[0].size].hex()}")
        else:
            print(f"  0x{addr:05X}: ??? bytes={b2[:2].hex()}")
except Exception as e:
    print(f"  Read error: {e}")
