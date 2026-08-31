"""Find A4 corruption point - fires spy only after first 0x0C2CE visit."""
import sys, struct, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'bin'))
logging.basicConfig(level=logging.CRITICAL)
from Code.Retro.Bridge import A4 as _A4_VALUE, AI_OUTER_DRIVER_ADDR, PLAYER_TYPE_BASE, Bridge
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Think import _BYPASS_NOOP
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Traps import ALLOC_POOL, ALLOC_POOL_SIZE, AmigaTraps
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID, HOOK_MEM_WRITE
import unicorn, unicorn.m68k_const as M68K, capstone

ROM_PATH = Path(default_rom_path())
rom_bytes = ROM_PATH.read_bytes()
regions = parse_amiga_hunk(rom_bytes)
cpu = Unicorn68k()
cpu.map_region(0, 0x200000)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_bytes[r.offset:r.offset+r.size])
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

_lc=[0]; _nc=[0]; _mapped=set(); _spy_armed=[False]

def lc(_e,a,_s,_u=None):
    try:
        a4_=cpu.reg_read('A4'); raw=bytes(cpu.mem_read((a4_-0x35A4)&0xFFFFFFFF,2)); flag=(raw[0]<<8)|raw[1]
        cpu.reg_write('PC',0x8228 if flag!=2 or _lc[0]>=1 else 0x8214)
        if flag==2: _lc[0]+=1
    except: cpu.reg_write('PC',0x8228)

def pc_hook(_e,a,_s,_u=None):
    try:
        a0_=cpu.reg_read('A0'); d0_=cpu.reg_read('D0')
        d0s=d0_ if d0_<0x80000000 else d0_-0x100000000
        val=struct.unpack('>H',bytes(cpu.mem_read((a0_+d0s)&0xFFFFFFFF,2)))[0]
        cpu.reg_write('PC',0x81E4 if val==1 else 0x8228)
    except: cpu.reg_write('PC',0x8228)

def ac(_e,a,_s,_u=None):
    _nc[0]+=1
    if not _spy_armed[0]:
        _spy_armed[0] = True
        print('First node at insn ~{}'.format(_nc[0])); sys.stdout.flush()
    if _nc[0]>=5000:
        try: cpu.mem_write(A4-0x35B4,struct.pack('>H',1))
        except: pass

def noop(_e,a,_s,_u=None):
    try:
        a7=cpu.reg_read('A7'); ret=struct.unpack('>I',bytes(cpu.mem_read(a7,4)))[0]
        cpu.reg_write('A7',a7+4); cpu.reg_write('PC',ret)
    except: pass

def mi(_e,_a,addr,_s,_v,_u=None):
    page=addr&0xFFFF0000
    if page not in _mapped:
        try: cpu.map_region(page,0x10000); cpu.mem_write(page,bytes(0x10000)); _mapped.add(page)
        except: pass
    return True

cpu.hook_add(HOOK_CODE,lc,begin=0x820C,end=0x820C)
cpu.hook_add(HOOK_CODE,pc_hook,begin=0x8220,end=0x8220)
cpu.hook_add(HOOK_CODE,ac,begin=0x0C2CE,end=0x0C2CE)
for _a in _BYPASS_NOOP: cpu.hook_add(HOOK_CODE,noop,begin=_a,end=_a)
cpu.hook_add(HOOK_MEM_INVALID,mi)
cpu.hook_add(HOOK_MEM_WRITE,lambda *a:None)

md=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN+capstone.CS_MODE_M68K_000)
_log=[]; _prev=[A4]

def spy(_e,addr,_sz,_u=None):
    if not _spy_armed[0]: return
    a4_=_e.reg_read(M68K.UC_M68K_REG_A4)
    if a4_!=_prev[0]:
        try:
            raw=bytes(_e.mem_read(addr,8)); ins=list(md.disasm(raw,addr))
            dis=ins[0].mnemonic+' '+ins[0].op_str if ins else '???'
        except: dis='???'
        msg='0x{:05X}: A4 0x{:X}->0x{:X} | {}'.format(addr,_prev[0],a4_,dis)
        _log.append(msg); print(msg); sys.stdout.flush()
        _prev[0]=a4_
        if len(_log)>=6: _spy_armed[0]=False

uc=cpu._uc; uc.hook_add(unicorn.UC_HOOK_CODE,spy)

try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR,until=SENTINEL,count=500_000_000)
    print('OK nodes={}'.format(_nc[0]))
except Exception as e:
    pc_=uc.reg_read(M68K.UC_M68K_REG_PC)
    print('CRASH {} PC=0x{:X} nodes={}'.format(e,pc_,_nc[0]))
