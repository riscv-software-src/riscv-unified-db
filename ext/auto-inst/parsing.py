# SPDX-FileCopyrightText: Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-FileCopyrightText: 2024-2025 Contributors to the RISCV UnifiedDB <https://github.com/riscv-software-src/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import re
import yaml
from pathlib import Path
import pytest

yaml_instructions = {}
REPO_DIRECTORY = None


def safe_get(data, key, default=""):
    """Safely get a value from a dictionary, return default if not found or error."""
    try:
        if isinstance(data, dict):
            return data.get(key, default)
        return default
    except:
        return default


def get_json_path():
    """
    Resolves the path to riscv.json in the repository.
    Returns the Path object if file exists, otherwise skips the test.
    """
    # Print current working directory and script location for debugging
    cwd = Path.cwd()
    script_dir = Path(__file__).parent.resolve()
    print(f"Current working directory: {cwd}")
    print(f"Script directory: {script_dir}")

    # Try to find the repository root
    repo_root = os.environ.get("GITHUB_WORKSPACE", cwd)
    repo_root = Path(repo_root)

    llvm_json_path = repo_root / "ext" / "llvm-project" / "riscv.json"
    print(f"Looking for riscv.json at: {llvm_json_path}")

    if not llvm_json_path.is_file():
        print(f"\nNo 'riscv.json' found at {llvm_json_path}.")
        print("Tests will be skipped.\n")
        pytest.skip("riscv.json does not exist in the repository at the expected path.")

    return llvm_json_path


def get_yaml_directory():
    return "spec/std/isa/inst"


def load_inherited_variable(var_path, repo_dir):
    """Load variable definition from an inherited YAML file."""
    try:
        path, anchor = var_path.split("#")
        if anchor.startswith("/"):
            anchor = anchor[1:]

        full_path = os.path.join(repo_dir, path)

        if not os.path.exists(full_path):
            print(f"Warning: Inherited file not found: {full_path}")
            return None

        with open(full_path) as f:
            data = yaml.safe_load(f)

        for key in anchor.split("/"):
            if key in data:
                data = data[key]
            else:
                print(f"Warning: Anchor path {anchor} not found in {path}")
                return None

        return data
    except Exception as e:
        print(f"Error loading inherited variable {var_path}: {str(e)}")
        return None


def resolve_variable_definition(var, repo_dir):
    """Resolve variable definition, handling inheritance if needed."""
    if "location" in var:
        return var
    elif "$inherits" in var:
        print(f"Warning: Failed to resolve inheritance for variable: {var}")
    return None


def parse_location(loc_str):
    """Parse location string that may contain multiple ranges."""
    if not loc_str:
        return []

    loc_str = str(loc_str).strip()
    ranges = []

    for range_str in loc_str.split("|"):
        range_str = range_str.strip()
        if "-" in range_str:
            high, low = map(int, range_str.split("-"))
            ranges.append((high, low))
        else:
            try:
                val = int(range_str)
                ranges.append((val, val))
            except ValueError:
                print(f"Warning: Invalid location format: {range_str}")
                continue

    return ranges


def load_yaml_encoding(instr_name):
    """Load YAML encoding data for an instruction."""
    candidates = set()
    lower_name = instr_name.lower()
    candidates.add(lower_name)
    candidates.add(lower_name.replace("_", "."))

    yaml_file_path = None
    for cand in candidates:
        if cand in yaml_instructions:
            yaml_category = yaml_instructions[cand]
            yaml_file_path = os.path.join(REPO_DIRECTORY, yaml_category, cand + ".yaml")
            if os.path.isfile(yaml_file_path):
                break
            else:
                yaml_file_path = None

    if not yaml_file_path or not os.path.isfile(yaml_file_path):
        return None, None

    with open(yaml_file_path) as yf:
        ydata = yaml.safe_load(yf)

    encoding = safe_get(ydata, "encoding", {})
    yaml_match = safe_get(encoding, "match", None)
    yaml_vars = safe_get(encoding, "variables", [])

    return yaml_match, yaml_vars


def compare_yaml_json_encoding(
    instr_name, yaml_match, yaml_vars, json_encoding_str, repo_dir
):
    """Compare the YAML encoding with the JSON encoding."""
    if not yaml_match:
        return ["No YAML match field available for comparison."]
    if not json_encoding_str:
        return ["No JSON encoding available for comparison."]

    expected_length = (
        16 if instr_name.lower().startswith(("c_", "c.", "cm_", "cm.")) else 32
    )

    yaml_pattern_str = yaml_match.replace("-", ".")
    if len(yaml_pattern_str) != expected_length:
        return [
            f"YAML match pattern length is {len(yaml_pattern_str)}, expected {expected_length}. Cannot compare properly."
        ]

    yaml_var_positions = {}
    for var in yaml_vars or []:
        resolved_var = resolve_variable_definition(var, repo_dir)
        if not resolved_var or "location" not in resolved_var:
            print(
                f"Warning: Could not resolve variable definition for {var.get('name', 'unknown')}"
            )
            continue

        ranges = parse_location(resolved_var["location"])
        if ranges:
            yaml_var_positions[var["name"]] = ranges

    tokens = re.findall(r"(?:[01]|[A-Za-z0-9]+(?:\[\d+\]|\[\?\])?)", json_encoding_str)
    json_bits = []
    bit_index = expected_length - 1
    for t in tokens:
        json_bits.append((bit_index, t))
        bit_index -= 1

    if bit_index != -1:
        return [
            f"JSON encoding does not appear to be {expected_length} bits. Ends at bit {bit_index+1}."
        ]

    normalized_json_bits = []
    for pos, tt in json_bits:
        if re.match(r"vm\[[^\]]*\]", tt):
            tt = "vm"
        normalized_json_bits.append((pos, tt))
    json_bits = normalized_json_bits

    differences = []

    for b in range(expected_length):
        yaml_bit = yaml_pattern_str[expected_length - 1 - b]
        token = [tt for (pos, tt) in json_bits if pos == b]
        if not token:
            differences.append(f"Bit {b}: No corresponding JSON bit found.")
            continue
        json_bit_str = token[0]

        if yaml_bit in ["0", "1"]:
            if json_bit_str not in ["0", "1"]:
                differences.append(
                    f"Bit {b}: YAML expects fixed bit '{yaml_bit}' but JSON has '{json_bit_str}'"
                )
            elif json_bit_str != yaml_bit:
                differences.append(
                    f"Bit {b}: YAML expects '{yaml_bit}' but JSON has '{json_bit_str}'"
                )
        else:
            if json_bit_str in ["0", "1"]:
                differences.append(
                    f"Bit {b}: YAML variable bit but JSON is fixed '{json_bit_str}'"
                )

    for var_name, ranges in yaml_var_positions.items():
        for high, low in ranges:
            if high >= expected_length or low < 0:
                differences.append(
                    f"Variable {var_name}: location {high}-{low} is out of range for {expected_length}-bit instruction."
                )
                continue

            json_var_fields = []
            for bb in range(low, high + 1):
                token = [tt for (pos, tt) in json_bits if pos == bb]
                if token:
                    json_var_fields.append(token[0])
                else:
                    json_var_fields.append("?")

            field_names = set(
                re.findall(
                    r"([A-Za-z0-9]+)(?:\[\d+\]|\[\?\])?", " ".join(json_var_fields)
                )
            )
            if len(field_names) == 0:
                differences.append(
                    f"Variable {var_name}: No corresponding field found in JSON bits {high}-{low}"
                )
            elif len(field_names) > 1:
                differences.append(
                    f"Variable {var_name}: Multiple fields {field_names} found in JSON for bits {high}-{low}"
                )

    return differences


def get_yaml_instructions(repo_directory):
    """Recursively find all YAML files in the repository and load their encodings."""
    global yaml_instructions, REPO_DIRECTORY
    REPO_DIRECTORY = repo_directory
    yaml_instructions = {}

    for root, _, files in os.walk(repo_directory):
        for file in files:
            if file.endswith(".yaml"):
                instr_name = os.path.splitext(file)[0]
                relative_path = os.path.relpath(root, repo_directory)
                yaml_instructions[instr_name.lower()] = relative_path

    instructions_with_encodings = {}
    for instr_name_lower, path in yaml_instructions.items():
        yaml_match, yaml_vars = load_yaml_encoding(instr_name_lower)
        instructions_with_encodings[instr_name_lower] = {
            "category": path,
            "yaml_match": yaml_match,
            "yaml_vars": yaml_vars,
        }

    return instructions_with_encodings
