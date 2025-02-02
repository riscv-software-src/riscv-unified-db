#!/usr/bin/env python3

from typing import List, Dict, Union, Any
import os
import yaml
import json
import argparse
import sys


def range_size(range_str: str) -> int:
    try:
        end, start = map(int, range_str.split("-"))
        return abs(end - start) + 1
    except ValueError:
        return 0


reg_names = {"qs1", "qs2", "qd", "fs1", "fs2", "fd"}


def GetVariables(vars: List[Dict[str, str]]) -> List[str]:
    var_names = []
    for var in vars:
        var_name = var["name"]
        if var_name in reg_names:
            # Since strings are immutable.
            lst_var_name = list(var_name)
            lst_var_name[0] = "r"
            var_name = "".join(lst_var_name)
        elif var_name == "shamt":
            size = range_size(var["location"])
            if size == 5:
                var_name = "shamtw"
            elif size == 6:
                var_name = "shamtd"
        var_names.append(var_name)
    var_names.reverse()
    return var_names


def BitStringToHex(bit_str: str) -> str:
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


def GetExtension(ext: Union[str, dict, list], base: str) -> List[str]:
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

            extension = []
            prefix = ""
            if rv64_flag:
                prefix = "64"
            try:
                if "base" in data:
                    extension = GetExtension(data["definedBy"], data["base"])
                else:
                    extension = GetExtension(data["definedBy"], prefix)
            except Exception as e:
                print(
                    f"Warning: Error processing extensions for {instr_name}: {str(e)}"
                )
                extension = []

            match_hex = BitStringToHex(enc_match)
            match_mask = GetMask(enc_match)

            json_out[instr_name] = {
                "encoding": enc_match,
                "variable_fields": var_names,
                "extension": extension,
                "match": match_hex,
                "mask": match_mask,
            }
    except Exception as e:
        print(f"Error processing file {file_dir}: {str(e)}")
        raise


def read_yaml_insts(path: str) -> List[str]:
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

    insts = read_yaml_insts(args.input_dir)
    if not insts:
        parser.error(f"No YAML files found in {args.input_dir}")

    inst_dict = {}
    output_file = os.path.join(args.output_dir, "instr_dict.json")

    try:
        for inst_dir in insts:
            try:
                convert(inst_dir, inst_dict)
            except Exception as e:
                print(f"Warning: Failed to process {inst_dir}: {str(e)}")
                continue

        with open(output_file, "w") as outfile:
            json.dump(inst_dict, outfile, indent=4)

        print(f"Successfully processed {len(insts)} YAML files")
        print(f"Output written to: {output_file}")
    except Exception as e:
        print(f"Error: Failed to process YAML files: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
