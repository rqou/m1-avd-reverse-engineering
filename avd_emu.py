import struct
from unicorn import *
from unicorn.arm_const import *

##### piodma stuff

with open('frame_params.bin', 'rb') as f:
	frame_params = f.read()

##### helpers

HACK_WFI_ADDRESS = 0x3f8

def _ascii(s):
	s2 = ""
	for c in s:
		if c < 0x20 or c > 0x7e:
			s2 += "."
		else:
			s2 += chr(c)
	return s2

def hexdump(s, sep=" "):
	return sep.join(["%02x"%x for x in s])

def chexdump(s, st=0, abbreviate=True, indent="", print_fn=print):
	last = None
	skip = False
	for i in range(0,len(s),16):
		val = s[i:i+16]
		if val == last and abbreviate:
			if not skip:
				print_fn(indent+"%08x  *" % (i + st))
				skip = True
		else:
			print_fn(indent+"%08x  %s  %s  |%s|" % (
				i + st,
				hexdump(val[:8], ' ').ljust(23),
				hexdump(val[8:], ' ').ljust(23),
				_ascii(val).ljust(16)))
			last = val
			skip = False

def dump_all_regs(emu_):
	r0 = emu_.reg_read(UC_ARM_REG_R0)
	r1 = emu_.reg_read(UC_ARM_REG_R1)
	r2 = emu_.reg_read(UC_ARM_REG_R2)
	r3 = emu_.reg_read(UC_ARM_REG_R3)
	print(f"R0  = {r0:08X}\tR1  = {r1:08X}\tR2  = {r2:08X}\tR3  = {r3:08X}")
	r4 = emu_.reg_read(UC_ARM_REG_R4)
	r5 = emu_.reg_read(UC_ARM_REG_R5)
	r6 = emu_.reg_read(UC_ARM_REG_R6)
	r7 = emu_.reg_read(UC_ARM_REG_R7)
	print(f"R4  = {r4:08X}\tR5  = {r5:08X}\tR6  = {r6:08X}\tR7  = {r7:08X}")
	r8 = emu_.reg_read(UC_ARM_REG_R8)
	r9 = emu_.reg_read(UC_ARM_REG_R9)
	r10 = emu_.reg_read(UC_ARM_REG_R10)
	r11 = emu_.reg_read(UC_ARM_REG_R11)
	print(f"R8  = {r8:08X}\tR9  = {r9:08X}\tR10 = {r10:08X}\tR11 = {r11:08X}")
	r12 = emu_.reg_read(UC_ARM_REG_R12)
	sp = emu_.reg_read(UC_ARM_REG_SP)
	lr = emu_.reg_read(UC_ARM_REG_LR)
	pc = emu_.reg_read(UC_ARM_REG_PC)
	print(f"R12 = {r12:08X}\tSP  = {sp:08X}\tLR  = {lr:08X}\tPC  = {pc:08X}")

def save_dram(emu_, fn):
	dram_contents = emu_.mem_read(0x10000000, 0x10000)
	with open(fn, 'wb') as f:
		f.write(dram_contents)

def trigger_irq(emu_, irq):
	print(f"Triggering an IRQ {irq}")
	irq_handler = struct.unpack("<I", FIRMWARE[0x40 + irq*4:0x40 + irq*4 + 4])[0]
	print(f"\tThe handler is at {irq_handler:08x}")

	emu_.reg_write(UC_ARM_REG_LR, HACK_WFI_ADDRESS + 1)
	emu_.reg_write(UC_ARM_REG_PC, irq_handler)
	emu_.emu_start(irq_handler, 0)

with open('avd-12.3-lilyD-fw.bin', 'rb') as f:
	FIRMWARE = f.read()

##### MMIO emu logic

def write_vtor(addr, val):
	print(f"VTOR = {val:08x}")


nvic_enabled_irqs = [0] * 8

def write_isen(addr, val):
	for i in range(32):
		if val & (1 << i):
			reg_idx = (addr - 0xe000e100) // 4
			irq_line = reg_idx * 32 + i
			print(f"NVIC enabling IRQ {irq_line}")
			nvic_enabled_irqs[reg_idx] |= (1 << i)

def read_isen(addr):
	reg_idx = (addr - 0xe000e100) // 4
	return nvic_enabled_irqs[reg_idx]


cm3ctrl_enabled_irq0 = 0
cm3ctrl_enabled_irqs = [0] * 6

def write_cm3ctrl_irq_en_0(addr, val):
	global cm3ctrl_enabled_irq0
	old_val = cm3ctrl_enabled_irq0
	for i in range(14):
		if (not (old_val & (1 << i))) and (val & (1 << i)):
			print(f"CM3 control enabling IRQ {i}")
		if (old_val & (1 << i)) and (not (val & (1 << i))):
			print(f"CM3 control disabling IRQ {i}")
	cm3ctrl_enabled_irq0 = val

def read_cm3ctrl_irq_en_0(_addr):
	return cm3ctrl_enabled_irq0

def write_cm3ctrl_irq_en(addr, val):
	global cm3ctrl_enabled_irqs
	reg_idx = (addr - 0x50010014) // 4
	old_val = cm3ctrl_enabled_irqs[reg_idx]
	for i in range(32):
		if (not (old_val & (1 << i))) and (val & (1 << i)):
			print(f"CM3 control enabling IRQ {14 + reg_idx * 32 + i}")
		if (old_val & (1 << i)) and (not (val & (1 << i))):
			print(f"CM3 control disabling IRQ {14 + reg_idx * 32 + i}")
	cm3ctrl_enabled_irqs[reg_idx] = val

def read_cm3ctrl_irq_en(addr):
	reg_idx = (addr - 0x50010014) // 4
	return cm3ctrl_enabled_irqs[reg_idx]

cmd_idx = 0
def read_cm3ctrl_mbox0_retrieve(_addr):
	global cmd_idx
	ret = 0x1092ccc + cmd_idx * 0x60
	cmd_idx += 1
	return ret

def read_cm3ctrl_irq_status(addr):
	print(f"NOT IMPLEMENTED: CM3 IRQ status read {addr:08x}")

def write_cm3ctrl_irq_status(addr, val):
	if addr == 0x5001002c:
		for i in range(14):
			if val & (1 << i):
				print(f"CM3 control clearing IRQ {i}")
	else:
		reg_idx = (addr - 0x50010030) // 4
		for i in range(32):
			if val & (1 << i):
				print(f"CM3 control clearing IRQ {14 + reg_idx * 32 + i}")

def write_cm3ctrl_mbox1_submit(addr, val):
	print(f"mbox uc->ap got something! {val:08x}")
	real_addr = val + 0xef7_0000
	reply = emu.mem_read(real_addr, 0x60)
	chexdump(reply)

piodma_iova_lo = 0
piodma_iova_hi = 0
def write_piodma_iova_lo(_addr, val):
	global piodma_iova_lo
	piodma_iova_lo = val
def write_piodma_iova_hi(_addr, val):
	global piodma_iova_hi
	piodma_iova_hi = val
def write_piodma_command(_addr, val):
	piodma_iova = piodma_iova_hi << 32 | piodma_iova_lo
	print(f"piodma copy from descriptor @ {piodma_iova:016x} cmd {val:08x}")
	# TODO actually do a piodma copy

	# anything else not implemented
	assert val & 0xff == 0x11
	piodma_cmd_len = (val >> 8) & 0x3fffff

	piodma_pkt_word = struct.unpack("<I", frame_params[piodma_iova:piodma_iova + 4])[0]
	print(f"\tpacket word = {piodma_pkt_word:08x}")

	# anything else not implemented
	assert piodma_pkt_word & 0b11 == 0b01
	piodma_dst_addr = piodma_pkt_word & 0x3fffc
	piodma_pkt_len = (piodma_pkt_word >> 18) & 0xfff
	assert (piodma_pkt_word >> 30) & 0b11 == 0
	assert piodma_pkt_len + 2 == piodma_cmd_len

	assert piodma_dst_addr >= 0x20000 and piodma_dst_addr < 0x30000
	target_addr = 0x10000000 + piodma_dst_addr - 0x20000

	word_count = piodma_pkt_len + 1
	print(f"\tcopying {word_count} words to {target_addr:08x}")

	words = frame_params[piodma_iova + 4:piodma_iova + 4 + word_count * 4]
	emu.mem_write(target_addr, words)

def read_config_maybe_fifo_level_0(addr):
	print(f"WARN reading not-fully-understood register {addr:08x}")
	return 0x80
def read_config_maybe_fifo_level_1(addr):
	print(f"WARN reading not-fully-understood register {addr:08x}")
	return 0
def warn_write(addr, val):
	print(f"WARN unexpected write to register {addr:08x} = {val:08x}")

MMIOS = {
	0x40100034: (read_config_maybe_fifo_level_0, warn_write),
	0x40100038: (read_config_maybe_fifo_level_0, warn_write),
	0x4010003c: (read_config_maybe_fifo_level_0, warn_write),
	0x40100040: (read_config_maybe_fifo_level_0, warn_write),
	0x40100044: (read_config_maybe_fifo_level_0, warn_write),
	0x40100048: (read_config_maybe_fifo_level_0, warn_write),
	0x4010004c: (read_config_maybe_fifo_level_0, warn_write),
	0x40100050: (read_config_maybe_fifo_level_0, warn_write),
	0x40100054: (read_config_maybe_fifo_level_0, warn_write),
	0x40100058: (read_config_maybe_fifo_level_0, warn_write),
	0x4010005c: (read_config_maybe_fifo_level_1, warn_write),
	0x40100060: (read_config_maybe_fifo_level_1, warn_write),
	0x40100064: (read_config_maybe_fifo_level_1, warn_write),
	0x40100068: (read_config_maybe_fifo_level_1, warn_write),
	0x4010006c: (read_config_maybe_fifo_level_1, warn_write),
	0x40100070: (read_config_maybe_fifo_level_1, warn_write),
	0x40100074: (read_config_maybe_fifo_level_1, warn_write),
	0x40100078: (read_config_maybe_fifo_level_1, warn_write),
	0x4010007c: (read_config_maybe_fifo_level_1, warn_write),
	0x40100080: (read_config_maybe_fifo_level_1, warn_write),

	# Fake status to be done instantly, set no other bits
	0x40070004: (lambda _addr: 1, lambda _addr, _val: None),

	0x4007004c: (lambda _addr: piodma_iova_lo, write_piodma_iova_lo),
	0x40070050: (lambda _addr: piodma_iova_hi, write_piodma_iova_hi),
	0x40070054: (lambda _addr: 0xdeadbeef, write_piodma_command),

	0x50010010: (read_cm3ctrl_irq_en_0, write_cm3ctrl_irq_en_0),
	0x50010014: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010018: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x5001001c: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010020: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010024: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010028: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x5001002c: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x50010030: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x50010034: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x50010038: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x5001003c: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x50010040: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),
	0x50010044: (read_cm3ctrl_irq_status, write_cm3ctrl_irq_status),

	0x50010058: (read_cm3ctrl_mbox0_retrieve, lambda _addr, _val: None),
	0x5001005c: (lambda _addr: 0x20001, lambda _addr, _val: None),	# mbox1 status
	0x50010060: (lambda _addr: 0xdeadbeef, write_cm3ctrl_mbox1_submit),


	0xe000ed08: (lambda _addr: None, write_vtor),
	0xe000e100: (read_isen, write_isen),
	0xe000e104: (read_isen, write_isen),
	0xe000e108: (read_isen, write_isen),
	0xe000e10c: (read_isen, write_isen),
	0xe000e110: (read_isen, write_isen),
	0xe000e114: (read_isen, write_isen),
	0xe000e118: (read_isen, write_isen),
	0xe000e11c: (read_isen, write_isen),
}

MMIO_BLOCKS = [
	(0x40070000, 0x4000),	# PIODMA
	(0x40100000, 0x8000),	# Config
	(0x4010c000, 0x4000),	# DMA thingy
	(0x40400000, 0x4000),	# WrapCtrl
	(0x50010000, 0x4000),	# CM3Ctrl
	(0xe000c000, 0x4000),	# SCS
]

##### setup

emu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
emu.mem_map(0, 0x10000)				# IRAM
emu.mem_map(0x10000000, 0x10000)	# DRAM

emu.mem_write(0, FIRMWARE)

def hook_code(emu_, _addr, _sz, _data):
	# HACK: This doesn't do anything, just disables JIT to get accurate PCs
	pass

def hook_mmio(emu_, access, addr, sz, value, _data):
	if addr in MMIOS:
		if access == UC_MEM_READ:
			read_fn = MMIOS[addr][0]
			out_val = read_fn(addr)
			if out_val is not None:
				emu_.mem_write(addr, struct.pack("<I", out_val))
		elif access == UC_MEM_WRITE:
			write_fn = MMIOS[addr][1]
			write_fn(addr, value)
	else:
		pc = emu_.reg_read(UC_ARM_REG_PC)
		if access == UC_MEM_READ:
			print(f"UNKNOWN read @ PC {pc:08x} of size {sz} to register {addr:08x}")
		elif access == UC_MEM_WRITE:
			print(f"UNKNOWN write @ PC {pc:08x} of size {sz} to register {addr:08x} with value {value:08x}")

for (addr, len_) in MMIO_BLOCKS:
	emu.mem_map(addr, len_)
	emu.hook_add(UC_HOOK_MEM_READ, hook_mmio, begin=addr, end=addr + len_)
	emu.hook_add(UC_HOOK_MEM_WRITE, hook_mmio, begin=addr, end=addr + len_)

emu.hook_add(UC_HOOK_CODE, hook_code, begin=0, end=0xffffffff)

##### kick off!

initial_sp = struct.unpack("<I", FIRMWARE[0:4])[0]
initial_pc = struct.unpack("<I", FIRMWARE[4:8])[0]
print(f"Starting @ {initial_pc:08x} with SP {initial_sp:08x}")
emu.reg_write(UC_ARM_REG_SP, initial_sp)
emu.emu_start(initial_pc, 0)


print("~~~~~ HOPEFULLY HIT WFI ~~~~~")
dump_all_regs(emu)
save_dram(emu, "avd_ram_after_boot.bin")

with open('cmds.bin', 'rb') as f:
	all_cmds = f.read()

num_cmds = len(all_cmds) // 0x60

assert num_cmds <= 8 # FIXME
emu.mem_write(0x10002ccc, all_cmds)

for cmd_i in range(num_cmds):
	# queue a command
	trigger_irq(emu, 1)

	print(f"~~~~~ HOPEFULLY PROCESSED COMMAND {cmd_i} ~~~~~")
	dump_all_regs(emu)
	save_dram(emu, f"avd_ram_after_cmd_{cmd_i}.bin")

	# get the reply
	trigger_irq(emu, 2)

	print(f"~~~~~ HOPEFULLY GOT REPLY {cmd_i} ~~~~~")
	dump_all_regs(emu)
	save_dram(emu, f"avd_ram_after_reply_{cmd_i}.bin")
