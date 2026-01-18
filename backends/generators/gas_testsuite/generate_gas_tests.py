"""
Generator script for GNU Assembler (GAS) testsuite files.

This script generates .s (assembly source) and .d (expected disassembly output)
test files for the binutils GAS testsuite from RISC-V instruction definitions
in the Unified Database.

The generated tests follow the standard GAS testsuite format:
- .s files contain assembly instructions to test
- .d files contain expected objdump output patterns

Usage:
    python generate_gas_tests.py --inst-dir=<path> --output-dir=<path> [options]
"""

import argparse
import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


# Mapping of extension names to their march string components
EXTENSION_MARCH_MAP = {
    "I": "i",
    "M": "m",
    "A": "a",
    "F": "f",
    "D": "d",
    "Q": "q",
    "C": "c",
    "Zca": "c",
    "Zcb": "_zcb",
    "Zcd": "_zcd",
    "Zcf": "_zcf",
    "Zcmop": "_zcmop",
    "Zcmp": "_zcmp",
    "Zcmt": "_zcmt",
    "B": "b",
    "H": "h",
    "S": "s",
    "V": "v",
    "Zba": "_zba",
    "Zbb": "_zbb",
    "Zbc": "_zbc",
    "Zbkb": "_zbkb",
    "Zbkx": "_zbkx",
    "Zbs": "_zbs",
    "Zfa": "_zfa",
    "Zfh": "_zfh",
    "Zfbfmin": "_zfbfmin",
    "Zicbom": "_zicbom",
    "Zicbop": "_zicbop",
    "Zicboz": "_zicboz",
    "Zicfilp": "_zicfilp",
    "Zicfiss": "_zicfiss",
    "Zicond": "_zicond",
    "Zicsr": "_zicsr",
    "Zifencei": "_zifencei",
    "Zihintntl": "_zihintntl",
    "Zimop": "_zimop",
    "Zaamo": "_zaamo",
    "Zabha": "_zabha",
    "Zacas": "_zacas",
    "Zalasr": "_zalasr",
    "Zalrsc": "_zalrsc",
    "Zawrs": "_zawrs",
    "Zkn": "_zkn",
    "Zknd": "_zknd",
    "Zkne": "_zkne",
    "Zknh": "_zknh",
    "Zks": "_zks",
    "Zvbb": "_zvbb",
    "Zvbc": "_zvbc",
    "Zvfbfmin": "_zvfbfmin",
    "Zvfbfwma": "_zvfbfwma",
    "Zvkg": "_zvkg",
    "Zvkned": "_zvkned",
    "Zvknha": "_zvknha",
    "Zvks": "_zvks",
    "Svinval": "_svinval",
    "Sdext": "_sdext",
    "Smdbltrp": "_smdbltrp",
    "Smrnmi": "_smrnmi",
}

# Standard register names for operand generation
X_REGS = [
    "zero",
    "ra",
    "sp",
    "gp",
    "tp",
    "t0",
    "t1",
    "t2",
    "s0",
    "s1",
    "a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
    "a6",
    "a7",
    "s2",
    "s3",
    "s4",
    "s5",
    "s6",
    "s7",
    "s8",
    "s9",
    "s10",
    "s11",
    "t3",
    "t4",
    "t5",
    "t6",
]

F_REGS = [
    "ft0",
    "ft1",
    "ft2",
    "ft3",
    "ft4",
    "ft5",
    "ft6",
    "ft7",
    "fs0",
    "fs1",
    "fa0",
    "fa1",
    "fa2",
    "fa3",
    "fa4",
    "fa5",
    "fa6",
    "fa7",
    "fs2",
    "fs3",
    "fs4",
    "fs5",
    "fs6",
    "fs7",
    "fs8",
    "fs9",
    "fs10",
    "fs11",
    "ft8",
    "ft9",
    "ft10",
    "ft11",
]

V_REGS = [f"v{i}" for i in range(32)]

# Compressed register subsets (x8-x15)
C_X_REGS = ["s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5"]
C_F_REGS = ["fs0", "fs1", "fa0", "fa1", "fa2", "fa3", "fa4", "fa5"]


def get_extension_from_path(inst_path):
    """Extract extension name from instruction file path."""
    # Path format: .../inst/ExtName/instruction.yaml
    parts = inst_path.split(os.sep)
    for i, part in enumerate(parts):
        if part == "inst" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def get_march_for_extension(ext_name, base="rv64"):
    """Generate the -march string for a given extension."""
    if ext_name in EXTENSION_MARCH_MAP:
        ext_march = EXTENSION_MARCH_MAP[ext_name]
        if ext_march.startswith("_"):
            # Extension that requires a base (e.g., _zba)
            return f"{base}i{ext_march}"
        else:
            # Base extension (e.g., i, m, f, d, c)
            return f"{base}{ext_march}"
    else:
        # Unknown extension, try lowercase
        return f"{base}i_{ext_name.lower()}"


def parse_assembly_format(assembly_str, variables):
    """Parse the assembly format string and variable definitions."""
    # Handle common assembly formats:
    # "xd, xs1, xs2" - register operands
    # "xd, imm(xs1)" - load/store with offset
    # "xs1, xs2, imm" - branches
    # "xd, imm" - immediate ops

    operands = []
    if not assembly_str:
        return operands

    # Split by comma and parentheses
    parts = re.split(r"[,\s()]+", assembly_str.strip())
    parts = [p for p in parts if p]  # Remove empty strings

    var_names = {v.get("name") for v in variables} if variables else set()

    for part in parts:
        operand = {"name": part, "type": "unknown"}

        if part in var_names:
            # Find the variable definition
            for var in variables:
                if var.get("name") == part:
                    operand["var"] = var
                    break

        # Determine operand type based on naming conventions
        if part.startswith("x") and part[1:].isalnum():
            operand["type"] = "xreg"
        elif part.startswith("f") and part[1:].isalnum():
            operand["type"] = "freg"
        elif part.startswith("v") and part[1:].isalnum():
            operand["type"] = "vreg"
        elif part == "imm":
            operand["type"] = "imm"
        elif part == "shamt":
            operand["type"] = "shamt"
        elif part == "csr":
            operand["type"] = "csr"
        elif part.startswith("xs"):
            operand["type"] = "xreg"
        elif part.startswith("fs"):
            operand["type"] = "freg"
        elif part.startswith("vs"):
            operand["type"] = "vreg"
        elif part in ("rd", "rs1", "rs2", "rs3"):
            # Standard RISC-V register names
            operand["type"] = "xreg"
        elif part in ("fd", "fs1", "fs2", "fs3"):
            operand["type"] = "freg"
        elif part in ("vd", "vs1", "vs2", "vs3"):
            operand["type"] = "vreg"

        operands.append(operand)

    return operands


def generate_operand_value(operand, idx=0, is_compressed=False):
    """Generate a valid operand value for testing."""
    op_type = operand.get("type", "unknown")
    var = operand.get("var", {})

    # Check for 'not' constraints (values that are not allowed)
    not_val = var.get("not")

    if op_type == "xreg":
        if is_compressed:
            reg = C_X_REGS[idx % len(C_X_REGS)]
        else:
            reg = X_REGS[(10 + idx) % len(X_REGS)]  # Start with a0, a1, etc.

        # Handle "not 0" constraint (must not be x0/zero)
        if not_val == 0 and reg == "zero":
            reg = "a0"

        return reg

    elif op_type == "freg":
        if is_compressed:
            return C_F_REGS[idx % len(C_F_REGS)]
        return F_REGS[(10 + idx) % len(F_REGS)]

    elif op_type == "vreg":
        return V_REGS[(8 + idx) % len(V_REGS)]

    elif op_type == "imm":
        # Get bit width from location field
        location = var.get("location", "")
        left_shift = var.get("left_shift", 0)

        # Calculate immediate bit width
        if isinstance(location, str):
            # Parse location like "31-20" or "12|6-2"
            bits = 0
            for part in location.split("|"):
                if "-" in part:
                    high, low = map(int, part.split("-"))
                    bits += high - low + 1
                else:
                    bits += 1
        else:
            bits = 12  # Default

        # Handle "not 0" constraint
        if not_val == 0:
            return str(1 << left_shift) if left_shift else "1"

        # Generate a small, safe immediate value
        max_val = min((1 << (bits - 1)) - 1, 0x7FF)  # Keep it small
        return str(max_val)

    elif op_type == "shamt":
        return "5"  # Safe shift amount

    elif op_type == "csr":
        return "0x300"  # mstatus CSR

    else:
        return "0"


def generate_test_assembly(inst_name, assembly_fmt, variables, is_compressed=False):
    """Generate a test assembly line for an instruction."""
    if not assembly_fmt:
        # Some instructions have no operands (e.g., nop, fence)
        return inst_name

    # Parse the assembly format
    operands = parse_assembly_format(assembly_fmt, variables)

    # Generate operand values
    operand_values = []
    for idx, op in enumerate(operands):
        val = generate_operand_value(op, idx, is_compressed)
        operand_values.append(val)

    # Reconstruct the assembly line
    # Handle different formats: "xd, imm(xs1)" vs "xd, xs1, xs2"
    if "(" in assembly_fmt and ")" in assembly_fmt:
        # Load/store format: xd, imm(xs1)
        # Find the position of imm and base register
        match = re.match(r"(\w+),\s*(\w+)\((\w+)\)", assembly_fmt)
        if match:
            # Groups: dest_name, imm_name, base_name (not used directly)
            _ = match.groups()
            dest_val = operand_values[0] if len(operand_values) > 0 else "a0"
            imm_val = "0"  # Safe offset
            base_val = operand_values[2] if len(operand_values) > 2 else "a1"

            return f"{inst_name}\t{dest_val}, {imm_val}({base_val})"

    # Standard comma-separated format
    return f"{inst_name}\t{', '.join(operand_values)}"


def generate_d_file_pattern(encoding):
    """Generate the expected objdump pattern for a .d file."""
    # Calculate hex digit width needed for encoding pattern
    width = len(encoding) // 4  # Hex digits needed

    # Create regex pattern for the encoding
    # Variable bits could have any value, so we use regex
    encoding_pattern = f"[0-9a-f]{{{width}}}"

    return encoding_pattern


def is_compressed_instruction(encoding):
    """Check if an instruction is compressed (16-bit)."""
    return len(encoding) == 16


def generate_test_files(
    instructions, output_dir, extension_filter=None, target_arch="RV64"
):
    """Generate .s and .d test files for the given instructions."""

    # Group instructions by extension
    instructions_by_ext = {}

    for inst_name, inst_data in instructions.items():
        ext = inst_data.get("extension", "unknown")
        if extension_filter and ext not in extension_filter:
            continue

        if ext not in instructions_by_ext:
            instructions_by_ext[ext] = {}
        instructions_by_ext[ext][inst_name] = inst_data

    generated_files = []

    for ext, insts in instructions_by_ext.items():
        if not insts:
            continue

        # Generate extension-specific test files
        ext_lower = ext.lower()
        s_filename = f"{ext_lower}.s"
        d_filename = f"{ext_lower}.d"

        s_path = os.path.join(output_dir, s_filename)
        d_path = os.path.join(output_dir, d_filename)

        # Generate .s file content
        s_lines = [
            f"# Test file for {ext} extension instructions",
            "# Auto-generated by riscv-unified-db",
            "",
            "target:",
        ]

        # Generate .d file content
        base = "rv32" if target_arch == "RV32" else "rv64"
        march = get_march_for_extension(ext, base)

        d_lines = [
            f"#as: -march={march}",
            f"#source: {s_filename}",
            "#objdump: -dr",
            "",
            r".*:[ \t]+file format .*",
            "",
            "",
            "Disassembly of section .text:",
            "",
            "0+000 <target>:",
        ]

        offset = 0
        for inst_name, inst_data in sorted(insts.items()):
            encoding = inst_data.get("match", "")
            assembly_fmt = inst_data.get("assembly", "")
            variables = inst_data.get("variables", [])

            if not encoding:
                continue

            is_compressed = is_compressed_instruction(encoding)
            inst_size = 2 if is_compressed else 4

            # Generate assembly line
            asm_line = generate_test_assembly(
                inst_name, assembly_fmt, variables, is_compressed
            )
            s_lines.append(f"\t{asm_line}")

            # Generate expected disassembly pattern
            encoding_pattern = generate_d_file_pattern(encoding)
            inst_pattern = inst_name.replace(".", r"\.")

            # Format: [ ]+offset:[ ]+encoding[ ]+instruction[ ]+operands
            d_pattern = (
                f"[ \t]+[0-9a-f]+:[ \t]+{encoding_pattern}[ \t]+{inst_pattern}[ \t]+.*"
            )
            d_lines.append(d_pattern)

            offset += inst_size

        # Write .s file
        with open(s_path, "w", encoding="utf-8") as f:
            f.write("\n".join(s_lines) + "\n")

        # Write .d file
        with open(d_path, "w", encoding="utf-8") as f:
            f.write("\n".join(d_lines) + "\n")

        generated_files.append((s_path, d_path))
        logging.info(f"Generated test files for {ext}: {s_filename}, {d_filename}")

    return generated_files


def load_instructions_with_metadata(
    root_dir, enabled_extensions, include_all=False, target_arch="RV64"
):
    """
    Load instructions with additional metadata needed for test generation.
    Extends the base load_instructions function with assembly format info.
    """
    import yaml

    instr_dict = {}
    logging.info(f"Loading instructions from {root_dir} for {target_arch}")

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue

            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                logging.error(f"Error parsing {path}: {e}")
                continue

            if data.get("kind") != "instruction":
                continue

            name = data.get("name")
            if not name:
                continue

            # Get extension from path
            ext = get_extension_from_path(path)

            # Get encoding
            encoding = data.get("encoding", {})
            if isinstance(encoding, dict):
                match_str = encoding.get("match", "")
                variables = encoding.get("variables", [])
            else:
                continue

            if not match_str:
                continue

            # Get assembly format
            assembly = data.get("assembly", "")

            # Get base architecture constraint
            base = data.get("base")
            if base is not None:
                if (base == 32 and target_arch not in ["RV32", "BOTH"]) or (
                    base == 64 and target_arch not in ["RV64", "BOTH"]
                ):
                    continue

            instr_dict[name] = {
                "match": match_str,
                "assembly": assembly,
                "variables": variables,
                "extension": ext,
                "path": path,
            }

    logging.info(f"Loaded {len(instr_dict)} instructions with metadata")
    return instr_dict


def main():
    """Main function to generate GAS testsuite files."""
    parser = argparse.ArgumentParser(
        description="Generate GAS testsuite files from RISC-V instruction definitions"
    )
    parser.add_argument(
        "--inst-dir",
        required=True,
        help="Directory containing instruction YAML files",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for generated test files",
    )
    parser.add_argument(
        "--extension",
        "-e",
        action="append",
        dest="extensions",
        help="Generate tests only for specified extension(s). Can be repeated.",
    )
    parser.add_argument(
        "--arch",
        choices=["RV32", "RV64", "BOTH"],
        default="RV64",
        help="Target architecture (default: RV64)",
    )
    parser.add_argument(
        "--include-all",
        "-a",
        action="store_true",
        help="Include all instructions, ignoring extension filtering",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Load instructions with metadata
    instructions = load_instructions_with_metadata(
        args.inst_dir,
        args.extensions or [],
        include_all=args.include_all,
        target_arch=args.arch,
    )

    if not instructions:
        logging.error("No instructions found!")
        return 1

    # Generate test files
    generated = generate_test_files(
        instructions,
        args.output_dir,
        extension_filter=args.extensions,
        target_arch=args.arch,
    )

    logging.info(f"Generated {len(generated)} test file pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
