import re
from typing import List, Dict, Union, Any
import argparse
import os
import sys
import yaml
import json
from typing import List, Dict, Union
import subprocess


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
reg_names = {"qs1", "qs2", "qd", "fs1", "fs2", "fd"}
fieldo = load_fieldo()


def range_size(range_str: str) -> int:
    """Compute the bit width from a range string like '31-20'."""
    try:
        end, start = map(int, range_str.split("-"))
        return abs(end - start) + 1
    except Exception:
        return 0


def lookup_immediate_by_range(
    var_base: str, high: int, low: int, instr_name: str
) -> Union[str, None]:
    """
    Look up a canonical field name from the fieldo mapping based on the bit range.

    - If var_base is "imm", then we consider any field whose name contains "imm"
      (but not starting with "c_" and not "csr").
    - If var_base starts with "c_", then only keys starting with "c_" are considered.
    - Otherwise, we require that the key starts with var_base (for "simm", "jimm", etc.).

    If multiple candidates are found and var_base is "imm", we prefer "zimm" if present.
    Otherwise, instr_name is used as a hint.
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
    var_name: str, location: str, instr_name: str
) -> List[str]:
    """
    Given a YAML immediate variable (its base name and location), return a list of canonical
    field names strictly from the fieldo mapping.

    - For non-composite locations (e.g. "31-20"), the range is parsed and a lookup is performed.
    - For composite locations (detected by "|" in the location), we assume a branch-immediate split:
      the high part uses the range (31, 25) and the low part (11, 7), with an appropriate prefix.
    - If no candidate is found in fieldo, an empty list is returned.
    """
    if "|" in location:
        parts = location.split("|")
        if len(parts) == 4:
            prefix = "bimm" if instr_name.lower().startswith("b") else "imm"
            hi_candidate = lookup_immediate_by_range(prefix, 31, 25, instr_name)
            lo_candidate = lookup_immediate_by_range(prefix, 11, 7, instr_name)
            if hi_candidate is None or lo_candidate is None:
                print(
                    f"Warning: composite immediate candidate not found in fieldo for {var_name} with location {location}"
                )
                return []
            return [hi_candidate, lo_candidate]
        else:
            # For other composite formats, attempt a basic lookup using the first two numbers.
            nums = list(map(int, re.findall(r"\d+", location)))
            if len(nums) >= 2:
                high, low = nums[0], nums[1]
                candidate = lookup_immediate_by_range(var_name, high, low, instr_name)
                if candidate:
                    return [candidate]
            print(
                f"Warning: composite immediate candidate not found in fieldo for {var_name} with location {location}"
            )
            return []
    else:
        try:
            high, low = map(int, location.split("-"))
        except Exception:
            print(f"Warning: invalid immediate location {location} for {var_name}")
            return []
        candidate = lookup_immediate_by_range(var_name, high, low, instr_name)
        if candidate:
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
    - For immediates (base names "imm", "simm", "zimm", "jimm", or those starting with "c_"),
      the canonical names are determined strictly by looking them up in fieldo.
      Only names found in fieldo are used.

    The variables are processed in reverse order.
    """
    result = []
    for var in reversed(vars):
        var_name = var["name"]
        location = var.get("location", "")
        if var_name in reg_names:
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
            canon_names = canonical_immediate_names(var_name, location, instr_name)
            if canon_names:
                result.extend(canon_names)
            else:
                print(
                    f"Warning: Skipping immediate field {var_name} with location {location} since no fieldo mapping was found."
                )
        else:
            result.append(var_name)
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
                var_names = GetVariables(encodings["variables"])

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

    # Ensure input directory exists
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

            insts_sorted = {}
            for inst in sorted(inst_dict):
                insts_sorted[inst] = inst_dict[inst]

            with open(output_file, "w") as outfile:
                json.dump(insts_sorted, outfile, indent=4)

        print(f"Successfully processed {len(insts)} YAML files")
        print(f"Output written to: {output_file}")
    except Exception as e:
        print(f"Error: Failed to process YAML files: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
