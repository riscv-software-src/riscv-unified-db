#!/usr/bin/env python3
import json
import logging
import os
import pprint

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

YAML_SAFE = YAML(typ="safe")

pp = pprint.PrettyPrinter(indent=2)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")
LOGGER = logging.getLogger(__name__)


XLENS = {"RV32": {32}, "RV64": {64}, "BOTH": {32, 64}}


def extension_condition_holds(cond, enabled_extensions):
    """
    Evaluate the inner part of an {extension: ...} condition: a {name, version}
    requirement, or an allOf/anyOf/oneOf/noneOf/not aggregation of them.
    Only the extension name is checked; versions are ignored.
    """
    if cond.get("name") is not None:
        return cond["name"] in enabled_extensions
    if "allOf" in cond:
        return all(extension_condition_holds(c, enabled_extensions) for c in cond["allOf"])
    if "anyOf" in cond or "oneOf" in cond:
        alternatives = cond["anyOf"] if "anyOf" in cond else cond["oneOf"]
        return any(extension_condition_holds(c, enabled_extensions) for c in alternatives)
    if "noneOf" in cond:
        return not any(extension_condition_holds(c, enabled_extensions) for c in cond["noneOf"])
    if "not" in cond:
        return not extension_condition_holds(cond["not"], enabled_extensions)
    LOGGER.warning(f"Unrecognized extension condition, including anyway: {cond}")
    return True


def condition_holds(condition, enabled_extensions, target_arch):
    """
    Evaluate a "definedBy" condition.
    Conditions can be a singleton YAML object like "extension" or "xlen", or a
    hierarchical dictionary including allOf/oneOf/anyOf aggregations of objects.

    enabled_extensions is the list of enabled extension names, or None to accept
    every extension (--include-all). target_arch is "RV32", "RV64", or "BOTH".
    """
    if "extension" in condition:
        return enabled_extensions is None or extension_condition_holds(
            condition["extension"], enabled_extensions
        )
    if "xlen" in condition:
        return condition["xlen"] in XLENS[target_arch]
    if "param" in condition:
        # Parameter constraints cannot be evaluated here; treat them as satisfied
        return True
    if "allOf" in condition:
        return all(condition_holds(c, enabled_extensions, target_arch) for c in condition["allOf"])
    if "anyOf" in condition or "oneOf" in condition:
        alternatives = condition["anyOf"] if "anyOf" in condition else condition["oneOf"]
        return any(condition_holds(c, enabled_extensions, target_arch) for c in alternatives)
    if "noneOf" in condition:
        return not any(
            condition_holds(c, enabled_extensions, target_arch) for c in condition["noneOf"]
        )
    if "not" in condition:
        return not condition_holds(condition["not"], enabled_extensions, target_arch)
    LOGGER.warning(f"Unrecognized definedBy condition, including anyway: {condition}")
    return True


def build_match_from_format(format_field):
    """
    Build a match string from the format field in the new schema.
    """
    if not format_field or "opcodes" not in format_field:
        return None

    # Determine instruction width by finding maximum bit position
    valid_locations = []

    opcodes = format_field["opcodes"]
    # Check opcodes
    for field_data in opcodes.values():
        if isinstance(field_data, dict) and "location" in field_data:
            if isinstance(field_data["location"], str):
                try:
                    location = field_data["location"]
                    split_location = location.split("|")
                    high = max(
                        (int(location.split("-")[0]) if "-" in location else int(location))
                        for location in split_location
                    )
                    valid_locations.append(high)
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid location format: {field_data['location']}")
            elif isinstance(field_data["location"], int):
                try:
                    valid_locations.append(field_data["location"])
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid location format: {field_data['location']}")
            else:
                raise ValueError(f"Unknown location format: {field_data['location']}")

    if "variables" in format_field:
        variables = format_field["variables"]
        # Check variables
        for var_data in variables.values():
            if isinstance(var_data, dict) and "location" in var_data:
                if isinstance(var_data["location"], str):
                    try:
                        location = var_data["location"]
                        if "-" in location:
                            high = int(location.split("-")[0])
                        else:
                            high = int(location)
                        valid_locations.append(high)
                    except (ValueError, IndexError):
                        raise ValueError(f"Invalid location format: {var_data['location']}")
                elif isinstance(var_data["location"], int):
                    try:
                        valid_locations.append(var_data["location"])
                    except (ValueError, IndexError):
                        raise ValueError(f"Invalid location format: {var_data['location']}")
                else:
                    raise ValueError(f"Invalid location format: {var_data['location']}")

    if not valid_locations:
        raise ValueError("No valid bit locations found in format field")

    max_bit = max(valid_locations)

    # Set instruction width based on maximum bit position
    width = max_bit + 1
    match_bits = ["-"] * width

    # Populate match string with opcode bits
    for field_data in opcodes.values():
        if isinstance(field_data, dict):
            try:
                location = field_data["location"]
                if isinstance(location, str) and "-" in location:
                    high, low = map(int, location.split("-"))
                else:
                    high = low = int(location)

                if high < low or high >= width:
                    LOGGER.warning(f"Invalid bit range: {location}")
                    continue  # Skip invalid bit ranges

                binary_value = format(field_data["value"], f"0{high - low + 1}b")
                match_bits[width - high - 1 : width - low] = binary_value
            except (ValueError, IndexError):
                raise ValueError(f"Error processing opcode field: {field_data}")

    return "".join(match_bits)


def load_instructions(root_dir, enabled_extensions, include_all=False, target_arch="RV64"):
    """
    Recursively walk through root_dir, load YAML files that define an instruction,
    filter by enabled extensions, and collect them into a dictionary keyed by the instruction name.

    If include_all is True, extension filtering is bypassed (xlen filtering still applies).
    target_arch can be "RV32", "RV64", or "BOTH".
    """
    instr_dict = {}
    found_files = 0
    found_instructions = 0
    condition_filtered = 0
    encoding_filtered = 0

    LOGGER.info(
        f"Searching for instruction files in {root_dir} for target architecture {target_arch}"
    )

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue
            found_files += 1
            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = YAML_SAFE.load(f)
            except (OSError, YAMLError) as e:
                LOGGER.error(f"Error parsing {path}: {e}")
                continue

            if data.get("kind") != "instruction":
                continue

            found_instructions += 1
            name = data.get("name")
            if not name:
                LOGGER.error(f"Missing 'name' field in {path}")
                continue

            # Check that this instruction is defined by an enabled extension for the target arch.
            # With include_all, only the xlen part of the condition is enforced.
            definedBy = data.get("definedBy")
            if definedBy is None:
                LOGGER.error(f"Missing 'definedBy' field in instruction {name} in {path}")
                condition_filtered += 1
                continue
            LOGGER.debug(f"Instruction {name} definedBy: {definedBy}")
            if not condition_holds(
                definedBy, None if include_all else enabled_extensions, target_arch
            ):
                LOGGER.debug(f"Skipping {name} because its definedBy condition is not satisfied")
                condition_filtered += 1
                continue

            encoding = data.get("encoding", {})
            if not encoding:
                # Check if this instruction uses the new schema with a 'format' field
                format_field = data.get("format")
                if not format_field:
                    LOGGER.error(f"Missing 'encoding' field in instruction {name} in {path}")
                    encoding_filtered += 1
                    continue

                # Try to build a match string from the format field
                match_string = build_match_from_format(format_field)
                if not match_string:
                    LOGGER.error(
                        f"Could not build encoding from format field in instruction {name} in {path}"
                    )
                    encoding_filtered += 1
                    continue

                # Create a synthetic encoding compatible with existing logic
                encoding = {"match": match_string, "variables": []}
                LOGGER.debug(f"Built encoding from format field for {name}")

            # Determine which encoding to use based on target architecture
            if isinstance(encoding, dict):
                if "RV64" in encoding and "RV32" in encoding:
                    # Instruction has both RV32 and RV64 encodings
                    if target_arch == "RV64":
                        encoding_to_use = encoding["RV64"]
                        instr_key = name
                    elif target_arch == "RV32":
                        encoding_to_use = encoding["RV32"]
                        instr_key = name
                    else:  # BOTH
                        # For "BOTH", include both encodings with suitable naming
                        rv64_encoding = encoding["RV64"]
                        rv32_encoding = encoding["RV32"]

                        # Process RV64 encoding
                        rv64_match = rv64_encoding.get("match")
                        rv32_match = rv32_encoding.get("match")

                        if rv64_match:
                            instr_dict[name] = {"match": rv64_match}  # RV64 gets the default name

                        if rv32_match and rv32_match != rv64_match:
                            # Process RV32 encoding with a _rv32 suffix
                            instr_dict[f"{name}_rv32"] = {"match": rv32_match}

                        continue  # Skip the rest of the loop as we've already added the encodings
                elif "RV64" in encoding:
                    if target_arch in ["RV64", "BOTH"]:
                        encoding_to_use = encoding["RV64"]
                        instr_key = name
                    else:
                        msg = f"Skipping {name} because it has only RV64 encoding in {path}"
                        LOGGER.debug(msg)
                        encoding_filtered += 1
                        continue
                elif "RV32" in encoding:
                    if target_arch in ["RV32", "BOTH"]:
                        encoding_to_use = encoding["RV32"]
                        instr_key = f"{name}_rv32" if target_arch == "BOTH" else name
                    else:
                        msg = f"Skipping {name} because it has only RV32 encoding in {path}"
                        LOGGER.debug(msg)
                        encoding_filtered += 1
                        continue
                elif "match" in encoding:
                    # Generic encoding, no specific architecture
                    encoding_to_use = encoding
                    instr_key = name
                else:
                    msg = f"Skipping {name} because its encoding in {path} has no recognized match field."
                    LOGGER.warning(msg)
                    encoding_filtered += 1
                    continue
            else:
                msg = f"Skipping {name} because its encoding in {path} is not a dictionary."
                LOGGER.warning(msg)
                encoding_filtered += 1
                continue

            match_str = encoding_to_use.get("match")
            if not match_str:
                msg = f"Skipping {name} because 'match' field is missing in {path}"
                LOGGER.warning(msg)
                encoding_filtered += 1
                continue

            instr_dict[instr_key] = {"match": match_str}

    if found_instructions > 0:
        LOGGER.info(f"Found {found_instructions} instruction definitions in {found_files} files")
        if condition_filtered > 0:
            LOGGER.info(f"Filtered out {condition_filtered} instructions by definedBy condition")
        if encoding_filtered > 0:
            LOGGER.info(f"Filtered out {encoding_filtered} instructions due to encoding issues")
        LOGGER.info(f"Added {len(instr_dict)} instruction encodings to the output")
    else:
        LOGGER.warning(f"No instruction definitions found in {root_dir}")

    return instr_dict


def load_csrs(csr_root, enabled_extensions, include_all=False, target_arch="RV64"):
    """
    Recursively walk through csr_root, load YAML files that define a CSR,
    filter by enabled extensions, and collect them into a dictionary mapping
    each address (as an integer) to the CSR name.

    If include_all is True, extension filtering is bypassed (xlen filtering still applies).
    target_arch can be "RV32", "RV64", or "BOTH".
    """
    csrs = {}
    found_files = 0
    found_csrs = 0
    condition_filtered = 0
    address_errors = 0

    LOGGER.info(f"Searching for CSR files in {csr_root} for target architecture {target_arch}")

    for dirpath, _, filenames in os.walk(csr_root):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue
            found_files += 1
            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = YAML_SAFE.load(f)
            except (OSError, YAMLError) as e:
                LOGGER.error(f"Error parsing CSR file {path}: {e}")
                continue

            if data.get("kind") != "csr":
                continue

            found_csrs += 1
            name = data.get("name")
            if not name:
                LOGGER.error(f"Missing 'name' field in {path}")
                continue

            address = data.get("address")
            indirect_address = data.get("indirect_address")

            if not address and not indirect_address:
                LOGGER.error(
                    f"Missing 'address' or 'indirect_address' field in CSR {name} in {path}"
                )
                address_errors += 1
                continue

            # Check that this CSR is defined by an enabled extension for the target arch.
            # With include_all, only the xlen part of the condition is enforced.
            definedBy = data.get("definedBy")
            if definedBy is None:
                LOGGER.error(f"Missing 'definedBy' field in CSR {name} in {path}")
                condition_filtered += 1
                continue
            LOGGER.debug(f"CSR {name} definedBy: {definedBy}")
            if not condition_holds(
                definedBy, None if include_all else enabled_extensions, target_arch
            ):
                LOGGER.debug(
                    f"Skipping CSR {name} because its definedBy condition is not satisfied"
                )
                condition_filtered += 1
                continue

            # If we're here, we've passed all checks
            try:
                # Use address if available, otherwise use indirect_address
                addr_to_use = address if address is not None else indirect_address
                if isinstance(addr_to_use, int):
                    addr_int = addr_to_use
                else:
                    addr_int = int(addr_to_use, 0)

                csrs[addr_int] = name.upper()
            except (TypeError, ValueError) as e:
                LOGGER.error(f"Error parsing address {addr_to_use} in {path}: {e}")
                address_errors += 1
                continue

    if found_csrs > 0:
        LOGGER.info(f"Found {found_csrs} CSR definitions in {found_files} files")
        if condition_filtered > 0:
            LOGGER.info(f"Filtered out {condition_filtered} CSRs by definedBy condition")
        if address_errors > 0:
            LOGGER.info(f"Filtered out {address_errors} CSRs due to address issues")
        LOGGER.info(f"Added {len(csrs)} CSRs to the output")
    else:
        LOGGER.warning(f"No CSR definitions found in {csr_root}")

    return csrs


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
                if not isinstance(code, dict):
                    continue
                num = code.get("num")
                name = code.get("name")
                if num is not None and name is not None:
                    sanitized_name = (
                        name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                    )
                    exception_codes.append((num, sanitized_name))

            LOGGER.info(
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

        except (OSError, json.JSONDecodeError) as e:
            LOGGER.error(f"Error loading resolved codes file {resolved_codes_file}: {e}")
    # Logging an error and skipping the exception cause generation if no resolved codes file found
    else:
        LOGGER.error(f"Resolved codes file not found: {resolved_codes_file}")
        return

    if found_extensions > 0:
        LOGGER.info(f"Found {found_extensions} extension definitions in {found_files} files")
        LOGGER.info(f"Added {len(exception_codes)} exception codes to the output")
    else:
        LOGGER.warning(f"No extension definitions found in {ext_dir}")

    # Sort by exception code number and deduplicate
    seen_nums = set()
    unique_codes = []
    for num, name in sorted(exception_codes, key=lambda x: x[0]):
        if num not in seen_nums:
            seen_nums.add(num)
            unique_codes.append((num, name))

    return unique_codes


def parse_match(match_str):
    """
    Convert the bit pattern string to an integer.
    Replace all '-' (variable bits) with '0' so that only constant bits are set.
    """
    binary_str = "".join("0" if c == "-" else c for c in match_str)
    return int(binary_str, 2)


# Returns signed interpretation of a value within a given width.
def signed(value: int, width: int) -> int:
    return value if 0 <= value < (1 << (width - 1)) else value - (1 << width)


if __name__ == "__main__":
    print("This module is not meant to be run directly.")
    print("Please use go_generator.py instead.")
