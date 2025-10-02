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
import json

# Add parent directory to path to import generator.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import functions from generator.py
from generator import (
    load_instructions,
    load_csrs,
    parse_match,
    parse_extension_requirements,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def calculate_mask(match_str):
    """Convert the bit pattern string to a mask (1 for fixed bits, 0 for variable bits)."""
    return int("".join("0" if c == "-" else "1" for c in match_str), 2)


def load_exception_codes(
    ext_dir, enabled_extensions=None, include_all=False, resolved_codes_file=None
):
    """Load exception codes from extension YAML files or pre-resolved JSON file."""
    exception_codes = []
    found_extensions = 0
    found_files = 0

    if enabled_extensions is None:
        enabled_extensions = []

    # If we have a resolved codes file, use it instead of processing YAML files
    if resolved_codes_file and os.path.exists(resolved_codes_file):
        try:
            with open(resolved_codes_file, encoding="utf-8") as f:
                resolved_codes = json.load(f)

            for code in resolved_codes:
                num = code.get("num")
                name = code.get("name")
                if num is not None and name is not None:
                    sanitized_name = (
                        name.lower()
                        .replace(" ", "_")
                        .replace("/", "_")
                        .replace("-", "_")
                    )
                    exception_codes.append((num, sanitized_name))

            logging.info(
                f"Loaded {len(exception_codes)} pre-resolved exception codes from {resolved_codes_file}"
            )

            # Sort by exception code number and deduplicate
            seen_nums = set()
            unique_codes = []
            for num, name in sorted(exception_codes, key=lambda x: x[0]):
                if num not in seen_nums:
                    seen_nums.add(num)
                    unique_codes.append((num, name))

            return unique_codes

        except Exception as e:
            logging.error(
                f"Error loading resolved codes file {resolved_codes_file}: {e}"
            )
            # Fall back to processing YAML files

    for dirpath, _, filenames in os.walk(ext_dir):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue

            found_files += 1
            path = os.path.join(dirpath, fname)

            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict) or data.get("kind") != "extension":
                    continue

                found_extensions += 1
                ext_name = data.get("name", "unnamed")

                # Skip extension filtering if include_all is True
                if not include_all:
                    # Filter by extension requirements
                    definedBy = data.get("definedBy")
                    if definedBy:
                        meets_req = parse_extension_requirements(definedBy)
                        if not meets_req(enabled_extensions):
                            continue

                    # Check if excluded
                    excludedBy = data.get("excludedBy")
                    if excludedBy:
                        exclusion_check = parse_extension_requirements(excludedBy)
                        if exclusion_check(enabled_extensions):
                            continue

                # Get exception codes
                for code in data.get("exception_codes", []):
                    num = code.get("num")
                    name = code.get("name")

                    if num is not None and name is not None:
                        sanitized_name = (
                            name.lower()
                            .replace(" ", "_")
                            .replace("/", "_")
                            .replace("-", "_")
                        )
                        exception_codes.append((num, sanitized_name))

            except Exception as e:
                logging.error(f"Error processing file {path}: {e}")

    if found_extensions > 0:
        logging.info(
            f"Found {found_extensions} extension definitions in {found_files} files"
        )
        logging.info(f"Added {len(exception_codes)} exception codes to the output")
    else:
        logging.warning(f"No extension definitions found in {ext_dir}")

    # Sort by exception code number and deduplicate
    seen_nums = set()
    unique_codes = []
    for num, name in sorted(exception_codes, key=lambda x: x[0]):
        if num not in seen_nums:
            seen_nums.add(num)
            unique_codes.append((num, name))

    return unique_codes


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
        # Vector register names
        "vs1": "rs1",
        "vs2": "rs2",
        "vd": "rd",
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
        if "encoding" in instr_data:
            encoding = instr_data["encoding"]

            if isinstance(encoding, dict):
                if "variables" in encoding:
                    variables = encoding.get("variables", [])
                elif "RV64" in encoding:
                    rv64_encoding = encoding.get("RV64", {})
                    if isinstance(rv64_encoding, dict):
                        variables = rv64_encoding.get("variables", [])
                elif "RV32" in encoding:
                    rv32_encoding = encoding.get("RV32", {})
                    if isinstance(rv32_encoding, dict):
                        variables = rv32_encoding.get("variables", [])

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

            # Process location format
            if isinstance(location, str) and "-" in location:
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
            elif isinstance(location, (int, str)):
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
