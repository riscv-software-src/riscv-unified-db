import os
import json
import re
import sys
from collections import defaultdict
import yaml

REPO_INSTRUCTIONS = {}
REPO_DIRECTORY = None

def safe_get(data, key, default=""):
    """Safely get a value from a dictionary, return default if not found or error."""
    try:
        if isinstance(data, dict):
            return data.get(key, default)
        return default
    except:
        return default

def load_yaml_encoding(instr_name):
    """
    Given an instruction name (from JSON), find the corresponding YAML file and load its encoding data.
    We'll try to match the instr_name to a YAML file by using REPO_INSTRUCTIONS and transformations.
    """
    candidates = set()
    lower_name = instr_name.lower()
    candidates.add(lower_name)
    candidates.add(lower_name.replace('_', '.'))

    yaml_file_path = None
    yaml_category = None
    for cand in candidates:
        if cand in REPO_INSTRUCTIONS:
            yaml_category = REPO_INSTRUCTIONS[cand]
            yaml_file_path = os.path.join(REPO_DIRECTORY, yaml_category, cand + ".yaml")
            if os.path.isfile(yaml_file_path):
                break
            else:
                yaml_file_path = None

    if not yaml_file_path or not os.path.isfile(yaml_file_path):
        # YAML not found
        return None, None

    # Load the YAML file
    with open(yaml_file_path, 'r') as yf:
        ydata = yaml.safe_load(yf)

    encoding = safe_get(ydata, 'encoding', {})
    yaml_match = safe_get(encoding, 'match', None)
    yaml_vars = safe_get(encoding, 'variables', [])

    return yaml_match, yaml_vars

def compare_yaml_json_encoding(yaml_match, yaml_vars, json_encoding_str):
    """
    Compare the YAML encoding (match + vars) with the JSON encoding (binary format).
    If the JSON has a variable like vm[?], it should be treated as just vm.
    Return a list of differences.
    """
    if not yaml_match:
        return ["No YAML match field available for comparison."]
    if not json_encoding_str:
        return ["No JSON encoding available for comparison."]

    yaml_pattern_str = yaml_match.replace('-', '.')
    if len(yaml_pattern_str) != 32:
        return [f"YAML match pattern length is {len(yaml_pattern_str)}, expected 32. Cannot compare properly."]

    def parse_location(loc_str):
        high, low = loc_str.split('-')
        return int(high), int(low)

    yaml_var_positions = {}
    for var in yaml_vars:
        high, low = parse_location(var["location"])
        yaml_var_positions[var["name"]] = (high, low)

    tokens = re.findall(r'(?:[01]|[A-Za-z0-9]+(?:\[\d+\]|\[\?\])?)', json_encoding_str)
    json_bits = []
    bit_index = 31
    for t in tokens:
        json_bits.append((bit_index, t))
        bit_index -= 1

    if bit_index != -1:
        return [f"JSON encoding does not appear to be 32 bits. Ends at bit {bit_index+1}."]

    normalized_json_bits = []
    for pos, tt in json_bits:
        if re.match(r'vm\[[^\]]*\]', tt):
            tt = 'vm'
        normalized_json_bits.append((pos, tt))
    json_bits = normalized_json_bits

    differences = []

    # Check fixed bits
    for b in range(32):
        yaml_bit = yaml_pattern_str[31 - b]
        token = [tt for (pos, tt) in json_bits if pos == b]
        if not token:
            differences.append(f"Bit {b}: No corresponding JSON bit found.")
            continue
        json_bit_str = token[0]

        if yaml_bit in ['0', '1']:
            if json_bit_str not in ['0', '1']:
                differences.append(f"Bit {b}: YAML expects fixed bit '{yaml_bit}' but JSON has '{json_bit_str}'")
            elif json_bit_str != yaml_bit:
                differences.append(f"Bit {b}: YAML expects '{yaml_bit}' but JSON has '{json_bit_str}'")
        else:
            if json_bit_str in ['0', '1']:
                differences.append(f"Bit {b}: YAML variable bit but JSON is fixed '{json_bit_str}'")

    # Check variable fields
    for var_name, (high, low) in yaml_var_positions.items():
        json_var_fields = []
        for bb in range(low, high+1):
            token = [tt for (pos, tt) in json_bits if pos == bb]
            if token:
                json_var_fields.append(token[0])
            else:
                json_var_fields.append('?')

        # Extract field names
        field_names = set(re.findall(r'([A-Za-z0-9]+)(?:\[\d+\]|\[\?\])?', ' '.join(json_var_fields)))
        if len(field_names) == 0:
            differences.append(f"Variable {var_name}: No corresponding field found in JSON bits {high}-{low}")
        elif len(field_names) > 1:
            differences.append(f"Variable {var_name}: Multiple fields {field_names} found in JSON for bits {high}-{low}")

    return differences

def safe_print_instruction_details(name: str, data: dict, output_stream):
    """Print formatted instruction details and compare YAML/JSON encodings."""
    try:
        output_stream.write(f"\n{name} Instruction Details\n")
        output_stream.write("=" * 50 + "\n")

        output_stream.write("\nBasic Information:\n")
        output_stream.write("-" * 20 + "\n")
        output_stream.write(f"Name:              {name}\n")
        output_stream.write(f"Assembly Format:   {safe_get(data, 'AsmString', 'N/A')}\n")
        output_stream.write(f"Size:              {safe_get(data, 'Size', 'N/A')} bytes\n")

        locs = safe_get(data, '!locs', [])
        loc = locs[0] if isinstance(locs, list) and len(locs) > 0 else "N/A"
        output_stream.write(f"Location:          {loc}\n")

        output_stream.write("\nOperands:\n")
        output_stream.write("-" * 20 + "\n")
        try:
            in_ops = safe_get(data, 'InOperandList', {}).get('printable', 'N/A')
            output_stream.write(f"Inputs:            {in_ops}\n")
        except:
            output_stream.write("Inputs:            N/A\n")

        try:
            out_ops = safe_get(data, 'OutOperandList', {}).get('printable', 'N/A')
            output_stream.write(f"Outputs:           {out_ops}\n")
        except:
            output_stream.write("Outputs:           N/A\n")

        # Encoding
        output_stream.write("\nEncoding Pattern:\n")
        output_stream.write("-" * 20 + "\n")
        encoding_bits = []
        try:
            inst = safe_get(data, 'Inst', [])
            for bit in inst:
                if isinstance(bit, dict):
                    encoding_bits.append(f"{bit.get('var', '?')}[{bit.get('index', '?')}]")
                else:
                    encoding_bits.append(str(bit))
            # Reverse the bit order before joining
            encoding_bits.reverse()
            encoding = "".join(encoding_bits)
            output_stream.write(f"JSON Encoding:     {encoding}\n")
        except:
            output_stream.write("JSON Encoding:     Unable to parse encoding\n")
            encoding = ""

        # compare YAML vs JSON encodings
        yaml_match, yaml_vars = load_yaml_encoding(name)
        if yaml_match is not None:
            output_stream.write(f"YAML Encoding:     {yaml_match}\n")
        else:
            output_stream.write("YAML Encoding:     Not found\n")

        if yaml_match and encoding:
            # Perform comparison
            differences = compare_yaml_json_encoding(yaml_match, yaml_vars, encoding)
            if differences and len(differences) > 0:
                output_stream.write("\nEncodings do not match. Differences:\n")
                for d in differences:
                    output_stream.write(f"  - {d}\n")
                    print(f"Difference in {name}: {d}", file=sys.stdout)  # Print to console
            else:
                output_stream.write("\nEncodings Match: No differences found.\n")
        else:
            # If we have no YAML match or no JSON encoding, we note that we can't compare
            output_stream.write("\nComparison: Cannot compare encodings (missing YAML or JSON encoding).\n")

        output_stream.write("\n")
    except Exception as e:
        output_stream.write(f"Error processing instruction {name}: {str(e)}\n")
        output_stream.write("Continuing with next instruction...\n\n")

def get_repo_instructions(repo_directory):
    """
    Recursively find all YAML files in the repository and extract instruction names along with their category.
    """
    repo_instructions = {}
    for root, _, files in os.walk(repo_directory):
        for file in files:
            if file.endswith(".yaml"):
                instr_name = os.path.splitext(file)[0]
                relative_path = os.path.relpath(root, repo_directory)
                repo_instructions[instr_name.lower()] = relative_path
    return repo_instructions

def find_json_key(instr_name, json_data):
    """
    Attempt to find a matching key in json_data for instr_name, considering different
    naming conventions: replacing '.' with '_', and trying various case transformations.
    """
    lower_name = instr_name.lower()
    lower_name_underscore = lower_name.replace('.', '_')
    variants = {
        lower_name,
        lower_name_underscore,
        instr_name.upper(),
        instr_name.replace('.', '_').upper(),
        instr_name.capitalize(),
        instr_name.replace('.', '_').capitalize()
    }

    for v in variants:
        if v in json_data:
            return v
    return None

def run_parser(json_file, repo_directory, output_file="output.txt"):
    """
    Run the parser logic:
    1. Get instructions from the repo directory.
    2. Parse the JSON file and match instructions.
    3. Generate output.txt with instruction details.
    """
    global REPO_INSTRUCTIONS, REPO_DIRECTORY
    REPO_DIRECTORY = repo_directory

    # Get instructions and categories from the repository structure
    REPO_INSTRUCTIONS = get_repo_instructions(REPO_DIRECTORY)
    if not REPO_INSTRUCTIONS:
        print("No instructions found in the provided repository directory.")
        return None

    try:
        # Read and parse JSON
        with open(json_file, 'r') as f:
            data = json.loads(f.read())
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return None

    all_instructions = []

    # For each YAML instruction, try to find it in the JSON data
    for yaml_instr_name, category in REPO_INSTRUCTIONS.items():
        json_key = find_json_key(yaml_instr_name, data)
        if json_key is None:
            print(f"DEBUG: Instruction '{yaml_instr_name}' (from YAML) not found in JSON, skipping...", file=sys.stderr)
            continue

        instr_data = data.get(json_key)
        if not isinstance(instr_data, dict):
            print(f"DEBUG: Instruction '{yaml_instr_name}' is in JSON but not a valid dict, skipping...", file=sys.stderr)
            continue

        # Add this instruction to our list
        all_instructions.append((json_key, instr_data))

    # Sort all instructions by name
    all_instructions.sort(key=lambda x: x[0].lower())

    with open(output_file, "w") as outfile:
        outfile.write("RISC-V Instruction Summary\n")
        outfile.write("=" * 50 + "\n")
        total = len(all_instructions)
        outfile.write(f"\nTotal Instructions Found: {total}\n")
        for name, _ in all_instructions:
            outfile.write(f"  - {name}\n")

        outfile.write("\nDETAILED INSTRUCTION INFORMATION\n")
        outfile.write("=" * 80 + "\n")

        # Print details for each instruction directly
        for name, instr_data in all_instructions:
            safe_print_instruction_details(name, instr_data, outfile)

    print(f"Output has been written to {output_file}")
    return output_file

def main():
    if len(sys.argv) != 3:
        print("Usage: python riscv_parser.py <tablegen_json_file> <arch_inst_directory>")
        sys.exit(1)

    json_file = sys.argv[1]
    repo_directory = sys.argv[2]

    result = run_parser(json_file, repo_directory, output_file="output.txt")
    if result is None:
        sys.exit(1)

if __name__ == '__main__':
    main()
