import re
from typing import List, Dict, Union, Any
import argparse
import os
import sys
import yaml
import json


def load_fieldo() -> dict:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(this_dir, "fieldo.json")
    try:
        with open(json_path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find fieldo.json in {this_dir}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in fieldo.json")


# Set of register names that need transformation.
reg_names = {"qs1", "qs2", "qd", "fs1", "fs2", "fd", "hs1", "dd", "hd"}
fieldo = load_fieldo()


def range_size(range_str: str) -> int:
    """Compute the bit width from a range string like '31-20'."""
    try:
        end, start = map(int, range_str.split("-"))
        return abs(end - start) + 1
    except Exception:
        return 0


def lookup_immediate_by_range(
    var_base: str, high: int, low: int, instr_name: str, left_shift: bool = False
) -> Union[str, None]:
    """
    Look up a canonical field name from the fieldo mapping based on the bit range.

    When multiple candidates are found and left_shift is True, prefer the one that
    starts with 'bimm'.
    """
    candidates = []
    for key, field in fieldo.items():
        if field.get("msb") == high and field.get("lsb") == low:
            if var_base == "imm":
                if "imm" in key and not key.startswith("c_") and key != "csr":
                    candidates.append(key)
            elif var_base.startswith("c_"):
                if key.startswith("c_"):
                    candidates.append(key)
            else:
                if key.startswith(var_base):
                    candidates.append(key)
    if candidates:
        if len(candidates) == 1:
            return candidates[0]
        else:
            if left_shift:
                # If left_shift flag is set, check for a candidate starting with 'bimm'
                for cand in candidates:
                    if cand.startswith("bimm"):
                        return cand
            if var_base == "imm" and "zimm" in candidates:
                return "zimm"
            lower_instr = instr_name.lower()
            for cand in candidates:
                if lower_instr.startswith("j") and cand.startswith("jimm"):
                    return cand
                if lower_instr.startswith("b") and cand.startswith("bimm"):
                    return cand
            return candidates[0]
    return None


def canonical_immediate_names(
    var_name: str, location: str, instr_name: str, left_shift: bool = False
) -> List[str]:
    """
    Given a YAML immediate variable (its base name and location), return a list of canonical
    field names from fieldo.

    Supports several formats:

    1. For branch instructions (name starts with 'b') and a 4-part compound format,
       e.g. "31|7|30-25|11-8", it extracts the two parts using 'bimm' as the prefix.

    2. For jump instructions (name starts with 'j') with a 4-part compound format,
       e.g. "31|19-12|20|30-21", it extracts the overall high (from part 0) and low (from part 1)
       and uses the 'jimm' prefix.

    3. For a standard composite format "X-Y|Z-W", it compares the two ranges.
    4. For non-composite formats "X-Y", it does a simple lookup.
    """
    parts = location.split("|")
    if len(parts) == 4 and var_name == "imm" and instr_name.lower().startswith("b"):
        # Branch compound format, e.g.: "31|7|30-25|11-8"
        try:
            high_msb = int(parts[0])
            high_lsb = int(parts[2].split("-")[-1])
            low_msb = int(parts[3].split("-")[0])
            # parts[1] should be a simple number when converting for branch immediates.
            low_lsb = int(parts[1])
        except Exception as e:
            print(
                f"Warning: invalid branch compound immediate format in location '{location}': {e}"
            )
            return []
        hi_candidate = lookup_immediate_by_range(
            "bimm", high_msb, high_lsb, instr_name, left_shift=left_shift
        )
        lo_candidate = lookup_immediate_by_range(
            "bimm", low_msb, low_lsb, instr_name, left_shift=left_shift
        )
        if hi_candidate is None or lo_candidate is None:
            print(
                f"Warning: composite immediate candidate not found in fieldo for {var_name} with location {location}"
            )
            return []
        return [hi_candidate, lo_candidate]
    elif len(parts) == 4 and var_name == "imm" and instr_name.lower().startswith("j"):
        # Jump compound format, e.g.: "31|19-12|20|30-21"
        try:
            # For jump immediates, the canonical field typically covers the whole range.
            # We extract the overall high (first part) and the lower end of the second part.
            high = int(parts[0])
            low = int(parts[1].split("-")[1])
        except Exception as e:
            print(
                f"Warning: invalid jump compound immediate format in location '{location}': {e}"
            )
            return []
        candidate = lookup_immediate_by_range(
            "jimm", high, low, instr_name, left_shift=left_shift
        )
        if candidate is None:
            print(
                f"Warning: jump compound immediate candidate not found in fieldo for {var_name} with location {location}"
            )
            return []
        return [candidate]
    elif "|" in location:
        # Standard composite format, e.g.: "31-25|11-7"
        import re

        match = re.match(r"(\d+-\d+)\|(\d+-\d+)", location)
        if match:
            high_range = match.group(1)
            low_range = match.group(2)
            try:
                high_msb, high_lsb = map(int, high_range.split("-"))
                low_msb, low_lsb = map(int, low_range.split("-"))
            except Exception as e:
                print(
                    f"Warning: invalid composite immediate range in location '{location}': {e}"
                )
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
            if hi_candidate is None or lo_candidate is None:
                print(
                    f"Warning: composite immediate candidate not found in fieldo for {var_name} with location {location}"
                )
                return []
            return [hi_candidate, lo_candidate]
        else:
            # Fallback: try to extract numbers and use the first two.
            from re import findall

            nums = list(map(int, findall(r"\d+", location)))
            if len(nums) >= 2:
                high, low = nums[0], nums[1]
                candidate = lookup_immediate_by_range(
                    var_name, high, low, instr_name, left_shift=left_shift
                )
                if candidate:
                    return [candidate]
            print(
                f"Warning: composite immediate candidate not found in fieldo for {var_name} with location {location}"
            )
            return []
    else:
        # Non-composite format: "X-Y"
        try:
            high, low = map(int, location.split("-"))
        except Exception:
            print(f"Warning: invalid immediate location {location} for {var_name}")
            return []
        candidate = lookup_immediate_by_range(
            var_name, high, low, instr_name, left_shift=left_shift
        )
        if candidate:
            # If candidate ends with "hi", attempt to get its complementary lower-part.
            if candidate.endswith("hi"):
                lo_candidate = lookup_immediate_by_range(
                    var_name, 11, 7, instr_name, left_shift=left_shift
                )
                if lo_candidate:
                    return [candidate, lo_candidate]
            return [candidate]
        else:
            print(
                f"Warning: No fieldo canonical name for {var_name} with range {location}"
            )
            return []


def GetVariables(vars: List[Dict[str, str]], instr_name: str = "") -> List[str]:
    """
    Process the YAML variable definitions and return a list of variable names as expected by the generator.

    - For registers (names in reg_names), the first character is replaced with "r".
    - For "shamt", the field is renamed to "shamtw" if its width is 5 or "shamtd" if 6.
    - For immediates (variable names "imm", "simm", "zimm", "jimm", or those starting with "c_"),
      the canonical names are determined strictly via fieldo.
      Only names found in fieldo are used.
    - If an immediate has a 'left_shift' attribute equal to 1, that flag is passed on to influence candidate selection.
    - For any other variable field, it is added only if it exists in fieldo.
    - Special case: if the YAML variable is "hs1", it is renamed to "rs1".
    """
    result = []
    for var in reversed(vars):
        # Normalize variable name to lowercase
        var_name = var["name"].lower()

        location = var.get("location", "")
        if (
            var_name in reg_names
            or var_name.startswith("q")
            or var_name.startswith("f")
        ):
            result.append("r" + var_name[1:])
        elif var_name == "shamt":
            size = range_size(location)
            if size == 5:
                result.append("shamtw")
            elif size == 6:
                result.append("shamtd")
            else:
                result.append(var_name)
        elif var_name in ("imm", "simm", "zimm", "jimm") or var_name.startswith("c_"):
            left_shift_flag = var.get("left_shift", 0) == 1
            canon_names = canonical_immediate_names(
                var_name, location, instr_name, left_shift=left_shift_flag
            )
            if canon_names:
                result.extend(canon_names)
            else:
                print(
                    f"Warning: Skipping immediate field {var_name} with location {location} since no fieldo mapping was found."
                )
        else:
            # Only add the variable if it exists in fieldo.
            if var_name in fieldo:
                result.append(var_name)
            else:
                print(
                    f"Warning: Variable field '{var_name}' not found in fieldo mapping; skipping."
                )
    return result


def GetMatchMask(bit_str: str) -> str:
    new_bit_str = ""
    for bit in bit_str:
        if bit == "-":
            new_bit_str += "0"
        else:
            new_bit_str += bit
    return hex(int(new_bit_str, 2))


def GetMask(bit_str: str) -> str:
    mask_str = ""
    for bit in bit_str:
        if bit == "-":
            mask_str += "0"
        else:
            mask_str += "1"
    return hex(int(mask_str, 2))


def process_extension(ext: Union[str, dict]) -> List[str]:
    """Process an extension definition into a list of strings."""
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
    """Get a list of extensions with proper prefix."""
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
    n = len(enc)
    if n < 32:
        return "-" * (32 - n) + enc
    return enc


def convert(file_dir: str, json_out: Dict[str, Any]) -> None:
    try:
        with open(file_dir) as file:
            data = yaml.safe_load(file)

            if data["kind"] != "instruction":
                print(
                    f"Error: File {file_dir} has kind '{data['kind']}', expected 'instruction'. Skipping."
                )
                return

            instr_name = data["name"].replace(".", "_")
            print(instr_name)
            encodings = data["encoding"]

            # USE RV_64
            rv64_flag = False
            if "RV64" in encodings:
                encodings = encodings["RV64"]
                rv64_flag = True
            enc_match = GetEncodings(encodings["match"])

            var_names = []
            if "variables" in encodings:
                var_names = GetVariables(encodings["variables"], instr_name)

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

            match_hex = GetMatchMask(enc_match)
            match_mask = GetMask(enc_match)

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
    yaml_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                yaml_files.append(os.path.join(root, file))
    return yaml_files


def main():
    parser = argparse.ArgumentParser(
        description="Convert YAML instruction files to JSON"
    )
    parser.add_argument("input_dir", help="Directory containing YAML instruction files")
    parser.add_argument("output_dir", help="Output directory for generated files")

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: {args.input_dir}")

    yaml_files = find_yaml_files(args.input_dir)
    if not yaml_files:
        parser.error(f"No YAML files found in {args.input_dir}")

    inst_dict = {}
    output_file = os.path.join(args.output_dir, "instr_dict.json")

    try:
        for yaml_file in yaml_files:
            try:
                convert(yaml_file, inst_dict)
            except Exception as e:
                print(f"Warning: Failed to process {yaml_file}: {str(e)}")
                continue

        insts_sorted = {inst: inst_dict[inst] for inst in sorted(inst_dict)}
        with open(output_file, "w") as outfile:
            json.dump(insts_sorted, outfile, indent=4)

        print(f"Successfully processed {len(yaml_files)} YAML files")
        print(f"Output written to: {output_file}")
    except Exception as e:
        print(f"Error: Failed to process YAML files: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
