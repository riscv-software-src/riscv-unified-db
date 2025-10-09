#!/usr/bin/env python3
import os
import yaml
import logging
import pprint

pp = pprint.PrettyPrinter(indent=2)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def check_requirement(req, exts):
    if isinstance(req, str):
        return req in exts
    elif isinstance(req, dict) and "name" in req:
        # If it has a name field, just match the extension name and ignore version
        return req["name"] in exts
    return False


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
                        (
                            int(location.split("-")[0])
                            if "-" in location
                            else int(location)
                        )
                        for location in split_location
                    )
                    valid_locations.append(high)
                except (ValueError, IndexError):
                    raise ValueError(
                        f"Invalid location format: {field_data['location']}"
                    )
            elif isinstance(field_data["location"], int):
                try:
                    valid_locations.append(field_data["location"])
                except (ValueError, IndexError):
                    raise ValueError(
                        f"Invalid location format: {field_data['location']}"
                    )
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
                        raise ValueError(
                            f"Invalid location format: {var_data['location']}"
                        )
                elif isinstance(var_data["location"], int):
                    try:
                        valid_locations.append(var_data["location"])
                    except (ValueError, IndexError):
                        raise ValueError(
                            f"Invalid location format: {var_data['location']}"
                        )
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
                    logging.warning(f"Invalid bit range: {location}")
                    continue  # Skip invalid bit ranges

                binary_value = format(field_data["value"], f"0{high - low + 1}b")
                match_bits[width - high - 1 : width - low] = binary_value
            except (ValueError, IndexError):
                raise ValueError(f"Error processing opcode field: {field_data}")

    return "".join(match_bits)


def parse_extension_requirements(extensions_spec):
    """
    Parse the extension requirements from the definedBy field.
    Extensions can be specified as a string or a dictionary with allOf/oneOf/anyOf fields.
    Returns a function that checks if the given extensions satisfy the requirements.
    """
    if extensions_spec is None:
        # If definedBy is None, we should never match
        logging.error(f"Missing 'definedBy' field")
        return lambda exts: False

    if isinstance(extensions_spec, str):
        # Simple case: a single extension
        extension = extensions_spec
        if extension.startswith("RV"):
            # Extract the actual extension part from RV prefix
            if extension.startswith("RV32") or extension.startswith("RV64"):
                ext_parts = extension[4:]
            else:
                ext_parts = extension[2:]
            # Check if any part matches enabled extensions
            return lambda enabled_exts: any(
                ext_part in enabled_exts for ext_part in ext_parts
            )
        return lambda exts: extension in exts

    # Handle complex cases with allOf/oneOf/anyOf
    if "allOf" in extensions_spec:
        required = extensions_spec["allOf"]
        if isinstance(required, str):
            required = [required]

        # Process each requirement, which could be a string or a dict with name/version
        return lambda exts: all(check_requirement(req, exts) for req in required)

    if "oneOf" in extensions_spec:
        alternatives = extensions_spec["oneOf"]
        if isinstance(alternatives, str):
            alternatives = [alternatives]

        # Process each alternative, which could be a string or a dict with name/version
        def check_alternative_one_of(alt, exts):
            if isinstance(alt, str):
                return alt in exts
            elif isinstance(alt, dict) and "name" in alt:
                return alt["name"] in exts
            return False

        return lambda exts: any(
            check_alternative_one_of(alt, exts) for alt in alternatives
        )

    # Handle anyOf case (most common in the error output)
    if "anyOf" in extensions_spec:
        alternatives = extensions_spec["anyOf"]
        if isinstance(alternatives, str):
            alternatives = [alternatives]

        # Process each alternative, which could be a string, dict with name/version, or nested allOf
        def check_alternative(alt, exts):
            if isinstance(alt, str):
                return alt in exts
            elif isinstance(alt, dict):
                if "allOf" in alt:
                    reqs = alt["allOf"]
                    if isinstance(reqs, str):
                        reqs = [reqs]
                    return all(check_requirement(r, exts) for r in reqs)
                elif "name" in alt:
                    return alt["name"] in exts
            return False

        return lambda exts: any(check_alternative(alt, exts) for alt in alternatives)

    # Handle direct name/version specification
    if "name" in extensions_spec and "version" in extensions_spec:
        extension = extensions_spec["name"]
        # We don't actually check the version, just the extension name
        return lambda exts: extension in exts

    # Default case if we can't parse the requirements
    logging.debug(f"Unrecognized extension specification format: {extensions_spec}")
    # Let's be more permissive for now - we'll include instructions
    # that have an unrecognized format rather than excluding them
    return lambda exts: True


def load_instructions(
    root_dir, enabled_extensions, include_all=False, target_arch="RV64"
):
    """
    Recursively walk through root_dir, load YAML files that define an instruction,
    filter by enabled extensions, and collect them into a dictionary keyed by the instruction name.

    If include_all is True, extension filtering is bypassed.
    target_arch can be "RV32", "RV64", or "BOTH".
    """
    instr_dict = {}
    found_files = 0
    found_instructions = 0
    extension_filtered = 0
    encoding_filtered = 0

    logging.info(
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
                    data = yaml.safe_load(f)
            except Exception as e:
                logging.error(f"Error parsing {path}: {e}")
                continue

            if data.get("kind") != "instruction":
                continue

            found_instructions += 1
            name = data.get("name")
            if not name:
                logging.error(f"Missing 'name' field in {path}")
                continue

            # If include_all is True, skip extension filtering
            if not include_all:
                # Check if this instruction is defined by an enabled extension
                definedBy = data.get("definedBy")
                if definedBy is None:
                    logging.error(
                        f"Missing 'definedBy' field in instruction {name} in {path}"
                    )
                    extension_filtered += 1
                    continue

                logging.debug(f"Instruction {name} definedBy: {definedBy}")
                meets_extension_req = parse_extension_requirements(definedBy)
                if not meets_extension_req(enabled_extensions):
                    msg = f"Skipping {name} because its extension is not enabled"
                    logging.debug(msg)
                    extension_filtered += 1
                    continue

                # Check if this instruction is excluded by an enabled extension
                excludedBy = data.get("excludedBy")
                if excludedBy:
                    exclusion_check = parse_extension_requirements(excludedBy)
                    if exclusion_check(enabled_extensions):
                        msg = f"Skipping {name} because it's excluded by an enabled extension"
                        logging.debug(msg)
                        extension_filtered += 1
                        continue

            encoding = data.get("encoding", {})
            if not encoding:
                # Check if this instruction uses the new schema with a 'format' field
                format_field = data.get("format")
                if not format_field:
                    logging.error(
                        f"Missing 'encoding' field in instruction {name} in {path}"
                    )
                    encoding_filtered += 1
                    continue

                # Try to build a match string from the format field
                match_string = build_match_from_format(format_field)
                if not match_string:
                    logging.error(
                        f"Could not build encoding from format field in instruction {name} in {path}"
                    )
                    encoding_filtered += 1
                    continue

                # Create a synthetic encoding compatible with existing logic
                encoding = {"match": match_string, "variables": []}
                logging.debug(f"Built encoding from format field for {name}")

            # Check if the instruction specifies a base architecture constraint
            base = data.get("base")
            if base is not None:
                if (base == 32 and target_arch not in ["RV32", "BOTH"]) or (
                    base == 64 and target_arch not in ["RV64", "BOTH"]
                ):
                    msg = f"Skipping {name} because it requires base {base} which doesn't match target arch {target_arch}"
                    logging.debug(msg)
                    encoding_filtered += 1
                    continue

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
                        if rv64_match:
                            instr_dict[name] = {
                                "match": rv64_match
                            }  # RV64 gets the default name

                        # Process RV32 encoding with a _rv32 suffix
                        rv32_match = rv32_encoding.get("match")
                        if rv32_match:
                            instr_dict[f"{name}_rv32"] = {"match": rv32_match}

                        continue  # Skip the rest of the loop as we've already added the encodings
                elif "RV64" in encoding:
                    if target_arch in ["RV64", "BOTH"]:
                        encoding_to_use = encoding["RV64"]
                        instr_key = name
                    else:
                        msg = f"Skipping {name} because it has only RV64 encoding in {path}"
                        logging.debug(msg)
                        encoding_filtered += 1
                        continue
                elif "RV32" in encoding:
                    if target_arch in ["RV32", "BOTH"]:
                        encoding_to_use = encoding["RV32"]
                        instr_key = f"{name}_rv32" if target_arch == "BOTH" else name
                    else:
                        msg = f"Skipping {name} because it has only RV32 encoding in {path}"
                        logging.debug(msg)
                        encoding_filtered += 1
                        continue
                elif "match" in encoding:
                    # Generic encoding, no specific architecture
                    encoding_to_use = encoding
                    instr_key = name
                else:
                    msg = f"Skipping {name} because its encoding in {path} has no recognized match field."
                    logging.warning(msg)
                    encoding_filtered += 1
                    continue
            else:
                msg = f"Skipping {name} because its encoding in {path} is not a dictionary."
                logging.warning(msg)
                encoding_filtered += 1
                continue

            match_str = encoding_to_use.get("match")
            if not match_str:
                msg = f"Skipping {name} because 'match' field is missing in {path}"
                logging.warning(msg)
                encoding_filtered += 1
                continue

            instr_dict[instr_key] = {"match": match_str}

    if found_instructions > 0:
        logging.info(
            f"Found {found_instructions} instruction definitions in {found_files} files"
        )
        if extension_filtered > 0:
            logging.info(f"Filtered out {extension_filtered} instructions by extension")
        if encoding_filtered > 0:
            logging.info(
                f"Filtered out {encoding_filtered} instructions due to encoding issues"
            )
        logging.info(f"Added {len(instr_dict)} instruction encodings to the output")
    else:
        logging.warning(f"No instruction definitions found in {root_dir}")

    return instr_dict


def load_csrs(csr_root, enabled_extensions, include_all=False, target_arch="RV64"):
    """
    Recursively walk through csr_root, load YAML files that define a CSR,
    filter by enabled extensions, and collect them into a dictionary mapping
    each address (as an integer) to the CSR name.

    If include_all is True, extension filtering is bypassed.
    target_arch can be "RV32", "RV64", or "BOTH".
    """
    csrs = {}
    found_files = 0
    found_csrs = 0
    extension_filtered = 0
    arch_filtered = 0
    address_errors = 0

    logging.info(
        f"Searching for CSR files in {csr_root} for target architecture {target_arch}"
    )

    for dirpath, _, filenames in os.walk(csr_root):
        for fname in filenames:
            if not fname.endswith(".yaml"):
                continue
            found_files += 1
            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                logging.error(f"Error parsing CSR file {path}: {e}")
                continue

            if data.get("kind") != "csr":
                continue

            found_csrs += 1
            name = data.get("name")
            if not name:
                logging.error(f"Missing 'name' field in {path}")
                continue

            address = data.get("address")
            indirect_address = data.get("indirect_address")

            if not address and not indirect_address:
                logging.error(
                    f"Missing 'address' or 'indirect_address' field in CSR {name} in {path}"
                )
                address_errors += 1
                continue

            # Check if the CSR has a base constraint (32 or 64)
            base = data.get("base")
            if base:
                if base == 32 and target_arch not in ["RV32", "BOTH"]:
                    logging.debug(f"Skipping CSR {name} because it requires RV32 base")
                    arch_filtered += 1
                    continue
                elif base == 64 and target_arch not in ["RV64", "BOTH"]:
                    logging.debug(f"Skipping CSR {name} because it requires RV64 base")
                    arch_filtered += 1
                    continue

            # If include_all is True, skip extension filtering
            if not include_all:
                # Check if this CSR is defined by an enabled extension
                definedBy = data.get("definedBy")

                # If definedBy is missing, log a warning but don't skip
                # This is different from instructions where we're more strict
                if definedBy is None:
                    logging.warning(
                        f"Missing 'definedBy' field in CSR {name} in {path}, including anyway"
                    )
                else:
                    logging.debug(f"CSR {name} definedBy: {definedBy}")
                    meets_extension_req = parse_extension_requirements(definedBy)
                    if not meets_extension_req(enabled_extensions):
                        msg = (
                            f"Skipping CSR {name} because its extension is not enabled"
                        )
                        logging.debug(msg)
                        extension_filtered += 1
                        continue

            # If we're here, we've passed all checks
            try:
                # Use address if available, otherwise use indirect_address
                addr_to_use = address if address is not None else indirect_address
                if isinstance(addr_to_use, int):
                    addr_int = addr_to_use
                else:
                    addr_int = int(addr_to_use, 0)

                # For BOTH architecture, add suffix to RV32-specific CSRs
                if target_arch == "BOTH" and base == 32:
                    csrs[addr_int] = f"{name.upper()}.RV32"
                else:
                    csrs[addr_int] = name.upper()
            except Exception as e:
                logging.error(f"Error parsing address {addr_to_use} in {path}: {e}")
                address_errors += 1
                continue

    if found_csrs > 0:
        logging.info(f"Found {found_csrs} CSR definitions in {found_files} files")
        if extension_filtered > 0:
            logging.info(f"Filtered out {extension_filtered} CSRs by extension")
        if arch_filtered > 0:
            logging.info(
                f"Filtered out {arch_filtered} CSRs by architecture constraints"
            )
        if address_errors > 0:
            logging.info(f"Filtered out {address_errors} CSRs due to address issues")
        logging.info(f"Added {len(csrs)} CSRs to the output")
    else:
        logging.warning(f"No CSR definitions found in {csr_root}")

    return csrs


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
