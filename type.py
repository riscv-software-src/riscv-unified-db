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
      - Load instructions (names starting with "lb", "ld", "lh", or "lw") are forced to I-type.
      - Any instruction whose name contains "fence" is forced to I-type.
6. As a fallback, if all tests have failed (the type is still "Unknown")
   and the encoding’s variables contain only "rd" and "rs1", then the type is set to R-type.

Once determined, the script inserts (or updates) a new field named `format`
immediately after the `long_name:` field.
"""

import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import PlainScalarString
from ruamel.yaml.representer import RoundTripRepresenter

# Use round-trip mode to preserve as much of the original formatting as possible.
yaml = YAML(typ="rt")
yaml.preserve_quotes = True  # Preserve original quoting
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096  # Prevent line wrapping


def represent_plain_str(dumper, data):
    # Force plain style (no quotes) for PlainScalarString instances.
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="")


yaml.Representer.add_representer(PlainScalarString, represent_plain_str)


def parse_location(location):
    """
    Parse a location (either a string or an integer) into a list of tuples.

    - If the location is an integer, it is treated as a single bit
      (e.g. 7 becomes [(7, 7)]).
    - If it is a string (e.g. "31|7|30-25|11-8"), it is assumed to be delimited by '|'
      characters. Each segment is either a single bit or a range.

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
    """
    if len(match_field) != 16:
        return "C-type"
    group = match_field[-2:]
    funct3 = match_field[0:3]
    if group == "00":
        if funct3 == "000":
            return "CIW"  # e.g., C.ADDI4SPN
        elif funct3 == "010":
            return "CL"  # e.g., C.LW
        elif funct3 == "110":
            return "CS"  # e.g., C.SW
        else:
            return "C-type"
    elif group == "01":
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
    it is wrapped in PlainScalarString so that it is output without added quotes.
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
      - Otherwise, if the match field is entirely hardcoded (only "0" and "1"),
        force the instruction type to I-type.
      - Otherwise, if an "imm" variable is present, use it to classify the instruction.
      - Else if a "shamt" variable is present, classify the instruction as I-type.
      - Otherwise, if registers appear as expected for R-type, classify as R-type;
        else, set the type to "Unknown".
      - Finally, force instructions whose names start with specific prefixes:
            - Names starting with "fcvt" or "fmv" are forced to R-type.
            - Load instructions (names starting with "lb", "ld", "lh", or "lw") are forced to I-type.
            - If the instruction name contains "fence", force it to I-type.
      - As a fallback: if all tests have failed (type is "Unknown") and the only register
        variables in the encoding are "rd" and "rs1", force the type to R-type.
      - Insert (or update) a new field "type:" immediately after "long_name:".
      - Ensure that the 'match' field remains unquoted.
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
    if isinstance(encoding, dict) and ("RV32" in encoding or "RV64" in encoding):
        chosen_encoding = encoding.get("RV32", encoding.get("RV64", {}))
    else:
        chosen_encoding = encoding

    match_field = chosen_encoding.get("match", "")
    # If the match field is entirely hardcoded (only "0" and "1"), force I-type.
    if isinstance(match_field, str) and match_field and set(match_field) <= {"0", "1"}:
        inst_type = "I-type"
    elif isinstance(match_field, str) and len(match_field) == 16:
        inst_type = classify_compressed(match_field)
    else:
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
    if inst_name.startswith("fcvt") or inst_name.startswith("fmv"):
        inst_type = "R-type"
    elif inst_name.startswith(("lb", "ld", "lh", "lw", "lr", "li")):
        inst_type = "I-type"
    elif inst_name.startswith(("sw.", "sh.", "sd.", "sb.")):
        inst_type = "S-type"
    elif (
        "fence" in inst_name
        or inst_name.startswith("cbo.")
        or inst_name.startswith("ssrdp")
    ):
        inst_type = "I-type"

    # Fallback: if inst_type is still "Unknown", check if there are "rd" and "rs1".
    if inst_type == "Unknown":
        var_names = [
            var.get("name", "").lower() for var in chosen_encoding.get("variables", [])
        ]
        # Remove empty names if any.
        var_names = [name for name in var_names if name]
        if (
            any(name.endswith("s1") for name in var_names)
            and any(name.endswith("d") for name in var_names)
            or (
                any(name.endswith("s1") for name in var_names)
                and any(name.endswith("s2") for name in var_names)
            )
            or (
                any(name.endswith("s2") for name in var_names)
                and any(name.endswith("d") for name in var_names)
            )
        ):
            inst_type = "R-type"
        elif {"csr", "imm", "rd"}.issubset(set(var_names)) or {
            "csr",
            "uimm",
            "rd",
        }.issubset(set(var_names)):
            inst_type = "I-type"

    # Insert (or update) a new field "type:" immediately after "long_name:".
    if "long_name" in data:
        keys = list(data.keys())
        idx = keys.index("long_name")
        # Use "format" as the key (change to "type" if desired)
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
