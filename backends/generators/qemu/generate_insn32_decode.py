#!/usr/bin/env python3
"""Generate QEMU decodetree snippets from the Unified DB."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# Make the shared generator helpers importable when running from source tree.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import load_full_instructions  # noqa: E402

logger = logging.getLogger(__name__)


DEFAULT_LAYOUT: List[int] = [7, 5, 5, 3, 5, 7]
# Instruction format mappings.
# Each key is a QEMU decodetree instruction format tag.
#
# TODO: When instruction formats are defined in UDB with their bit layouts
# in the YAML, remove FORMAT_LAYOUTS, FORMAT_OVERRIDES, and most of
# determine_format(); this generator should then directly use the provided
# format tag + layout instead of inferringfrom the mapping here.

FORMAT_LAYOUTS: Dict[str, List[int]] = {
    "@r": [7, 5, 5, 3, 5, 7],
    "@i": [12, 5, 3, 5, 7],
    "@s": [7, 5, 5, 3, 5, 7],
    "@b": [7, 5, 5, 3, 5, 7],
    "@u": [20, 5, 7],
    "@j": [20, 5, 7],
    "@csr": [12, 5, 3, 5, 7],
    "@sh": [6, 6, 5, 3, 5, 7],
    "@sh5": [7, 5, 5, 3, 5, 7],
    "@sh6": [6, 6, 5, 3, 5, 7],
    "@atom_ld": [5, 1, 1, 5, 5, 3, 5, 7],
    "@atom_st": [5, 1, 1, 5, 5, 3, 5, 7],
    "@sfence_vma": [7, 5, 5, 3, 5, 7],
    "@sfence_vm": [7, 5, 5, 3, 5, 7],
    "@hfence_gvma": [7, 5, 5, 3, 5, 7],
    "@hfence_vvma": [7, 5, 5, 3, 5, 7],
    "@r4_rm": [5, 2, 5, 5, 3, 5, 7],
    "@r_rm": [7, 5, 5, 3, 5, 7],
    "@r2_rm": [7, 5, 5, 3, 5, 7],
    "@r2": [7, 5, 5, 3, 5, 7],
    "@r2_s": [7, 5, 5, 3, 5, 7],
    "@r2_vm": [6, 1, 5, 5, 3, 5, 7],
    "@r1_vm": [6, 1, 5, 5, 3, 5, 7],
    "@r_vm": [6, 1, 5, 5, 3, 5, 7],
    "@r_nfvm": [3, 3, 1, 5, 5, 3, 5, 7],
    "@r2_nfvm": [3, 3, 1, 5, 5, 3, 5, 7],
    "@r2_zimm6": [5, 1, 1, 5, 5, 3, 5, 7],
    "@r2_zimm10": [2, 10, 5, 3, 5, 7],
    "@r2_zimm11": [1, 11, 5, 3, 5, 7],
    "@k_aes": [2, 5, 5, 5, 3, 5, 7],
    "@i_aes": [2, 5, 5, 5, 3, 5, 7],
    "@mop5": [1, 1, 2, 2, 4, 2, 5, 3, 5, 7],
    "@mop3": [1, 1, 2, 2, 1, 5, 5, 3, 5, 7],
}

# Manual overrides for special cases where field patterns alone can't determine
# the correct instruction format tag. Keep this minimal.
FORMAT_OVERRIDES: Dict[str, str] = {
    # Shift instructions: field detection handles these via shamt field
    "slli": "@sh",
    "srli": "@sh",
    "srai": "@sh",
    "slliw": "@sh5",
    "srliw": "@sh5",
    "sraiw": "@sh5",
    # Cache/fence instructions: these have same fields as @r2_s but need specific formats
    "cbo.clean": "@sfence_vm",
    "cbo.flush": "@sfence_vm",
    "cbo.inval": "@sfence_vm",
    "cbo.zero": "@sfence_vm",
    "hfence.gvma": "@hfence_gvma",
    "hfence.vvma": "@hfence_vvma",
    "hinval.gvma": "@hfence_gvma",
    "hinval.vvma": "@hfence_vvma",
    "sfence.vma": "@sfence_vma",
    "sinval.vma": "@sfence_vma",
    # May-be-operations: special encoding format
    "mop.r.n": "@mop5",
    "mop.r.w": "@mop5",
    "mop.r.l": "@mop5",
    "mop.rr.n": "@mop3",
    "mop.rr.w": "@mop3",
    "mop.rr.l": "@mop3",
}

SUPPORTED_FORMAT_TAGS: Iterable[str] = FORMAT_LAYOUTS.keys()



@dataclass
class VariableInfo:
    name: str
    location: str
    left_shift: int = 0

    @property
    def normalized(self) -> str:
        return normalize_var_name(self.name)

    @property
    def width(self) -> int:
        return compute_field_width(self.location)


@dataclass
class ProcessedInstruction:
    name: str
    pattern: str
    format_tag: Optional[str]

    def render(self, name_width: int = 12) -> str:
        # Replace dots with underscores for QEMU naming convention
        qemu_name = self.name.replace(".", "_")
        tag_part = f" {self.format_tag}" if self.format_tag else ""
        return f"{qemu_name:<{name_width}} {self.pattern}{tag_part}"


def normalize_var_name(raw: str) -> str:
    if not raw:
        return raw
    if raw.startswith("xs"):
        return "rs" + raw[2:]
    if raw.startswith("xt"):
        return "rt" + raw[2:]
    if raw.startswith("xd"):
        return "rd" + raw[2:]
    if raw.startswith("rsd"):
        return "rd" + raw[3:]
    if raw.startswith("rd") or raw.startswith("rs"):
        return raw
    if raw.startswith("imm"):
        return "imm"
    return raw


def compute_field_width(location: Optional[str]) -> int:
    if not location:
        return 0
    total = 0
    for part in str(location).split("|"):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            hi, lo = part.split("-")
            total += int(hi) - int(lo) + 1
        else:
            total += 1
    return total


def determine_format(name: str, variables: Dict[str, VariableInfo]) -> Optional[str]:
    # Check overrides first for special cases that can't be derived from fields
    override = FORMAT_OVERRIDES.get(name)
    if override:
        return override

    var_names = set(variables.keys())
    if not var_names:
        return None

    # Count field types to help with classification
    has_int_dest = "rd" in var_names or "xd" in var_names
    has_int_src1 = "rs1" in var_names or "xs1" in var_names
    has_int_src2 = "rs2" in var_names or "xs2" in var_names
    has_fp_dest = "fd" in var_names
    has_fp_src1 = "fs1" in var_names
    has_fp_src2 = "fs2" in var_names
    has_fp_src3 = "fs3" in var_names
    has_rounding = "rm" in var_names
    has_imm = "imm" in var_names
    
    # CSR instructions
    if "csr" in var_names:
        return "@csr"

    # Shift amount instructions (use shamt field to detect)
    if "shamt" in var_names:
        shamt_width = variables["shamt"].width
        if shamt_width <= 5:
            return "@sh5"
        elif shamt_width == 6:
            return "@sh6"
        return "@sh"

    # Atomic instructions: detect by aq/rl fields
    if "aq" in var_names or "rl" in var_names:
        # lr.* instructions: only one source register (xs1), dest (xd)
        if has_int_dest and has_int_src1 and not has_int_src2:
            return "@atom_ld"
        # sc.* and amo* instructions: two source registers
        if has_int_dest and has_int_src1 and has_int_src2:
            return "@atom_st"

    # Floating-point with rounding mode
    # @r4_rm: fd, fs1, fs2, fs3, rm (fused multiply-add)
    if has_fp_dest and has_fp_src1 and has_fp_src2 and has_fp_src3 and has_rounding:
        return "@r4_rm"
    
    # @r_rm: fd, fs1, fs2, rm (FP arithmetic)
    if has_fp_dest and has_fp_src1 and has_fp_src2 and has_rounding:
        return "@r_rm"
    
    # @r2_rm: FP conversions with rounding mode (various combinations)
    if has_rounding:
        # fd, fs1, rm (fsqrt, fcvt between FP types)
        if has_fp_dest and has_fp_src1:
            return "@r2_rm"
        # rd, fs1, rm (FP to int conversions)
        if has_int_dest and has_fp_src1:
            return "@r2_rm"
        # fd, rs1, rm (int to FP conversions)
        if has_fp_dest and has_int_src1:
            return "@r2_rm"

    # Vector instructions with vm field
    # @r_vm: vd, vs2, vs1, vm
    if {"vd", "vs2", "vs1", "vm"}.issubset(var_names):
        return "@r_vm"
    
    # @r_vm: vd, vs2, rs1, vm (vector-scalar operations)
    if {"vd", "vs2", "rs1", "vm"}.issubset(var_names):
        return "@r_vm"
    
    # @r_vm: vd, vs2, imm, vm (vector-immediate operations)
    if {"vd", "vs2", "imm", "vm"}.issubset(var_names):
        return "@r_vm"
    
    # @r2_vm: vd, vs2, vm (vector unary operations)
    if {"vd", "vs2", "vm"}.issubset(var_names):
        return "@r2_vm"
    
    # @r1_vm: vd, vs1, vm
    if {"vd", "vs1", "vm"}.issubset(var_names):
        return "@r1_vm"
    
    # @r_nfvm: vd, rs1, nf, vm (vector segment loads/stores)
    if {"vd", "rs1", "nf", "vm"}.issubset(var_names):
        return "@r_nfvm"
    
    # @r2_nfvm: vd, vs2, rs1, nf, vm
    if {"vd", "vs2", "rs1", "nf", "vm"}.issubset(var_names):
        return "@r2_nfvm"

    # Vector configuration instructions
    # @r2_zimm11: rd, rs1, zimm (vsetvl)
    if {"rd", "rs1", "zimm"}.issubset(var_names):
        zimm = variables["zimm"]
        if zimm.width == 11:
            return "@r2_zimm11"
        elif zimm.width == 10:
            return "@r2_zimm10"
        elif zimm.width == 6:
            return "@r2_zimm6"
    
    # @r2_zimm10: rd, zimm (vsetivli)
    if {"rd", "zimm"}.issubset(var_names):
        zimm = variables["zimm"]
        if zimm.width == 10:
            return "@r2_zimm10"
        elif zimm.width == 6:
            return "@r2_zimm6"

    # Crypto instructions: detect by bs/rnum fields
    if "bs" in var_names:
        return "@k_aes"
    if "rnum" in var_names:
        return "@i_aes"

    # Floating-point three-register operations without rounding mode
    # @r: fd, fs1, fs2 (fsgnj, fmin, fmax, etc.)
    if has_fp_dest and has_fp_src1 and has_fp_src2 and not has_rounding:
        return "@r"
    
    # FP comparison operations that write to integer register
    # @r: xd/rd, fs1, fs2 (feq, flt, fle)
    if has_int_dest and has_fp_src1 and has_fp_src2:
        return "@r"
    
    # Integer three-register operations
    # @r: rd, rs1, rs2
    if has_int_dest and has_int_src1 and has_int_src2:
        return "@r"
    
    # Two-register operations without immediate
    # @r2: rd, rs1
    if has_int_dest and has_int_src1 and not has_imm and not has_int_src2:
        return "@r2"
    
    # @r2: fd, fs1 (two FP register operations without rm)
    if has_fp_dest and has_fp_src1 and not has_rounding and not has_imm and not has_fp_src2:
        return "@r2"
    
    # @r2: xd/rd, fs1 (FP classify/move operations)
    if has_int_dest and has_fp_src1 and not has_imm and not has_int_src1:
        return "@r2"
    
    # @r2: fd, xs1/rs1 (move from integer to FP)
    if has_fp_dest and has_int_src1 and not has_imm and not has_fp_src1:
        return "@r2"

    # S-type and B-type instructions
    if has_imm and has_int_src1 and has_int_src2:
        imm = variables["imm"]
        # B-type: branches have left-shifted immediate
        if imm.left_shift == 1:
            return "@b"
        # S-type: stores
        return "@s"
    
    # FP store instructions: xs1, fs2, imm
    if has_imm and has_int_src1 and has_fp_src2:
        return "@s"
    
    # @r2_s: rs1, rs2 (fence instructions)
    if has_int_src1 and has_int_src2 and not has_int_dest and not has_imm:
        return "@r2_s"

    # I-type instructions: rd, rs1, imm
    if has_imm and has_int_src1 and has_int_dest:
        imm = variables["imm"]
        # U-type: upper immediate
        if imm.width == 20 and imm.left_shift >= 12:
            return "@u"
        return "@i"
    
    # FP load instructions: xs1, fd, imm
    if has_imm and has_int_src1 and has_fp_dest:
        return "@i"

    # J-type and U-type: rd, imm (no source register)
    if has_imm and has_int_dest and not has_int_src1:
        imm = variables["imm"]
        # J-type: jal has left-shifted immediate
        if imm.width == 20 and imm.left_shift == 1:
            return "@j"
        # U-type: lui, auipc
        if imm.left_shift >= 12:
            return "@u"
        return "@i"

    return None


def format_match(match: str, format_tag: Optional[str]) -> Optional[str]:
    """Format instruction match pattern with single spaces between fields.
    
    The QEMU decodetree parser splits on whitespace, so extra spacing is purely
    cosmetic. We use single spaces for simplicity.
    """
    if not match:
        return None
    
    # Convert dashes to dots (both are "don't care" in QEMU)
    cleaned = match.replace("-", ".")
    
    # Get the layout for this instruction format tag
    layout = FORMAT_LAYOUTS.get(format_tag, DEFAULT_LAYOUT)
    
    # Verify the pattern length matches the expected layout
    if len(cleaned) != sum(layout):
        logger.debug("Unable to format match %s with layout %s", match, layout)
        return None
    
    # Split the pattern according to the layout and join with single spaces
    tokens = []
    pos = 0
    for width in layout:
        tokens.append(cleaned[pos : pos + width])
        pos += width
    
    return " ".join(tokens)



def collect_variables(raw_vars: Iterable[dict]) -> Dict[str, VariableInfo]:
    variables: Dict[str, VariableInfo] = {}
    for entry in raw_vars or []:
        name = entry.get("name")
        location = entry.get("location")
        if not name or not location:
            continue
        info = VariableInfo(
            name=name,
            location=location,
            left_shift=int(entry.get("left_shift", 0)),
        )
        variables[info.normalized] = info
    return variables


def process_instruction(name: str, info: dict) -> Optional[ProcessedInstruction]:
    encoding = info.get("encoding", {})
    if not isinstance(encoding, dict):
        logger.debug("Skipping %s: encoding not a dictionary", name)
        return None

    match = encoding.get("match")
    if not match or len(match) != 32:
        logger.debug("Skipping %s: missing or non-32b match", name)
        return None

    variables = collect_variables(encoding.get("variables", []))
    format_tag = determine_format(name, variables)

    if format_tag and format_tag not in SUPPORTED_FORMAT_TAGS:
        logger.debug("Skipping %s: format tag %s not supported", name, format_tag)
        return None

    pattern = format_match(match, format_tag)
    if not pattern:
        logger.debug("Skipping %s: failed to format pattern", name)
        return None
    return ProcessedInstruction(name=name, pattern=pattern, format_tag=format_tag)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate QEMU decodetree snippets (e.g. insn32.decode entries) from "
            "Unified DB instruction metadata"
        )
    )
    parser.add_argument(
        "--inst-dir",
        default="../../../spec/std/isa/inst/",
        help="Directory containing instruction YAML files",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Where to write generated content (use '-' for stdout)",
    )
    parser.add_argument(
        "--extensions",
        default="I,Zicsr",
        help="Comma-separated list of enabled extensions (omit or use --include-all to skip filtering)",
    )
    parser.add_argument(
        "--arch",
        default="RV64",
        choices=["RV32", "RV64", "BOTH"],
        help="Target architecture",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all instructions, ignoring extension filtering",
    )
    parser.add_argument(
        "--target",
        default="insn32",
        choices=["insn32"],
        help="QEMU artifact to generate (insn32 decode table only for now)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def write_output(lines: List[ProcessedInstruction], skipped: List[str], path: str) -> None:
    header = [
        "# Auto-generated by generate_insn32_decode.py; DO NOT EDIT.",
        "#",
        "# Generated instruction entries",
    ]
    body = [instr.render() for instr in lines]
    footer: List[str] = []
    if skipped:
        footer.append("#")
        footer.append("# Skipped instructions (needs manual mapping or unsupported encoding):")
        footer.extend(f"# - {item}" for item in skipped)

    content = "\n".join(header + [""] + body + ([""] + footer if footer else [])) + "\n"

    if path == "-":
        sys.stdout.write(content)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    include_all = args.include_all or not args.extensions
    if include_all:
        enabled_extensions: List[str] = []
        logger.info("Including all instructions (extension filtering disabled)")
    else:
        enabled_extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        logger.info("Enabled extensions: %s", ", ".join(enabled_extensions))

    logger.info("Target architecture: %s", args.arch)

    instructions = load_full_instructions(
        args.inst_dir,
        enabled_extensions,
        include_all,
        args.arch,
    )

    processed: List[ProcessedInstruction] = []
    skipped: List[str] = []

    for name in sorted(instructions.keys()):
        instr = instructions[name]
        result = process_instruction(name, instr)
        if result is None:
            skipped.append(name)
        else:
            processed.append(result)

    processed.sort(key=lambda item: item.name)

    if not processed:
        logger.warning("No instructions were generated")

    write_output(processed, skipped, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
