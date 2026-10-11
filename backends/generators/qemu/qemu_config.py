"""
QEMU Generator Configuration

Define custom mappings and preferences for QEMU code generation.
"""

# Map extension identifiers to QEMU extension feature flags
# This helps QEMU correctly identify which features to enable for each extension
QEMU_EXTENSION_FEATURES = {
    # Base ISA
    "I": "cpu->cfg.ext_i",
    "M": "cpu->cfg.ext_m",
    "A": "cpu->cfg.ext_a",
    "F": "cpu->cfg.ext_f",
    "D": "cpu->cfg.ext_d",
    "C": "cpu->cfg.ext_c",
    "V": "cpu->cfg.ext_v",
    # Standard extensions
    "Zba": "cpu->cfg.ext_zba",
    "Zbb": "cpu->cfg.ext_zbb",
    "Zbc": "cpu->cfg.ext_zbc",
    "Zbs": "cpu->cfg.ext_zbs",
    "Zk": "cpu->cfg.ext_zk",
    "Zkn": "cpu->cfg.ext_zkn",
    "Zks": "cpu->cfg.ext_zks",
}

# Map extension names to QEMU CPU feature strings used in -cpu flags
QEMU_CPU_FEATURE_MAP = {
    "I": "i",
    "M": "m",
    "A": "a",
    "F": "f",
    "D": "d",
    "C": "c",
    "V": "v",
    "Zba": "zba",
    "Zbb": "zbb",
    "Zbc": "zbc",
    "Zbs": "zbs",
}

# Standard RISC-V register names used in QEMU
QEMU_REGISTER_NAMES = {
    "x0": "zero",
    "x1": "ra",
    "x2": "sp",
    "x3": "gp",
    "x4": "tp",
    "x5": "t0",
    "x6": "t1",
    "x7": "t2",
    "x8": "s0",
    "x9": "s1",
    "x10": "a0",
    "x11": "a1",
    "x12": "a2",
    "x13": "a3",
    "x14": "a4",
    "x15": "a5",
    "x16": "a6",
    "x17": "a7",
    "x18": "s2",
    "x19": "s3",
    "x20": "s4",
    "x21": "s5",
    "x22": "s6",
    "x23": "s7",
    "x24": "s8",
    "x25": "s9",
    "x26": "s10",
    "x27": "s11",
    "x28": "t3",
    "x29": "t4",
    "x30": "t5",
    "x31": "t6",
}

# Map UDB operand names to QEMU operand characters for disassembly
# Used when generating disassembler table entries
QEMU_OPERAND_MAP = {
    "xd": "d",  # x-register destination
    "xs1": "s",  # x-register source 1
    "xs2": "t",  # x-register source 2
    "imm": "j",  # immediate (I-type)
    "fd": "D",  # f-register destination
    "fs1": "S",  # f-register source 1
    "fs2": "T",  # f-register source 2
    "vd": "V",  # v-register destination
    "vs1": "U",  # v-register source 1
    "vs2": "W",  # v-register source 2
}


# Helper functions
def get_qemu_feature_flag(extension_name):
    """Get the QEMU feature flag for an extension"""
    return QEMU_EXTENSION_FEATURES.get(
        extension_name, f"cpu->cfg.ext_{extension_name.lower()}"
    )


def get_cpu_feature_string(extension_name):
    """Get the CPU feature string for use in -cpu flags"""
    return QEMU_CPU_FEATURE_MAP.get(extension_name, extension_name.lower())


def get_register_alias(register_number):
    """Get the ABI name for a register number"""
    return QEMU_REGISTER_NAMES.get(f"x{register_number}", f"x{register_number}")
