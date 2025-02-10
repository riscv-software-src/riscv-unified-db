#!/usr/bin/env python3
"""
This script recursively processes YAML instruction files and determines
the instruction type based on the encoding. The decision is made as follows:

1. If the chosen encoding’s match field is 16 characters long, we assume the
   instruction is compressed and call classify_compressed() to assign a specific
   C-type (such as CIW, CL, CS, CI, CR, CB, or CJ).
2. Otherwise, if an immediate variable ("imm") is defined, its bit layout is used:
      - I-type: immediate is a contiguous field (31-20)
      - S-type: immediate is split as (31-25) and (11-7)
      - B-type: immediate is split as (bit 31), (30-25), (11-8), (bit 7)
      - U-type: immediate is a contiguous field (31-12)
      - J-type: immediate is split as (bit 31), (30-21), (20-20), (19-12)
3. Else if no "imm" is present but a "shamt" variable is found, classify as I-type.
4. Otherwise, if registers appear as expected for R-type, classify as R-type;
   else, set the type to "Unknown".
5. Finally, force instructions whose names start with specific prefixes:
      - Names starting with "fcvt" or "fmv" are forced to R-type.
      - **Loads** (names starting with "lb", "ld", "lh", or "lw") are forced to I-type.

Once determined, the script inserts (or updates) a new field named `type:`
immediately after the `long_name:` field.
"""

import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import PlainScalarString
from ruamel.yaml.representer import RoundTripRepresenter


yaml = YAML(typ="rt")  # Use round-trip mode
yaml.preserve_quotes = True  # Preserve original quoting
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096  # Prevent line wrapping


def represent_plain_str(dumper, data):
    # Force plain style (empty string) regardless of the content.
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="")


yaml.Representer.add_representer(PlainScalarString, represent_plain_str)


def parse_location(location):
    """
    Parse a location (either a string or an integer) into a list of tuples.

    - If the location is an integer, it is treated as a single bit
      (e.g. 7 becomes [(7, 7)]).
    - If it is a string (e.g. "31|7|30-25|11-8"), it is assumed to be delimited by '|'
      characters. Each segment is either a single bit (e.g. "7") or a range (e.g. "30-25").

    Returns a list of tuples in the form (high_bit, low_bit).
    """
    if isinstance(location, int):
        return [(location, location)]

    segments = [seg.strip() for seg in location.split("|") if seg.strip()]
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
    Determine the instruction type based on the immediate's bit layout.

    Recognized types:
      I-type: single contiguous field (31-20)
      S-type: two parts: (31-25) and (11-7)
      B-type: four parts: (31,31), (30-25), (11,8), (7,7)
      U-type: single contiguous field (31-12)
      J-type: four parts: (31,31), (30-21), (20,20), (19,12)
    """
    segments = parse_location(imm_location)
    seg_set = set(segments)

    if len(segments) == 1 and segments[0] == (31, 20):
        return "I-type"
    if len(segments) == 2 and seg_set == {(31, 25), (11, 7)}:
        return "S-type"
    if len(segments) == 4 and seg_set == {(31, 31), (30, 25), (11, 8), (7, 7)}:
        return "B-type"
    if len(segments) == 1 and segments[0] == (31, 12):
        return "U-type"
    if len(segments) == 4 and seg_set == {(31, 31), (30, 21), (20, 20), (19, 12)}:
        return "J-type"

    return "Unknown"


def check_rtype_registers(variables):
    """
    Check that among the variables there is one register at:
       - Bits 19–15 (source1)
       - Bits 24–20 (source2)
       - Bits 11–7  (destination)
    Returns True if all three are found, otherwise False.
    """
    found_source1 = False
    found_source2 = False
    found_dest = False

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


def classify_compressed(match_field):
    """
    Given a 16-character match string for a compressed instruction,
    attempt to classify it into a specific C-type based on common RVC
    patterns. This is a best‑effort mapping using:
      - group: the two least-significant bits (bits [1:0])
      - funct3: the top three bits (bits [15:13])

    Returns one of:
      "CIW", "CL", "CS", "CI", "CR", "CB", "CJ"
    or falls back to "C-type" if none match.

    Note: This mapping is a simplification and may not cover all cases.
    """
    if len(match_field) != 16:
        return "C-type"
    # In our assumed representation, bit15 is match_field[0] and bit0 is match_field[15]
    # Extract the two least-significant bits (bits 1:0):
    group = match_field[-2:]
    # Extract bits 15:13 as funct3:
    funct3 = match_field[0:3]

    if group == "00":
        # Group 0: usually CIW, CL, or CS.
        if funct3 == "000":
            return "CIW"  # e.g., C.ADDI4SPN
        elif funct3 == "010":
            return "CL"  # e.g., C.LW
        elif funct3 == "110":
            return "CS"  # e.g., C.SW
        else:
            return "C-type"
    elif group == "01":
        # Group 1: often CI, CR, or CB.
        if funct3 in ["000", "010", "011"]:
            return "CI"  # e.g., C.ADDI, C.LI, C.ADDI16SP
        elif funct3 == "100":
            return "CR"  # e.g., C.MV, C.ADD, C.JR, etc.
        elif funct3 in ["101", "110"]:
            return "CB"  # e.g., C.BEQZ, C.BNEZ
        elif funct3 == "111":
            return "CJ"  # e.g., C.J
        else:
            return "C-type"
    elif group == "10":
        # Group 2: similar to group 1.
        if funct3 in ["000", "010", "011"]:
            return "CI"
        elif funct3 == "100":
            return "CR"
        elif funct3 in ["101", "110"]:
            return "CB"
        elif funct3 == "111":
            return "CJ"
        else:
            return "C-type"
    else:
        return "C-type"


def ensure_plain_match(enc):
    """
    Ensure that if the given encoding dict has a 'match' field that is a string,
    it is wrapped in PlainScalarString so that it is output without quotes.
    """
    if isinstance(enc, dict) and "match" in enc:
        match_value = enc["match"]
        if isinstance(match_value, str):
            enc["match"] = PlainScalarString(match_value)


def process_file(filepath):
    """
    Process a single YAML file:
      - Determine the instruction type using the encoding section.
      - If the chosen encoding's "match" field is 16 characters long,
        classify the instruction using classify_compressed().
      - Otherwise, if an "imm" variable is present, use it to classify the instruction.
      - Else if a "shamt" variable is present, classify the instruction as I-type.
      - Otherwise, if registers appear as expected for R-type, classify as R-type;
        else, set the type to "Unknown".
      - Finally, force instructions whose names start with specific prefixes:
            - Names starting with "fcvt" or "fmv" are forced to R-type.
            - **Load instructions** (names starting with "lb", "ld", "lh", or "lw") are forced to I-type.
      - Insert (or update) a new field "type:" immediately after "long_name:".
      - Ensure that the 'match' field remains unquoted by wrapping it in PlainScalarString.
      - Write the updated YAML back to the same file.
    """
    try:
        with open(filepath) as f:
            data = yaml.load(f)
    except Exception as e:
        print(f"Error reading or parsing {filepath}: {e}")
        return

    # Handle nested encoding (e.g., RV32, RV64) versus flat encoding.
    encoding = data.get("encoding", {})
    chosen_encoding = {}
    if isinstance(encoding, dict) and ("RV32" in encoding or "RV64" in encoding):
        # Prefer RV32 if available; otherwise use RV64.
        chosen_encoding = encoding.get("RV32", encoding.get("RV64", {}))
    else:
        chosen_encoding = encoding

    # First, if the match field is 16 characters long, classify as a specific C-type.
    match_field = chosen_encoding.get("match", "")
    if isinstance(match_field, str) and len(match_field) == 16:
        inst_type = classify_compressed(match_field)
    else:
        # Otherwise, use our usual tests.
        variables = chosen_encoding.get("variables", [])
        imm_location = None
        shamt_exists = False

        for var in variables:
            if var.get("name") == "imm":
                imm_location = var.get("location")
            if var.get("name") == "shamt":
                shamt_exists = True

        if imm_location is not None:
            inst_type = identify_immediate_type(imm_location)
        elif shamt_exists:
            inst_type = "I-type"
        elif check_rtype_registers(variables):
            inst_type = "R-type"
        else:
            inst_type = "Unknown"

    # Force specific instruction types based on the instruction name.
    inst_name = data.get("name", "").lower()
    # Force instructions starting with "fcvt" or "fmv" to be R-type.
    if inst_name.startswith("fcvt") or inst_name.startswith("fmv"):
        inst_type = "R-type"
    # Force load instructions (lb, ld, lh, lw) to be I-type.
    elif inst_name.startswith(("lb", "ld", "lh", "lw", "lr")):
        # Loads are I-type
        inst_type = "I-type"

    # Insert or update the new field "type:" immediately after "long_name:"
    if "long_name" in data:
        keys = list(data.keys())
        idx = keys.index("long_name")
        if "format" in data:
            data["format"] = inst_type
        else:
            data.insert(idx + 1, "format", inst_type)
    else:
        data["format"] = inst_type

    # Ensure the "match" field remains unquoted.
    if isinstance(encoding, dict):
        if "RV32" in encoding or "RV64" in encoding:
            for key in encoding:
                if isinstance(encoding[key], dict):
                    ensure_plain_match(encoding[key])
        else:
            ensure_plain_match(encoding)

    try:
        with open(filepath, "w") as f:
            yaml.dump(data, f)
        if inst_type == "Unknown":
            print(f"Updated {filepath}: Instruction type set to {inst_type}")
    except Exception as e:
        print(f"Error writing file {filepath}: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <file_or_directory>".format(sys.argv[0]))
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file() and path.suffix == ".yaml":
        process_file(path)
    elif path.is_dir():
        yaml_files = list(path.rglob("*.yaml"))
        if not yaml_files:
            print("No .yaml files found in directory:", path)
        for yf in yaml_files:
            process_file(yf)
    else:
        print(f"Error: {path} is neither a .yaml file nor a directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
