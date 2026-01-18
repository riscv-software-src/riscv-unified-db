#!/usr/bin/env python3
"""
Generator script for C encoding header.
This script uses the existing generator.py functions to create encoding.h.
"""
import os
import sys
import logging
import argparse
import yaml

# Add parent directory to path to import generator.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import functions from generator.py
from generator import (
    load_instructions,
    load_csrs,
    load_exception_codes,
    parse_match,
    parse_extension_requirements,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def calculate_mask(match_str):
    """Convert the bit pattern string to a mask (1 for fixed bits, 0 for variable bits)."""
    return int("".join("0" if c == "-" else "1" for c in match_str), 2)


def extract_instruction_fields(instructions):
    """Extract field names and their positions from instruction definitions."""
    field_dict = {}

    # Define standard field name mapping (architecture-specific to standard)
    field_name_map = {
        # Standard register names
        "xs1": "rs1",
        "xs2": "rs2",
        "xd": "rd",
        # Floating point register names
        "fs1": "rs1",
        "fs2": "rs2",
        "fd": "rd",
        # Keep standard names as-is
        "rs1": "rs1",
        "rs2": "rs2",
        "rs3": "rs3",
        "rd": "rd",
        "imm": "imm",
        "shamt": "shamt",
        "csr": "csr",
        "funct3": "funct3",
        "funct7": "funct7",
        "opcode": "opcode",
        "rm": "rm",
    }

    # Predefined common field positions
    common_fields = {
        "opcode": (6, 0),
        "rd": (11, 7),
        "rs1": (19, 15),
        "rs2": (24, 20),
        "rs3": (31, 27),
        "funct3": (14, 12),
        "funct5": (31, 27),
        "funct7": (31, 25),
        "funct2": (26, 25),
        "imm12": (31, 20),
        "imm12hi": (31, 25),
        "imm12lo": (11, 7),
        "imm20": (31, 12),
        "jimm20": (31, 12),
        "bimm12hi": (31, 25),
        "bimm12lo": (11, 7),
        "zimm": (19, 15),
        "zimm5": (19, 15),
        "zimm6hi": (26, 26),
        "zimm6lo": (19, 15),
        "zimm10": (29, 20),
        "zimm11": (30, 20),
        "pred": (27, 24),
        "succ": (23, 20),
        "rm": (14, 12),
        "csr": (31, 20),
        "fm": (31, 28),
        "aq": (26, 26),
        "rl": (25, 25),
        "aqrl": (26, 25),
        "amoop": (31, 27),
        "bs": (31, 30),
        "rnum": (23, 20),
        "rc": (31, 30),
        "nf": (31, 29),
        "vm": (25, 25),
        "vd": (11, 7),
        "vs1": (19, 15),
        "vs2": (24, 20),
        "vs3": (11, 7),
        "wd": (26, 26),
        "shamtw": (24, 20),
        "shamtd": (25, 20),
        "shamtq": (26, 20),
        "shamtw4": (23, 20),
        "simm5": (19, 15),
        "imm2": (21, 20),
        "imm3": (22, 20),
        "imm4": (23, 20),
        "imm5": (24, 20),
        "imm6": (25, 20),
        # Compressed instruction fields
        "c_rs2": (6, 2),
        "c_rs2_n0": (6, 2),
        "c_rs1_n0": (11, 7),
        "c_rs2_e": (6, 2),
        "c_index": (9, 2),
        "c_rlist": (7, 4),
        "c_spimm": (5, 2),
        "c_sreg1": (9, 7),
        "c_sreg2": (4, 2),
        "c_uimm1": (6, 6),
        "c_uimm2": (6, 5),
        "c_nzuimm5": (6, 2),
        "c_nzuimm6hi": (12, 12),
        "c_nzuimm6lo": (6, 2),
        "c_nzuimm10": (12, 5),
        "c_nzimm6hi": (12, 12),
        "c_nzimm6lo": (6, 2),
        "c_nzimm10hi": (12, 12),
        "c_nzimm10lo": (6, 2),
        "c_nzimm18hi": (12, 12),
        "c_nzimm18lo": (6, 2),
        "c_imm6hi": (12, 12),
        "c_imm6lo": (6, 2),
        "c_imm12": (12, 2),
        "c_bimm9hi": (12, 10),
        "c_bimm9lo": (6, 2),
        "c_uimm7hi": (6, 5),
        "c_uimm7lo": (12, 10),
        "c_uimm8hi": (6, 5),
        "c_uimm8lo": (12, 10),
        "c_uimm8sphi": (4, 2),
        "c_uimm8splo": (12, 7),
        "c_uimm8sp_s": (12, 7),
        "c_uimm9hi": (6, 5),
        "c_uimm9lo": (12, 10),
        "c_uimm9sphi": (4, 2),
        "c_uimm9splo": (12, 7),
        "c_uimm9sp_s": (12, 7),
        "c_uimm10sphi": (5, 2),
        "c_uimm10splo": (12, 7),
        "c_uimm10sp_s": (12, 7),
        "c_mop_t": (10, 8),
        # MOP instruction fields
        "mop_r_t_30": (30, 30),
        "mop_r_t_27_26": (27, 26),
        "mop_r_t_21_20": (21, 20),
        "mop_rr_t_30": (30, 30),
        "mop_rr_t_27_26": (27, 26),
        # Other fields
        "rd_n0": (11, 7),
        "rd_n2": (11, 7),
        "rd_n0_e": (11, 7),
        "rd_e": (11, 7),
        "rd_p": (9, 7),
        "rd_p_e": (9, 7),
        "rd_rs1": (11, 7),
        "rd_rs1_n0": (11, 7),
        "rd_rs1_p": (9, 7),
        "rs1_n0": (19, 15),
        "rs1_p": (9, 7),
        "rs2_e": (24, 20),
        "rs2_p": (4, 2),
        "rs2_p_e": (4, 2),
        "rs2_eq_rs1": (24, 20),
        "rt": (24, 20),
    }

    # First add all common fields
    for name, (high, low) in common_fields.items():
        mask = ((1 << (high - low + 1)) - 1) << low
        field_dict[name] = {
            "location": f"{high}-{low}",
            "mask": f"0x{mask:x}",
            "source": "common",
        }

    # Then process fields from actual instructions
    for name, instr_data in instructions.items():
        # Get variables from the instruction structure
        variables = []
        encoding = instr_data.get("encoding", {})

        if isinstance(encoding, dict):
            vars_data = encoding.get("variables", [])
            # Handle both list format (old style) and dict format (new style from resolved format)
            if isinstance(vars_data, list):
                variables = vars_data
            elif isinstance(vars_data, dict):
                # Convert dict to list format
                for var_name, var_info in vars_data.items():
                    if isinstance(var_info, dict) and "location" in var_info:
                        variables.append(
                            {"name": var_name, "location": var_info["location"]}
                        )

        # Process each field
        for var in variables:
            if not isinstance(var, dict):
                continue

            orig_field_name = var.get("name")
            location = var.get("location")

            if not orig_field_name or not location:
                continue

            # Map to standard field name if possible
            std_field_name = field_name_map.get(orig_field_name, orig_field_name)

            # Skip if we already have this field from common definitions
            if (
                std_field_name in field_dict
                and field_dict[std_field_name].get("source") == "common"
            ):
                continue

            # Process location format - handle pipe-separated locations (e.g., "30|27-26|21-20")
            if isinstance(location, str):
                if "|" in location:
                    # Split location has multiple parts, compute combined mask
                    parts = location.split("|")
                    total_mask = 0
                    for part in parts:
                        if "-" in part:
                            high, low = map(int, part.split("-"))
                        else:
                            high = low = int(part)
                        total_mask |= ((1 << (high - low + 1)) - 1) << low
                    field_dict[std_field_name] = {
                        "location": location,
                        "mask": f"0x{total_mask:x}",
                        "source": "instruction",
                        "original_name": (
                            orig_field_name
                            if orig_field_name != std_field_name
                            else None
                        ),
                    }
                elif "-" in location:
                    try:
                        high, low = map(int, location.split("-"))
                        mask = ((1 << (high - low + 1)) - 1) << low
                        field_dict[std_field_name] = {
                            "location": f"{high}-{low}",
                            "mask": f"0x{mask:x}",
                            "source": "instruction",
                            "original_name": (
                                orig_field_name
                                if orig_field_name != std_field_name
                                else None
                            ),
                        }
                    except ValueError:
                        logging.warning(
                            f"Invalid location format: {location} for field {orig_field_name}"
                        )
                else:
                    try:
                        pos = int(location)
                        mask = 1 << pos
                        field_dict[std_field_name] = {
                            "location": str(pos),
                            "mask": f"0x{mask:x}",
                            "source": "instruction",
                            "original_name": (
                                orig_field_name
                                if orig_field_name != std_field_name
                                else None
                            ),
                        }
                    except ValueError:
                        logging.warning(
                            f"Invalid location format: {location} for field {orig_field_name}"
                        )
            elif isinstance(location, int):
                mask = 1 << location
                field_dict[std_field_name] = {
                    "location": str(location),
                    "mask": f"0x{mask:x}",
                    "source": "instruction",
                    "original_name": (
                        orig_field_name if orig_field_name != std_field_name else None
                    ),
                }

    logging.info(f"Extracted {len(field_dict)} unique instruction field names")
    return field_dict


def main():
    """Main function to generate encoding.h."""
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
        "--ext-dir",
        default="../../../arch/ext/",
        help="Directory containing extension YAML files",
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
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        default=[],
        help="List of extensions to include",
    )
    parser.add_argument(
        "--fallback-to-hardcoded",
        "-f",
        action="store_true",
        help="Fallback to hardcoded exception causes if none are loaded from files",
    )
    parser.add_argument(
        "--resolved-codes",
        help="JSON file containing pre-resolved exception codes",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    this_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(this_dir, args.output)

    # Load instructions and CSRs
    logging.info(f"Loading instructions from {args.inst_dir}")
    instructions = load_instructions(
        args.inst_dir, args.extensions, include_all=args.include_all, target_arch="BOTH"
    )

    logging.info(f"Loading CSRs from {args.csr_dir}")
    csrs = load_csrs(
        args.csr_dir, args.extensions, include_all=args.include_all, target_arch="BOTH"
    )

    # Load exception codes
    logging.info(f"Loading exception codes from {args.ext_dir}")
    causes = load_exception_codes(
        args.ext_dir,
        args.extensions,
        include_all=args.include_all,
        resolved_codes_file=args.resolved_codes,
    )

    # Process instructions and calculate masks
    instr_dict = {}
    for name, instr_data in instructions.items():
        match_str = instr_data.get("match")
        if match_str:
            try:
                match_val = parse_match(match_str)
                mask_val = calculate_mask(match_str)

                # Convert .rv32 suffix to _rv32
                if name.endswith(".rv32"):
                    name = name[:-5] + "_rv32"

                instr_dict[name] = {
                    "match": f"0x{match_val:x}",
                    "mask": f"0x{mask_val:x}",
                }
            except Exception as e:
                logging.error(f"Error processing {name}: {e}")

    # Extract field information
    field_dict = extract_instruction_fields(instructions)

    # Generate output strings
    mask_match_str = ""
    for i in sorted(instr_dict.keys()):
        mask_match_str += (
            f'#define MATCH_{i.upper().replace(".","_")} {instr_dict[i]["match"]}\n'
        )
        mask_match_str += (
            f'#define MASK_{i.upper().replace(".","_")} {instr_dict[i]["mask"]}\n'
        )

    declare_insn_str = ""
    for i in sorted(instr_dict.keys()):
        declare_insn_str += f'DECLARE_INSN({i.replace(".","_")}, MATCH_{i.upper().replace(".","_")}, MASK_{i.upper().replace(".","_")})\n'

    csr_names_str = ""
    declare_csr_str = ""
    for addr, name in sorted(csrs.items()):
        csr_names_str += f"#define CSR_{name.upper().replace(".","_")} 0x{addr:x}\n"
        declare_csr_str += f"DECLARE_CSR({name.lower().replace(".","_")}, CSR_{name.upper().replace(".","_")})\n"

    causes_str = ""
    declare_cause_str = ""
    for num, name in causes:
        sanitized_name = name.upper()
        causes_str += f"#define CAUSE_{sanitized_name} 0x{num:x}\n"
        declare_cause_str += f'DECLARE_CAUSE("{name}", CAUSE_{sanitized_name})\n'

    field_str = ""
    for field_name, details in sorted(field_dict.items()):
        sanitized_name = field_name.replace(" ", "_").replace("=", "_eq_")
        comment = f"{details['location']}"
        if details.get("original_name"):
            comment += f" (from {details['original_name']})"
        field_str += f"#define INSN_FIELD_{sanitized_name.upper()} {details['mask']}  /* {comment} */\n"

    # Assemble final output
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
{field_str}#endif
#ifdef DECLARE_INSN
{declare_insn_str}#endif
#ifdef DECLARE_CSR
{declare_csr_str}#endif
#ifdef DECLARE_CAUSE
{declare_cause_str}#endif
"""

    # Write output file
    with open(output_file, "w", encoding="utf-8") as enc_file:
        enc_file.write(output_str)

    logging.info(f"Generated encoding header file: {output_file}")


if __name__ == "__main__":
    main()
