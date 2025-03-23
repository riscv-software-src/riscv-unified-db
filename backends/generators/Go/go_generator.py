#!/usr/bin/env python3
import os
import sys
import yaml
import logging
import pprint
import argparse

pp = pprint.PrettyPrinter(indent=2)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


def parse_extension_requirements(extensions_spec):
    """
    Parse the extension requirements from the definedBy field.
    Extensions can be specified as a string or a dictionary with allOf/oneOf/anyOf fields.
    Returns a function that checks if the given extensions satisfy the requirements.
    """
    if extensions_spec is None:
        # If no extension is specified, assume it's in the base ISA
        return lambda exts: "I" in exts

    if isinstance(extensions_spec, str):
        # Simple case: a single extension
        extension = extensions_spec
        if extension.startswith("RV"):
            if "I" in extension and "I" in exts:
                return lambda exts: True
            return lambda exts: False
        return lambda exts: extension in exts

    # Handle complex cases with allOf/oneOf/anyOf
    if "allOf" in extensions_spec:
        required = extensions_spec["allOf"]
        if isinstance(required, str):
            required = [required]
        return lambda exts: all(ext in exts for ext in required)

    if "oneOf" in extensions_spec:
        alternatives = extensions_spec["oneOf"]
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        return lambda exts: any(ext in exts for ext in alternatives)

    # Handle anyOf case (most common in the error output)
    if "anyOf" in extensions_spec:
        alternatives = extensions_spec["anyOf"]
        if isinstance(alternatives, str):
            alternatives = [alternatives]

        # Handle nested allOf conditions within anyOf
        def check_alternative(alt, exts):
            if isinstance(alt, str):
                return alt in exts
            elif isinstance(alt, dict) and "allOf" in alt:
                reqs = alt["allOf"]
                if isinstance(reqs, str):
                    reqs = [reqs]
                return all(r in exts for r in reqs)
            return False

        return lambda exts: any(check_alternative(alt, exts) for alt in alternatives)

    # Handle version specifications
    if "name" in extensions_spec and "version" in extensions_spec:
        extension = extensions_spec["name"]
        # We don't actually check the version, just the extension name
        return lambda exts: extension in exts

    # Default case if we can't parse the requirements
    logging.debug(f"Unrecognized extension specification format: {extensions_spec}")
    # Let's be more permissive for now - we'll include instructions
    # that have an unrecognized format rather than excluding them
    return lambda exts: True


def load_instructions(root_dir, enabled_extensions, include_all=False):
    """
    Recursively walk through root_dir, load YAML files that define an instruction,
    filter by enabled extensions, and collect them into a dictionary keyed by the instruction name.

    If include_all is True, extension filtering is bypassed.
    """
    instr_dict = {}
    found_files = 0
    found_instructions = 0
    extension_filtered = 0
    encoding_filtered = 0

    logging.info(f"Searching for instruction files in {root_dir}")

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
                logging.error(
                    f"Missing 'encoding' field in instruction {name} in {path}"
                )
                encoding_filtered += 1
                continue

            # Determine which encoding to use:
            if isinstance(encoding, dict):
                if "RV64" in encoding:
                    encoding_to_use = encoding["RV64"]
                elif "RV32" in encoding:
                    msg = f"Skipping {name} because it has only RV32 encoding in {path}"
                    logging.debug(msg)
                    encoding_filtered += 1
                    continue
                elif "match" in encoding:
                    encoding_to_use = encoding
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

            instr_dict[name] = {"match": match_str}

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
    else:
        logging.warning(f"No instruction definitions found in {root_dir}")

    return instr_dict


def load_csrs(csr_root, enabled_extensions, include_all=False):
    """
    Recursively walk through csr_root, load YAML files that define a CSR,
    filter by enabled extensions, and collect them into a dictionary mapping
    each address (as an integer) to the CSR name.

    If include_all is True, extension filtering is bypassed.
    """
    csrs = {}
    found_files = 0
    found_csrs = 0
    extension_filtered = 0
    address_errors = 0

    logging.info(f"Searching for CSR files in {csr_root}")

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
            if not address and not data.get("indirect_address"):
                logging.error(
                    f"Missing 'address' or 'indirect_address' field in CSR {name} in {path}"
                )
                address_errors += 1
                continue

            # If include_all is True, skip extension filtering
            if not include_all:
                # Check if this CSR is defined by an enabled extension
                definedBy = data.get("definedBy")
                if definedBy is None:
                    logging.error(f"Missing 'definedBy' field in CSR {name} in {path}")
                    extension_filtered += 1
                    continue

                logging.debug(f"CSR {name} definedBy: {definedBy}")
                meets_extension_req = parse_extension_requirements(definedBy)
                if not meets_extension_req(enabled_extensions):
                    msg = f"Skipping CSR {name} because its extension is not enabled"
                    logging.debug(msg)
                    extension_filtered += 1
                    continue

            # If we're here, we've passed all checks
            try:
                # Use address if available, otherwise use indirect_address
                addr_to_use = (
                    address if address is not None else data.get("indirect_address")
                )
                if isinstance(addr_to_use, int):
                    addr_int = addr_to_use
                else:
                    addr_int = int(addr_to_use, 0)
                csrs[addr_int] = name.upper()
            except Exception as e:
                logging.error(f"Error parsing address {addr_to_use} in {path}: {e}")
                address_errors += 1
                continue

    if found_csrs > 0:
        logging.info(f"Found {found_csrs} CSR definitions in {found_files} files")
        if extension_filtered > 0:
            logging.info(f"Filtered out {extension_filtered} CSRs by extension")
        if address_errors > 0:
            logging.info(f"Filtered out {address_errors} CSRs due to address issues")
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


def make_go(instr_dict, csrs, output_file="inst.go"):
    """
    Generate a Go source file with the instruction encodings followed by
    a map of CSR names and addresses.
    """
    args = " ".join(sys.argv)
    prelude = f"// Code generated by {args}; DO NOT EDIT.\n"
    prelude += """package riscv

import "cmd/internal/obj"

type inst struct {
	opcode uint32
	funct3 uint32
	rs1    uint32
	rs2    uint32
    csr    int64
	funct7 uint32
}

func encode(a obj.As) *inst {
	switch a {
"""

    instr_str = ""
    # Process instructions in sorted order (by name)
    for name, info in sorted(instr_dict.items(), key=lambda x: x[0].upper()):
        match_str = info["match"]
        enc_match = parse_match(match_str)
        opcode = (enc_match >> 0) & ((1 << 7) - 1)
        funct3 = (enc_match >> 12) & ((1 << 3) - 1)
        rs1 = (enc_match >> 15) & ((1 << 5) - 1)
        rs2 = (enc_match >> 20) & ((1 << 5) - 1)
        csr_val = (enc_match >> 20) & ((1 << 12) - 1)
        funct7 = (enc_match >> 25) & ((1 << 7) - 1)
        # Create the instruction case name. For example, "bclri" becomes "ABCLRI"
        instr_case = f"A{name.upper().replace('.','')}"
        instr_str += f"""  case {instr_case}:
    return &inst{{ {hex(opcode)}, {hex(funct3)}, {hex(rs1)}, {hex(rs2)}, {signed(csr_val,12)}, {hex(funct7)} }}
"""
    instructions_end = """  }
	return nil
}
"""

    # Build the CSR map block.
    csrs_map_str = "var csrs = map[uint16]string {\n"
    for addr in sorted(csrs.keys()):
        csrs_map_str += f'  {hex(addr)} : "{csrs[addr]}",\n'
    csrs_map_str += "}\n"

    go_code = prelude + instr_str + instructions_end + "\n" + csrs_map_str

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(go_code)
    logging.info(
        f"Generated {output_file} with {len(instr_dict)} instructions and {len(csrs)} CSRs"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate Go code for RISC-V instructions and CSRs filtered by extensions"
    )
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
    parser.add_argument("--output", default="inst.go", help="Output Go file name")
    parser.add_argument(
        "--extensions",
        default="",
        help="Comma-separated list of enabled extensions (e.g., I,M,A,F,D,C). If empty, all instructions will be included.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--include-all",
        "-a",
        action="store_true",
        help="Include all instructions, ignoring extension filtering",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check if we should include all instructions
    include_all = args.include_all or not args.extensions

    # Parse enabled extensions
    if include_all:
        enabled_extensions = []
        logging.info(
            "Including all instructions and CSRs (extension filtering disabled)"
        )
    else:
        enabled_extensions = [
            ext.strip() for ext in args.extensions.split(",") if ext.strip()
        ]
        logging.info(f"Enabled extensions: {', '.join(enabled_extensions)}")

    # Check if the directories exist
    if not os.path.isdir(args.inst_dir):
        logging.error(f"Instruction directory not found: {args.inst_dir}")
        sys.exit(1)
    if not os.path.isdir(args.csr_dir):
        logging.warning(f"CSR directory not found: {args.csr_dir}")

    # Load instructions filtered by extensions or all instructions
    instr_dict = load_instructions(args.inst_dir, enabled_extensions, include_all)
    if not instr_dict:
        logging.error("No instructions found or all were filtered out.")
        logging.error(
            "Try using --verbose to see more details about the filtering process."
        )
        sys.exit(1)
    logging.info(f"Loaded {len(instr_dict)} instructions")

    # Load CSRs filtered by extensions or all CSRs
    csrs = load_csrs(args.csr_dir, enabled_extensions, include_all)
    if not csrs:
        logging.warning("No CSRs found or all were filtered out.")
    else:
        logging.info(f"Loaded {len(csrs)} CSRs")

    # Generate the Go code
    make_go(instr_dict, csrs, args.output)


if __name__ == "__main__":
    main()
