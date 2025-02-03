#!/usr/bin/env python3
"""
This script loads instruction description files (in YAML format) and
identifies each instruction’s type based on its encoding.

It uses two methods:
1. If an immediate variable ("imm") is defined, it uses the bit‐layout
   of the immediate to classify the instruction as one of:
      - I-Type: immediate in one contiguous field (31–20)
      - S-Type: immediate split as (31–25) and (11–7)
      - B-Type: immediate split as (bit31), (30–25), (11–8), (bit7)
      - U-Type: immediate in one contiguous field (31–12)
      - J-Type: immediate split as (bit31), (30–21), (20,20), (19–12)
2. Otherwise, it expects an R-Type instruction, meaning that the encoding
   must contain three registers at the following bit–positions:
      - Source 1: bits 19–15 (e.g. rs1 or fs1)
      - Source 2: bits 24–20 (e.g. rs2 or fs2)
      - Destination: bits 11–7 (e.g. rd or fd)

If a file is passed, the script processes that file; if a directory is passed,
it recurses through the directory and processes all files ending in `.yaml`.
"""

import sys
import yaml
from pathlib import Path


def parse_location(location_str):
    """
    Parse a location string into a list of segments.

    The location string is assumed to be delimited by '|' characters.
    Each segment is either a single bit (e.g. "7") or a range (e.g. "30-25").
    Returns a list of tuples in the form (high_bit, low_bit).
    """
    segments = [seg.strip() for seg in location_str.split("|") if seg.strip()]
    parsed = []
    for seg in segments:
        if "-" in seg:
            try:
                high, low = seg.split("-")
                parsed.append((int(high.strip()), int(low.strip())))
            except ValueError:
                pass  # Skip malformed segment
        else:
            try:
                bit = int(seg)
                parsed.append((bit, bit))
            except ValueError:
                pass
    return parsed


def identify_immediate_type(imm_location):
    """
    Given the immediate's location string, determine the instruction type.
    Recognized types:
      I-Type: single contiguous field (31-20)
      S-Type: two parts: (31-25) and (11-7)
      B-Type: four parts: (31,31), (30-25), (11-8), (7,7)
      U-Type: single contiguous field (31-12)
      J-Type: four parts: (31,31), (30-21), (20,20), (19-12)
    """
    segments = parse_location(imm_location)
    seg_set = set(segments)

    if len(segments) == 1 and segments[0] == (31, 20):
        return "I-Type"
    if len(segments) == 2 and seg_set == {(31, 25), (11, 7)}:
        return "S-Type"
    if len(segments) == 4 and seg_set == {(31, 31), (30, 25), (11, 8), (7, 7)}:
        return "B-Type"
    if len(segments) == 1 and segments[0] == (31, 12):
        return "U-Type"
    if len(segments) == 4 and seg_set == {(31, 31), (30, 21), (20, 20), (19, 12)}:
        return "J-Type"

    return "Unknown"


def check_rtype_registers(variables):
    """
    Check that among the variables there is one register at bits 19-15 (source1),
    one register at bits 24-20 (source2), and one register at bits 11-7 (destination).

    Returns True if all three are found, otherwise False.
    """
    found_source1 = False
    found_source2 = False
    found_dest = False

    # Look at each variable's location. For register fields we expect a single contiguous range.
    for var in variables:
        loc_str = var.get("location", "")
        segments = parse_location(loc_str)
        if len(segments) == 1:
            seg = segments[0]
            if seg == (19, 15):
                found_source1 = True
            elif seg == (24, 20):
                found_source2 = True
            elif seg == (11, 7):
                found_dest = True

    return found_source1 and found_source2 and found_dest


def process_file(filepath):
    """
    Process a single YAML file to determine its instruction type.
    """
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading or parsing {filepath}: {e}")
        return

    encoding = data.get("encoding", {})
    variables = encoding.get("variables", [])

    # First, check if an immediate variable ("imm") is defined.
    imm_location = None
    for var in variables:
        if var.get("name") == "imm":
            imm_location = var.get("location")
            break

    if imm_location is not None:
        inst_type = identify_immediate_type(imm_location)
    else:
        # If no immediate is defined, expect an R-Type instruction.
        if check_rtype_registers(variables):
            inst_type = "R-Type"
        else:
            inst_type = "Unknown"

    print(f"{filepath}: Instruction type: {inst_type}")


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <file_or_directory>".format(sys.argv[0]))
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file() and path.suffix == ".yaml":
        # Process a single file.
        process_file(path)
    elif path.is_dir():
        # Recursively process all .yaml files in the directory.
        yaml_files = list(path.rglob("*.yaml"))
        if not yaml_files:
            print("No .yaml files found in directory:", path)
        for yaml_file in yaml_files:
            process_file(yaml_file)
    else:
        print(f"Error: {path} is neither a .yaml file nor a directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
