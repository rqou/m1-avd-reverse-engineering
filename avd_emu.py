import struct
from unicorn import *
from unicorn.arm_const import *

##### helpers

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

MMIOS = {
	0x50010010: (read_cm3ctrl_irq_en_0, write_cm3ctrl_irq_en_0),
	0x50010014: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010018: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x5001001c: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010020: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010024: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),
	0x50010028: (read_cm3ctrl_irq_en, write_cm3ctrl_irq_en),

	0xe000ed08: (lambda _addr: None, write_vtor),
	0xe000e100: (read_isen, write_isen),
	0xe000e104: (read_isen, write_isen),
	0xe000e108: (read_isen, write_isen),
	0xe000e10c: (read_isen, write_isen),
	0xe000e110: (read_isen, write_isen),
	0xe000e114: (read_isen, write_isen),
	0xe000e118: (read_isen, write_isen),
	0xe000e11c: (read_isen, write_isen),
	# 0xdeadaa00: (read_magic_reg, write_magic_reg),
	# 0xdeadaa04: (read_magic_reg_2, write_magic_reg_2),
}

MMIO_BLOCKS = [
	(0x50010000, 0x4000),	# CM3Ctrl
	(0xe000c000, 0x4000),	# SCS
]

##### setup

emu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
emu.mem_map(0, 0x10000)				# IRAM
emu.mem_map(0x10000000, 0x10000)	# DRAM

emu.mem_write(0, FIRMWARE)

def hook_mmio(emu_, access, addr, sz, value, data):
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

initial_sp = struct.unpack("<I", FIRMWARE[0:4])[0]
initial_pc = struct.unpack("<I", FIRMWARE[4:8])[0]
print(f"Starting @ {initial_pc:08x} with SP {initial_sp:08x}")
emu.reg_write(UC_ARM_REG_SP, initial_sp)
emu.emu_start(initial_pc, 0)


print("~~~~~ HOPEFULLY HIT WFI ~~~~~")
dump_all_regs(emu)
save_dram(emu, "avd_ram_after_boot.bin")
