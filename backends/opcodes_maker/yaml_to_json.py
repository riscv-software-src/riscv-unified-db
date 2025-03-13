import re
from typing import List, Dict, Union, Any
import argparse
import os
import sys
import yaml
import json
from re import findall

# Mapping of instructions to their canonical fields
#  needed for compressed instructions since their immediates have a syntax impossible (to the best of my knowledge) to replicate
HARDCODED_FIELDS = {
    # Compressed instructions
    "c_addi": ["rd_rs1_n0", "c_nzimm6lo", "c_nzimm6hi"],
    "c_addi16sp": ["c_nzimm10hi", "c_nzimm10lo"],
    "c_addi4spn": ["rd_p", "c_nzuimm10"],
    "c_addiw": ["rd_rs1_n0", "c_imm6lo", "c_imm6hi"],
    "c_andi": ["rd_rs1_p", "c_imm6hi", "c_imm6lo"],
    "c_beqz": ["rs1_p", "c_bimm9lo", "c_bimm9hi"],
    "c_bnez": ["rs1_p", "c_bimm9lo", "c_bimm9hi"],
    "c_fld": ["rd_p", "rs1_p", "c_uimm8lo", "c_uimm8hi"],
    "c_fldsp": ["rd", "c_uimm9sphi", "c_uimm9splo"],
    "c_flw": ["rd_p", "rs1_p", "c_uimm7lo", "c_uimm7hi"],
    "c_flwsp": ["rd", "c_uimm8sphi", "c_uimm8splo"],
    "c_fsd": ["rs1_p", "rs2_p", "c_uimm8lo", "c_uimm8hi"],
    "c_fsdsp": ["c_rs2", "c_uimm9sp_s"],
    "c_fsw": ["rs1_p", "rs2_p", "c_uimm7lo", "c_uimm7hi"],
    "c_fswsp": ["c_rs2", "c_uimm8sp_s"],
    "c_j": ["c_imm12"],
    "c_jal": ["c_imm12"],
    "c_jr": ["rs1_n0"],
    "c_lbu": ["rd_p", "rs1_p", "c_uimm2"],
    "c_ld": ["rd_p", "rs1_p", "c_uimm8lo", "c_uimm8hi"],
    "c_ldsp": ["rd_n0", "c_uimm9sphi", "c_uimm9splo"],
    "c_lh": ["rd_p", "rs1_p", "c_uimm1"],
    "c_lhu": ["rd_p", "rs1_p", "c_uimm1"],
    "c_li": ["rd_n0", "c_imm6lo", "c_imm6hi"],
    "c_lui": ["rd_n2", "c_nzimm18hi", "c_nzimm18lo"],
    "c_lw": ["rd_p", "rs1_p", "c_uimm7lo", "c_uimm7hi"],
    "c_lwsp": ["rd_n0", "c_uimm8sphi", "c_uimm8splo"],
    "c_mv": ["rd_n0", "c_rs2_n0"],
    "c_nop": ["c_nzimm6hi", "c_nzimm6lo"],
    "c_sb": ["rs2_p", "rs1_p", "c_uimm2"],
    "c_sd": ["rs1_p", "rs2_p", "c_uimm8hi", "c_uimm8lo"],
    "c_sdsp": ["c_rs2", "c_uimm9sp_s"],
    "c_sh": ["rs2_p", "rs1_p", "c_uimm1"],
    "c_slli": ["rd_rs1_n0", "c_nzuimm6hi", "c_nzuimm6lo"],
    "c_srai": ["rd_rs1_p", "c_nzuimm6lo", "c_nzuimm6hi"],
    "c_srli": ["rd_rs1_p", "c_nzuimm6lo", "c_nzuimm6hi"],
    "c_sw": ["rs1_p", "rs2_p", "c_uimm7lo", "c_uimm7hi"],
    "c_swsp": ["c_rs2", "c_uimm8sp_s"],
    # CM instructions
    "cm_mva01s": ["c_sreg1", "c_sreg2"],
    "cm_mvsa01": ["c_sreg1", "c_sreg2"],
}


def load_fieldo() -> dict:
    """Load the fieldo.json file from the current directory."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(this_dir, "fieldo.json")
    try:
        with open(json_path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find fieldo.json in {this_dir}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in fieldo.json")


# Register names that need special handling
reg_names = {"qs1", "qs2", "qd", "fs1", "fs2", "fd", "hs1", "dd", "hd"}
fieldo = load_fieldo()


def range_size(range_str: str) -> int:
    """Calculate the width of a bit range like '31-20'. Returns 0 if invalid."""
    try:
        end, start = map(int, range_str.split("-"))
        return abs(end - start) + 1
    except Exception:
        return 0


def lookup_immediate_by_range(
    var_base: str,
    high: int,
    low: int,
    instr_name: str,
    left_shift: bool = False,
    hi: int = 0,
    lo: int = 0,
) -> Union[str, None]:
    """
    Find a canonical field name in fieldo that matches the bit range.

    Args:
        var_base: Base variable name (e.g., 'imm', 'bimm')
        high: Most significant bit position
        low: Least significant bit position
        instr_name: Name of the instruction for context
        left_shift: Flag for left-shift operations
        hi: Set to 1 when looking for high portion of a field
        lo: Set to 1 when looking for low portion of a field

    Returns:
        Canonical field name or None if not found
    """
    # Search for fields that match the bit range
    candidates = []
    for key, field in fieldo.items():
        if field.get("msb") == high and field.get("lsb") == low:
            # Handle standard immediates
            if var_base == "imm":
                if "imm" in key and not key.startswith("c_") and key != "csr":
                    candidates.append(key)
            # Handle compressed immediates
            elif var_base.startswith("c_") or var_base.startswith("c_imm"):
                if key.startswith("c_"):
                    candidates.append(key)
            # Handle other field types
            else:
                if key.startswith(var_base):
                    candidates.append(key)

    # Filter by hi/lo flags if requested
    if hi == 1:
        candidates = [c for c in candidates if "hi" in c.lower()]
    if lo == 1:
        candidates = [c for c in candidates if "lo" in c.lower()]

    print(
        f"DEBUG: lookup_immediate_by_range: var_base='{var_base}', high={high}, low={low}, hi_flag={hi}, lo_flag={lo}, candidates={candidates}"
    )

    # Pick the best candidate
    if candidates:
        if len(candidates) == 1:
            return candidates[0]
        else:
            # Apply heuristics for multiple candidates
            if left_shift:
                for cand in candidates:
                    if cand.startswith("bimm"):
                        return cand

            # Prefer "zimm" for imm fields
            if var_base == "imm" and "zimm" in candidates:
                return "zimm"

            # Instruction-specific preferences
            lower_instr = instr_name.lower()
            for cand in candidates:
                if lower_instr.startswith("j") and cand.startswith("jimm"):
                    return cand
                if lower_instr.startswith("b") and cand.startswith("bimm"):
                    return cand

            # Default to first candidate
            return candidates[0]

    return None


def canonical_immediate_names(
    var_name: str,
    location: str,
    instr_name: str,
    left_shift: bool = False,
    not_val: Union[str, None] = None,
) -> List[str]:
    """
    Map YAML immediate variables to canonical field names.

    This function handles various immediate encoding formats:
    - 4-part branch immediates
    - 4-part jump immediates
    - 3-part compressed store/load immediates
    - 2-part immediates
    - Standard composite formats
    - Single range immediates

    Returns list of canonical field names or empty list if not found.
    """
    print(
        f"DEBUG: canonical_immediate_names: var_name='{var_name}', location='{location}', instr_name='{instr_name}', not_val='{not_val}'"
    )
    parts = location.split("|")

    # Handle 4-part branch immediates (format: 31|7|30-25|11-8)
    if len(parts) == 4 and var_name == "imm" and instr_name.lower().startswith("b"):
        try:
            high_msb = int(parts[0])
            high_lsb = int(parts[2].split("-")[-1])
            low_msb = int(parts[3].split("-")[0])
            low_lsb = int(parts[1])
        except Exception as e:
            print(f"DEBUG: Error parsing 4-part branch composite immediate: {e}")
            return []

        hi_candidate = lookup_immediate_by_range(
            "bimm", high_msb, high_lsb, instr_name, left_shift=left_shift
        )
        lo_candidate = lookup_immediate_by_range(
            "bimm", low_msb, low_lsb, instr_name, left_shift=left_shift
        )

        print(
            f"DEBUG: 4-part branch composite: hi_candidate='{hi_candidate}', lo_candidate='{lo_candidate}'"
        )
        if hi_candidate is None or lo_candidate is None:
            print(
                f"DEBUG: 4-part branch composite immediate candidate not found for location '{location}'"
            )
            return []
        return [hi_candidate, lo_candidate]

    # Handle 4-part jump immediates (jal instruction)
    elif len(parts) == 4 and var_name == "imm" and instr_name.lower().startswith("j"):
        try:
            high = int(parts[0])
            low = int(parts[1].split("-")[1])
        except Exception as e:
            print(f"DEBUG: Error parsing 4-part jump composite immediate: {e}")
            return []

        candidate = lookup_immediate_by_range(
            "jimm", high, low, instr_name, left_shift=left_shift
        )
        print(f"DEBUG: 4-part jump composite: candidate='{candidate}'")
        if candidate is None:
            return []
        return [candidate]

    # Handle 3-part compressed store/load immediates (e.g., c.sw format: 5|12-10|6)
    elif "|" in location and len(parts) == 3:
        try:
            # The three parts need special adjustments based on encoding format
            low_msb = int(parts[0].strip()) - 1  # e.g., 5 becomes 4
            low_lsb = int(parts[2].strip()) - 4  # e.g., 6 becomes 2
            high_range = parts[1].strip()  # e.g., "12-10"
            high_msb, high_lsb = map(int, high_range.split("-"))
        except Exception as e:
            print(f"DEBUG: Error parsing 3-part composite immediate: {e}")
            return []

        print(
            f"DEBUG: 3-part composite immediate: computed high=({high_msb},{high_lsb}), computed low=({low_msb},{low_lsb})"
        )

        # Use c_uimm prefix for c_sw/c_sd/c_ld instructions
        if (
            instr_name.lower().startswith("c_sw")
            or instr_name.lower().startswith("c_sd")
            or instr_name.lower().startswith("c_ld")
        ):
            prefix = "c_uimm"
            print(
                "DEBUG: Instruction starts with 'c_sw/c_sd/c_ld', using prefix 'c_uimm'"
            )
        else:
            prefix = var_name
            print(
                f"DEBUG: Using default prefix '{prefix}' for 3-part composite immediate"
            )

        hi_candidate = lookup_immediate_by_range(
            prefix, high_msb, high_lsb, instr_name, left_shift=left_shift, hi=1
        )
        lo_candidate = lookup_immediate_by_range(
            prefix, low_msb, low_lsb, instr_name, left_shift=left_shift, lo=1
        )

        print(
            f"DEBUG: 3-part composite immediate: hi_candidate='{hi_candidate}', lo_candidate='{lo_candidate}'"
        )

        # Try to find matching high/low pairs
        if hi_candidate and hi_candidate.endswith("hi"):
            desired_lo = hi_candidate.replace("hi", "lo")
            print(f"DEBUG: Attempting to use paired lower candidate: '{desired_lo}'")
            try:
                if (
                    desired_lo in fieldo
                    and fieldo[desired_lo].get("msb") == low_msb
                    and fieldo[desired_lo].get("lsb") == low_lsb
                ):
                    lo_candidate = desired_lo
                    print(f"DEBUG: Paired lower candidate found: '{lo_candidate}'")
            except Exception:
                pass

        if hi_candidate is None or lo_candidate is None:
            print(
                f"DEBUG: 3-part composite immediate candidate not found for location '{location}'"
            )
            return []

        # Return low part first (important for store instructions)
        return [lo_candidate, hi_candidate]

    # Handle 2-part composite immediates (format: X|Y or X|Y-Z)
    elif "|" in location and len(parts) == 2:
        high_part = parts[0].strip()
        low_part = parts[1].strip()

        # Convert single-bit locations to range format
        if "-" not in high_part:
            high_range = f"{high_part}-{high_part}"
        else:
            high_range = high_part

        if "-" not in low_part:
            low_range = f"{low_part}-{low_part}"
        else:
            low_range = low_part

        try:
            high_msb, high_lsb = map(int, high_range.split("-"))
            low_msb, low_lsb = map(int, low_range.split("-"))
        except Exception as e:
            print(f"DEBUG: Error parsing 2-part composite immediate ranges: {e}")
            return []

        print(
            f"DEBUG: 2-part composite immediate parts: high=({high_msb},{high_lsb}), low=({low_msb},{low_lsb})"
        )

        # Use bimm prefix for branch instructions
        if var_name == "imm" and instr_name.lower().startswith("b"):
            prefix = "bimm"
            print("DEBUG: Branch immediate, using prefix 'bimm'")
        else:
            prefix = var_name
            print(f"DEBUG: Using default prefix '{prefix}'")

        hi_candidate = lookup_immediate_by_range(
            prefix, high_msb, high_lsb, instr_name, left_shift=left_shift
        )
        lo_candidate = lookup_immediate_by_range(
            prefix, low_msb, low_lsb, instr_name, left_shift=left_shift
        )

        print(
            f"DEBUG: 2-part composite immediate: hi_candidate='{hi_candidate}', lo_candidate='{lo_candidate}'"
        )

        # Look for paired hi/lo fields
        if hi_candidate and hi_candidate.endswith("hi"):
            desired_lo = hi_candidate.replace("hi", "lo")
            print(f"DEBUG: Attempting to use paired lower candidate: '{desired_lo}'")
            try:
                if (
                    desired_lo in fieldo
                    and fieldo[desired_lo].get("msb") == low_msb
                    and fieldo[desired_lo].get("lsb") == low_lsb
                ):
                    lo_candidate = desired_lo
                    print(f"DEBUG: Paired lower candidate found: '{lo_candidate}'")
            except Exception:
                pass

        if hi_candidate is None or lo_candidate is None:
            print(
                f"DEBUG: 2-part composite immediate candidate not found for location '{location}'"
            )
            return []

        return [hi_candidate, lo_candidate]

    # Handle standard format X-Y|Z-W with regex
    elif "|" in location:
        match = re.match(r"(\d+-\d+)\|(\d+-\d+)", location)
        if match:
            high_range = match.group(1)
            low_range = match.group(2)
            try:
                high_msb, high_lsb = map(int, high_range.split("-"))
                low_msb, low_lsb = map(int, low_range.split("-"))
            except Exception as e:
                print(f"DEBUG: Error parsing standard composite ranges: {e}")
                return []

            prefix = (
                "bimm"
                if var_name == "imm" and instr_name.lower().startswith("b")
                else var_name
            )
            hi_candidate = lookup_immediate_by_range(
                prefix, high_msb, high_lsb, instr_name, left_shift=left_shift
            )
            lo_candidate = lookup_immediate_by_range(
                prefix, low_msb, low_lsb, instr_name, left_shift=left_shift
            )

            print(
                f"DEBUG: standard composite: hi_candidate='{hi_candidate}', lo_candidate='{lo_candidate}'"
            )
            if hi_candidate is None or lo_candidate is None:
                return []
            return [hi_candidate, lo_candidate]

        else:
            # Fall back to number extraction
            nums = list(map(int, findall(r"\d+", location)))
            if len(nums) >= 2:
                high, low = nums[0], nums[1]
                candidate = lookup_immediate_by_range(
                    var_name, high, low, instr_name, left_shift=left_shift
                )
                print(f"DEBUG: fallback composite: candidate='{candidate}'")
                if candidate:
                    return [candidate]
            print(
                f"DEBUG: Fallback composite immediate candidate not found for location '{location}'"
            )
            return []

    # Handle simple range format X-Y or single bit X
    else:
        try:
            # Handle single bit cases (e.g., "26" instead of "26-26")
            if isinstance(location, int) or (
                isinstance(location, str) and location.isdigit()
            ):
                high = low = int(location)
            else:
                high, low = map(int, location.split("-"))
        except Exception:
            print(
                f"DEBUG: Invalid immediate location '{location}' for variable '{var_name}'"
            )
            return []

        candidate = lookup_immediate_by_range(
            var_name, high, low, instr_name, left_shift=left_shift
        )
        print(f"DEBUG: non-composite: candidate='{candidate}'")

        if candidate:
            # For "hi" fields, try to find the corresponding "lo" field
            if candidate.endswith("hi"):
                lo_candidate = lookup_immediate_by_range(
                    var_name, 11, 7, instr_name, left_shift=left_shift
                )
                if lo_candidate:
                    return [candidate, lo_candidate]
            return [candidate]
        else:
            print(
                f"DEBUG: No fieldo canonical name for {var_name} with range {location}"
            )
            return []


def GetVariables(vars: List[Dict[str, str]], instr_name: str = "") -> List[str]:
    """
    Extract field names from YAML variables.

    This processes variables from YAML and maps them to canonical field names
    using various heuristics for different field types.
    """
    # Use hardcoded fields for certain instructions
    if instr_name in HARDCODED_FIELDS:
        print(
            f"Using hardcoded fields for {instr_name}: {HARDCODED_FIELDS[instr_name]}"
        )
        return HARDCODED_FIELDS[instr_name]

    result = []
    for var in reversed(vars):
        var_name = str(var["name"]).lower().strip()

        # Get location and handle integer values
        location_val = var.get("location", "")
        if isinstance(location_val, int):
            # Convert single integer to range format
            location = f"{location_val}-{location_val}"
        else:
            location = str(location_val).strip()

        # SPECIAL CASE: Always preserve original "fm" field name
        # This prevents it from being replaced with "rm" due to bit position overlap
        if var_name == "fm":
            result.append("fm")
            continue

        # Handle register pair naming with slash
        if "/" in var_name:
            if var_name == "rd/rs1":
                not_val = var.get("not", None)
                if not_val is not None and str(not_val).strip() == "0":
                    result.append("rd_rs1_n0")
                else:
                    result.append("rd_rs1_p")
            else:
                result.append(var_name)
            continue

        # Handle shift amount fields
        if var_name == "shamt":
            size = range_size(location)
            if size == 5:
                result.append("shamtw")
            elif size == 6:
                result.append("shamtd")
            else:
                result.append("shamt")
            continue

        # Handle immediate fields
        if var_name in ("imm", "simm", "zimm", "jimm") or var_name.startswith("c_"):
            left_shift_flag = var.get("left_shift", 0) == 1
            not_val = var.get("not", None)
            canon_names = canonical_immediate_names(
                var_name,
                location,
                instr_name,
                left_shift=left_shift_flag,
                not_val=not_val,
            )
            if canon_names:
                result.extend(canon_names)
            else:
                print(
                    f"Warning: Skipping immediate field {var_name} with location {location} since no fieldo mapping was found."
                )
                result.append(var_name)  # Add the original name as fallback
            continue

        # Handle special register names
        if (
            var_name in reg_names
            or var_name.startswith("q")
            or var_name.startswith("f")
        ):
            result.append("r" + var_name[1:])
            continue

        # Handle general variables with bit positions
        if location:
            try:
                msb, lsb = map(int, location.split("-"))
                candidate = None

                # Try exact match first
                if var_name in fieldo:
                    field = fieldo[var_name]
                    if field.get("msb") == msb and field.get("lsb") == lsb:
                        candidate = var_name

                # Try compressed variants
                if candidate is None:
                    prefix = "c_" + var_name
                    comp_candidates = [
                        key
                        for key, field in fieldo.items()
                        if key.startswith(prefix)
                        and field.get("msb") == msb
                        and field.get("lsb") == lsb
                    ]
                    if comp_candidates:
                        candidate = comp_candidates[0]

                # Try name-based matches
                if candidate is None:
                    all_candidates = [
                        key
                        for key, field in fieldo.items()
                        if var_name in key
                        and field.get("msb") == msb
                        and field.get("lsb") == lsb
                    ]
                    if all_candidates:
                        # Prefer exact match, then _p variants, then first match
                        for cand in all_candidates:
                            if cand == var_name:
                                candidate = cand
                                break
                        if candidate is None:
                            for cand in all_candidates:
                                if "_p" in cand:
                                    candidate = cand
                                    break
                        if candidate is None:
                            candidate = all_candidates[0]

                if candidate:
                    result.append(candidate)
                elif var_name in fieldo:
                    result.append(var_name)
                else:
                    # Add original name as fallback
                    result.append(var_name)
                    print(
                        f"Warning: Variable field '{var_name}' not found in fieldo mapping with location {location}; using original name"
                    )
            except Exception as e:
                # Add original name when parsing fails
                result.append(var_name)
                print(
                    f"Warning: Could not parse location '{location}' for variable '{var_name}': {e}"
                )
        else:
            # Handle variables without location
            if var_name in fieldo:
                result.append(var_name)
            else:
                # Add original name as fallback
                result.append(var_name)
                print(
                    f"Warning: Variable field '{var_name}' not found in fieldo mapping; using original name"
                )

    return result


def GetMatchMask(bit_str: str) -> str:
    """Convert a bit string with dashes to hex, replacing dashes with zeros."""
    new_bit_str = ""
    for bit in bit_str:
        if bit == "-":
            new_bit_str += "0"
        else:
            new_bit_str += bit
    return hex(int(new_bit_str, 2))


def GetMask(bit_str: str) -> str:
    """Create a mask from a bit string, with 1's for bits and 0's for dashes."""
    mask_str = ""
    for bit in bit_str:
        if bit == "-":
            mask_str += "0"
        else:
            mask_str += "1"
    return hex(int(mask_str, 2))


def process_extension(ext: Union[str, dict]) -> List[str]:
    """Extract extension names from YAML definedBy field."""
    if isinstance(ext, str):
        return [ext.lower()]
    elif isinstance(ext, dict):
        result = []
        for item in ext.values():
            if isinstance(item, list):
                result.extend(
                    [
                        x.lower() if isinstance(x, str) else x["name"].lower()
                        for x in item
                    ]
                )
            elif isinstance(item, (str, dict)):
                if isinstance(item, str):
                    result.append(item.lower())
                else:
                    result.append(item["name"].lower())
        return result
    return []


def GetExtensions(ext: Union[str, dict, list], base: str) -> List[str]:
    """Get a list of extensions with RV prefix and remove duplicates."""
    prefix = f"rv{base}_"
    final_extensions = []

    if isinstance(ext, (str, dict)):
        extensions = process_extension(ext)
        final_extensions.extend(prefix + x for x in extensions)
    elif isinstance(ext, list):
        for item in ext:
            extensions = process_extension(item)
            final_extensions.extend(prefix + x for x in extensions)

    # Remove duplicates while preserving order
    seen = set()
    return [x for x in final_extensions if not (x in seen or seen.add(x))]


def GetEncodings(enc: str) -> str:
    """Pad encoding to 32 bits if needed."""
    n = len(enc)
    if n < 32:
        return "-" * (32 - n) + enc
    return enc


def convert(file_dir: str, json_out: Dict[str, Any]) -> None:
    """Process a single YAML file into JSON format."""
    try:
        with open(file_dir) as file:
            data = yaml.safe_load(file)

            # Skip non-instruction files
            if data["kind"] != "instruction":
                print(
                    f"Error: File {file_dir} has kind '{data['kind']}', expected 'instruction'. Skipping."
                )
                return

            instr_name = data["name"].replace(".", "_")
            print(instr_name)
            encodings = data["encoding"]

            # Handle RV64 variant if present
            rv64_flag = False
            if "RV64" in encodings:
                encodings = encodings["RV64"]
                rv64_flag = True
            enc_match = GetEncodings(encodings["match"])

            # Extract variable fields
            var_names = []
            if "variables" in encodings:
                var_names = GetVariables(encodings["variables"], instr_name)

            # Extract extension information
            extensions = []
            prefix = ""
            if rv64_flag:
                prefix = "64"
            try:
                if "base" in data:
                    extensions = GetExtensions(data["definedBy"], data["base"])
                else:
                    extensions = GetExtensions(data["definedBy"], prefix)
            except Exception as e:
                print(
                    f"Warning: Error processing extensions for {instr_name}: {str(e)}"
                )
                extensions = []

            # Calculate match and mask values
            match_hex = GetMatchMask(enc_match)
            match_mask = GetMask(enc_match)

            # Store instruction data
            json_out[instr_name] = {
                "encoding": enc_match,
                "variable_fields": var_names,
                "extension": extensions,
                "match": match_hex,
                "mask": match_mask,
            }
    except Exception as e:
        print(f"Error processing file {file_dir}: {str(e)}")
        raise


def find_yaml_files(path: str) -> List[str]:
    """Find all YAML files in a directory tree."""
    yaml_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                yaml_files.append(os.path.join(root, file))
    return yaml_files


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Convert YAML instruction files to JSON"
    )
    parser.add_argument("input_dir", help="Directory containing YAML instruction files")
    parser.add_argument("output_dir", help="Output directory for generated files")

    args = parser.parse_args()

    # Validate input directory
    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: {args.input_dir}")

    # Find YAML files
    yaml_files = find_yaml_files(args.input_dir)
    if not yaml_files:
        parser.error(f"No YAML files found in {args.input_dir}")

    # Process files
    inst_dict = {}
    output_file = os.path.join(args.output_dir, "instr_dict.json")

    try:
        for yaml_file in yaml_files:
            try:
                convert(yaml_file, inst_dict)
            except Exception as e:
                print(f"Warning: Failed to process {yaml_file}: {str(e)}")
                continue

        # Sort alphabetically
        insts_sorted = {inst: inst_dict[inst] for inst in sorted(inst_dict)}

        # Write output
        with open(output_file, "w") as outfile:
            json.dump(insts_sorted, outfile, indent=4)

        print(f"Successfully processed {len(yaml_files)} YAML files")
        print(f"Output written to: {output_file}")
    except Exception as e:
        print(f"Error: Failed to process YAML files: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
