#!/usr/bin/env python3
"""
Generator script for C encoding header.
This script uses the existing generator.py functions to create encoding.h.
"""
import os
import sys
import logging
import pprint

# Add parent directory to path to import generator.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import functions from generator.py
from generator import load_instructions, load_csrs, parse_match

pp = pprint.PrettyPrinter(indent=2)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def calculate_mask(match_str):
    """
    Calculate the mask for an instruction match pattern.
    For each position, if it's '-', we put 0 in the mask (don't care bit).
    For each position, if it's '0' or '1', we put 1 in the mask (fixed bit).
    """
    mask_str = "".join("0" if c == "-" else "1" for c in match_str)
    return int(mask_str, 2)


def main():
    """
    Main function to generate encoding.h.
    """
    import argparse

    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Generate RISC-V C encoding header")
    parser.add_argument(
        "--inst-dir",
        default="../../../arch/inst/",
        help="Directory containing instruction YAML files",
    )
    parser.add_argument(
        "--csr-dir",
        default="../../../arch/csr/",
        help="Directory containing CSR YAML files",
    )
    parser.add_argument(
        "--output",
        default="encoding.out.h",
        help="Output filename (default: encoding.out.h)",
    )
    parser.add_argument(
        "--include-all",
        "-a",
        action="store_true",
        help="Include all instructions, ignoring extension filtering",
    )

    args = parser.parse_args()
    # Directory paths
    this_dir = os.path.dirname(os.path.abspath(__file__))

    instructions_dir = args.inst_dir
    csrs_dir = args.csr_dir
    output_file = os.path.join(this_dir, args.output)

    # Load all instructions regardless of base
    # Use "BOTH" to get both RV32 and RV64 instructions
    logging.info(f"Loading instructions from {instructions_dir}")
    instructions = load_instructions(
        instructions_dir, [], include_all=args.include_all, target_arch="BOTH"
    )

    logging.info(f"Loading CSRs from {csrs_dir}")
    csrs = load_csrs(csrs_dir, [], include_all=args.include_all, target_arch="BOTH")

    # Process each instruction to calculate its mask
    # For RV32-specific instructions, append "_rv32" to the name
    instr_dict = {}
    for name, instr_data in instructions.items():
        match_str = instr_data.get("match")
        if match_str:
            try:
                match_val = parse_match(match_str)
                mask_val = calculate_mask(match_str)

                # If the name ends with ".rv32", change it to "_rv32"
                if name.endswith(".rv32"):
                    name = name[:-5] + "_rv32"

                instr_dict[name] = {
                    "match": f"0x{match_val:x}",
                    "mask": f"0x{mask_val:x}",
                }
            except Exception as e:
                logging.error(f"Error processing {name}: {e}")

    # exception causes
    causes = [
        (0x0, "misaligned fetch"),
        (0x1, "fetch access"),
        (0x2, "illegal instruction"),
        (0x3, "breakpoint"),
        (0x4, "misaligned load"),
        (0x5, "load access"),
        (0x6, "misaligned store"),
        (0x7, "store access"),
        (0x8, "user ecall"),
        (0x9, "supervisor ecall"),
        (0xA, "virtual supervisor ecall"),
        (0xB, "machine ecall"),
        (0xC, "fetch page fault"),
        (0xD, "load page fault"),
        (0xF, "store page fault"),
        (0x14, "fetch guest page fault"),
        (0x15, "load guest page fault"),
        (0x16, "virtual instruction"),
        (0x17, "store guest page fault"),
    ]

    # Define instruction field positions for argument extraction
    arg_lut = {
        "opcode": (6, 0),
        "rd": (11, 7),
        "rs1": (19, 15),
        "rs2": (24, 20),
        "rs3": (31, 27),
        "funct3": (14, 12),
        "funct5": (31, 27),
        "funct7": (31, 25),
        "imm_i": (31, 20),
        "imm_s": (31, 25),
        "imm_b": (31, 25),
        "imm_u": (31, 12),
        "imm_j": (31, 12),
        "zimm": (19, 15),
        "pred": (27, 24),
        "succ": (23, 20),
        "rm": (14, 12),
        "csr": (31, 20),
    }

    # Generate mask_match_str
    mask_match_str = ""
    for i in sorted(instr_dict.keys()):
        mask_match_str += (
            f'#define MATCH_{i.upper().replace(".","_")} {instr_dict[i]["match"]}\n'
        )
        mask_match_str += (
            f'#define MASK_{i.upper().replace(".","_")} {instr_dict[i]["mask"]}\n'
        )

    # Generate declare_insn_str
    declare_insn_str = ""
    for i in sorted(instr_dict.keys()):
        declare_insn_str += f'DECLARE_INSN({i.replace(".","_")}, MATCH_{i.upper().replace(".","_")}, MASK_{i.upper().replace(".","_")})\n'

    # Generate csr_names_str and declare_csr_str
    csr_names_str = ""
    declare_csr_str = ""
    for addr, name in sorted(csrs.items()):
        csr_names_str += f"#define CSR_{name.upper()} 0x{addr:x}\n"
        declare_csr_str += f"DECLARE_CSR({name.lower()}, CSR_{name.upper()})\n"

    # Generate causes_str and declare_cause_str
    causes_str = ""
    declare_cause_str = ""
    for num, name in causes:
        sanitized_name = name.upper().replace(" ", "_")
        causes_str += f"#define CAUSE_{sanitized_name} 0x{num:x}\n"
        declare_cause_str += f'DECLARE_CAUSE("{name}", CAUSE_{sanitized_name})\n'

    # Generate arg_str
    arg_str = ""
    for name, rng in arg_lut.items():
        sanitized_name = name.replace(" ", "_").replace("=", "_eq_")
        begin = rng[1]
        end = rng[0]
        mask = ((1 << (end - begin + 1)) - 1) << begin
        arg_str += f"#define INSN_FIELD_{sanitized_name.upper()} 0x{mask:x}\n"

    # Try to get current git commit hash
    try:
        commit = os.popen('git log -1 --format="format:%h"').read().strip()
        if not commit:
            commit = "unknown"
    except:
        commit = "unknown"

    # Generate the output as a string
    output_str = f"""/* SPDX-License-Identifier: BSD-3-Clause */
/* Copyright (c) 2023 RISC-V International */
/*
 * This file is auto-generated by riscv-unified-db
 */

#ifndef RISCV_ENCODING_H
#define RISCV_ENCODING_H
{mask_match_str}
{csr_names_str}
{causes_str}
{arg_str}#endif
#ifdef DECLARE_INSN
{declare_insn_str}#endif
#ifdef DECLARE_CSR
{declare_csr_str}#endif
#ifdef DECLARE_CAUSE
{declare_cause_str}#endif
"""

    # Write the output to the file
    with open(output_file, "w", encoding="utf-8") as enc_file:
        enc_file.write(output_str)

    logging.info(f"Generated encoding header file: {output_file}")


if __name__ == "__main__":
    main()
