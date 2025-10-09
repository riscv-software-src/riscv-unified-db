#!/usr/bin/env python3
"""
Generator script for overlapping instruction declarations.
"""
import os
import sys
import logging
import argparse
import yaml
from collections import defaultdict

# Add parent directory to path to import generator.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def get_extension_name(instruction_yaml_path):
    """Extract the extension name from the instruction YAML file."""
    try:
        with open(instruction_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        definedBy = data.get("definedBy")
        if not definedBy:
            return None

        if isinstance(definedBy, str):
            return definedBy

        if isinstance(definedBy, dict):
            # Try anyOf - prefer simple strings, take last alternative
            if "anyOf" in definedBy:
                alternatives = definedBy["anyOf"]
                if isinstance(alternatives, list):
                    for alt in reversed(alternatives):
                        if isinstance(alt, str):
                            return alt
                        if isinstance(alt, dict):
                            if "name" in alt:
                                return alt["name"]
                            if "allOf" in alt and isinstance(alt["allOf"], list):
                                last = alt["allOf"][-1]
                                if isinstance(last, str):
                                    return last
                                if isinstance(last, dict) and "name" in last:
                                    return last["name"]

            # Try allOf - take last extension
            if "allOf" in definedBy and isinstance(definedBy["allOf"], list):
                last_ext = definedBy["allOf"][-1]
                if isinstance(last_ext, str):
                    return last_ext
                if isinstance(last_ext, dict) and "name" in last_ext:
                    return last_ext["name"]

            # Try oneOf - take first alternative
            if "oneOf" in definedBy and isinstance(definedBy["oneOf"], list):
                first_ext = definedBy["oneOf"][0]
                if isinstance(first_ext, str):
                    return first_ext
                if isinstance(first_ext, dict) and "name" in first_ext:
                    return first_ext["name"]

            # Direct name field
            if "name" in definedBy:
                return definedBy["name"]

        return None
    except Exception as e:
        logging.debug(f"Error extracting extension from {instruction_yaml_path}: {e}")
        return None


def load_all_instructions_with_metadata(root_dir):
    """Load all instructions with their encoding metadata."""
    instructions = {}

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue

            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                logging.debug(f"Error parsing {path}: {e}")
                continue

            if data.get("kind") != "instruction" or not data.get("name"):
                continue

            name = data["name"]
            encoding = data.get("encoding", {})
            extension = get_extension_name(path)

            # Extract match patterns
            match_patterns = {}
            if isinstance(encoding, dict):
                if "match" in encoding:
                    match_patterns["default"] = encoding["match"]
                else:
                    for arch in ["RV32", "RV64"]:
                        if arch in encoding and "match" in encoding[arch]:
                            match_patterns[arch] = encoding[arch]["match"]

            # Store instruction variants
            for arch, match in match_patterns.items():
                key = name if arch == "default" else f"{name}_{arch}"
                instructions[key] = {
                    "name": name,
                    "match": match,
                    "extension": extension,
                    "file_path": path,
                    "arch": arch,
                }

    return instructions


def matches_overlap(match1, match2):
    """Check if two match patterns overlap."""
    if len(match1) != len(match2):
        return False

    for bit1, bit2 in zip(match1, match2):
        if bit1 != "-" and bit2 != "-" and bit1 != bit2:
            return False

    return True


def count_fixed_bits(match):
    """Count the number of fixed bits in a match pattern."""
    return sum(1 for bit in match if bit != "-")


def find_overlapping_instructions(instructions):
    """Find all pairs of overlapping instructions."""
    BASE_EXTS = {"I", "C", "M", "A", "F", "D", "Zicsr", "Zifencei"}
    COMPRESSED_EXTS = {"Zca", "Zcb", "Zcd", "Zcf", "Zcmp", "Zcmt", "Zcmop", "Zclsd"}
    SPECIAL_C_EXTS = {"Zcf", "Zcd", "Zcmp", "Zcmt", "Zcmop"}
    GENERAL_C_EXTS = {"Zca", "Zclsd"}

    overlaps = []
    seen_pairs = set()

    instr_list = list(instructions.items())

    for name1, data1 in instr_list:
        for name2, data2 in instr_list:
            # Skip same instruction or same base name
            if name1 == name2 or data1["name"] == data2["name"]:
                continue

            match1, match2 = data1["match"], data2["match"]

            # Skip if different lengths or no overlap
            if len(match1) != len(match2) or not matches_overlap(match1, match2):
                continue

            fixed1, fixed2 = count_fixed_bits(match1), count_fixed_bits(match2)
            ext1, ext2 = data1.get("extension", ""), data2.get("extension", "")

            should_add = False
            specific_name, specific_data = name1, data1
            general_name, general_data = name2, data2

            # Case 1: More specific encoding (more fixed bits)
            if fixed1 > fixed2:
                should_add = True

            # Case 2: Same specificity but different extensions
            elif fixed1 == fixed2 and ext1 != ext2:
                ext1_is_base = ext1 in BASE_EXTS or (ext1 and ext1.startswith("RV"))
                ext2_is_base = ext2 in BASE_EXTS or (ext2 and ext2.startswith("RV"))

                # Extension vs base: extension overlaps
                if not ext1_is_base and ext2_is_base:
                    should_add = True
                elif ext1_is_base and not ext2_is_base:
                    # Swap: ext2 is the specific one
                    specific_name, specific_data = name2, data2
                    general_name, general_data = name1, data1
                    should_add = True
                # Both compressed extensions: special vs general
                elif ext1 in COMPRESSED_EXTS and ext2 in COMPRESSED_EXTS:
                    if ext1 in SPECIAL_C_EXTS and ext2 in GENERAL_C_EXTS:
                        should_add = True
                    elif ext2 in SPECIAL_C_EXTS and ext1 in GENERAL_C_EXTS:
                        # Swap: ext2 is the specific one
                        specific_name, specific_data = name2, data2
                        general_name, general_data = name1, data1
                        should_add = True

            if should_add:
                pair_key = (specific_data["name"], general_data["name"])
                if pair_key not in seen_pairs:
                    overlaps.append(
                        (specific_name, specific_data, general_name, general_data)
                    )
                    seen_pairs.add(pair_key)

    return overlaps


def format_extension_name(ext_name):
    """Format extension name as EXT_XXX."""
    if not ext_name:
        return "UNKNOWN"
    ext_upper = ext_name.upper()
    return ext_upper if ext_upper.startswith("EXT_") else f"EXT_{ext_upper}"


def format_instruction_name(inst_name):
    """Format instruction name as C identifier."""
    return inst_name.replace(".", "_")


def generate_output(overlaps, instructions):
    """Generate the DECLARE_OVERLAP_INSN output."""
    overlap_groups = defaultdict(list)

    for specific_name, specific_data, general_name, general_data in overlaps:
        general_inst_name = general_data["name"]
        overlap_groups[general_inst_name].append((specific_name, specific_data))

    output_lines = []
    for general_inst, specific_list in sorted(overlap_groups.items()):
        general_inst_formatted = format_instruction_name(general_inst)
        output_lines.append(f"// these overlap {general_inst_formatted}")

        for specific_name, specific_data in sorted(specific_list, key=lambda x: x[0]):
            inst_name = format_instruction_name(specific_data["name"])
            ext_name = format_extension_name(specific_data["extension"])
            output_lines.append(f"DECLARE_OVERLAP_INSN({inst_name}, {ext_name})")

        output_lines.append("")

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate overlapping instruction declarations"
    )
    parser.add_argument("--inst-dir", help="Path to spec directory")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine spec directory
    if args.inst_dir:
        inst_dir = args.inst_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        inst_dir = os.path.join(repo_root, "spec", "std", "isa", "inst")

    if not os.path.exists(inst_dir):
        logging.error(f"Spec directory not found: {inst_dir}")
        sys.exit(1)

    logging.info(f"Loading instructions from {inst_dir}")
    instructions = load_all_instructions_with_metadata(inst_dir)
    logging.info(f"Loaded {len(instructions)} instructions")

    overlaps = find_overlapping_instructions(instructions)
    logging.info(f"Found {len(overlaps)} overlapping instruction pairs")

    output = generate_output(overlaps, instructions)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        logging.info(f"Wrote output to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
