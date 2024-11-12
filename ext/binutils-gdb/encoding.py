import os
import re
import sys
from collections import defaultdict

def parse_header_files(header_files):
    """
    Parses header files to extract all #define constants.

    Args:
        header_files (list of str): Paths to header files.

    Returns:
        defines (dict): Mapping from define name to its integer value.
    """
    define_pattern = re.compile(r'#define\s+(\w+)\s+(.+)')

    defines = {}

    for header_file in header_files:
        try:
            with open(header_file, 'r') as file:
                for line_num, line in enumerate(file, 1):
                    # Remove inline comments
                    line = line.split('//')[0]
                    line = line.split('/*')[0]
                    match = define_pattern.match(line)
                    if match:
                        name = match.group(1)
                        value_expr = match.group(2).strip()
                        try:
                            # Replace defined constants in the expression with their values
                            value = evaluate_expression(value_expr, defines)
                            defines[name] = value
                            # Debug: Uncomment the following line to see parsed defines
                            # print(f"Parsed Define: {name} = {hex(value)}")
                        except Exception:
                            # Skip defines that cannot be evaluated
                            continue
        except FileNotFoundError:
            print(f"Error: Header file '{header_file}' not found.")
            sys.exit(1)  # Exit if a header file is missing

    return defines

def evaluate_expression(expr, defines):
    """
    Evaluates a C-style expression using the defines provided.

    Args:
        expr (str): The expression to evaluate.
        defines (dict): Mapping from define names to integer values.

    Returns:
        int: The evaluated integer value of the expression.
    """
    # Replace C-style bitwise operators with Python equivalents if needed
    expr = expr.replace('<<', '<<').replace('>>', '>>').replace('|', '|').replace('&', '&').replace('~', '~')

    if '|' in expr:
        # Assign only the part before the first '|'
        expr = expr.split('|')[0]

    # Replace define names with their integer values
    tokens = re.findall(r'\w+|\S', expr)
    expr_converted = ''
    for token in tokens:
        if token in defines:
            expr_converted += str(defines[token])
        elif re.match(r'0x[0-9a-fA-F]+', token):  # Hexadecimal literals
            expr_converted += str(int(token, 16))
        elif re.match(r'\d+', token):  # Decimal literals
            expr_converted += token
        elif token in ('|', '&', '~', '<<', '>>', '(', ')'):
            expr_converted += f' {token} '
        else:
            raise ValueError(f"Undefined constant or invalid token: {token}")

    try:
        # Safely evaluate the expression
        value = eval(expr_converted, {"__builtins__": None}, {})
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression '{expr}': {e}")

    return value

def parse_instruction_files(instruction_files):
    """
    Parses instruction definition files to extract instruction names, their MATCH_* and MASK_* expressions, class, and flags.

    Args:
        instruction_files (list of str): Paths to instruction definition files.

    Returns:
        instructions (list of dict): Each dict contains 'name', 'match_expr', 'mask_expr', 'class', 'flags', 'line_num', 'file'.
    """
    # Updated pattern to capture the entire match and mask expressions and the flags
    # Example line:
    # {"fence",       0, INSN_CLASS_I, "P,Q",       MATCH_FENCE, MASK_FENCE|MASK_RD|MASK_RS1|(MASK_IMM & ~MASK_PRED & ~MASK_SUCC), match_opcode, 0 },
    instr_pattern = re.compile(
        r'\{\s*"([\w\.]+)",\s*\d+,\s*(INSN_CLASS_\w+),\s*"[^"]*",\s*(MATCH_[^,]+),\s*(MASK_[^,]+),[^,]+,\s*([^}]+)\s*\},'
    )

    instructions = []

    for instr_file in instruction_files:
        try:
            with open(instr_file, 'r') as file:
                for line_num, line in enumerate(file, 1):
                    instr_match = instr_pattern.match(line)
                    if instr_match:
                        instr_name = instr_match.group(1)
                        instr_class = instr_match.group(2)
                        match_expr = instr_match.group(3).strip()
                        mask_expr = instr_match.group(4).strip()
                        flags = instr_match.group(5).strip()
                        instructions.append({
                            'name': instr_name,
                            'class': instr_class,
                            'match_expr': match_expr,
                            'mask_expr': mask_expr,
                            'flags': flags,
                            'line_num': line_num,
                            'file': instr_file
                        })
                        # Debug: Uncomment the following line to see parsed instructions
                        # print(f"Parsed Instruction: {instr_name} at {instr_file}:{line_num}")
        except FileNotFoundError:
            print(f"Error: Instruction file '{instr_file}' not found.")
            sys.exit(1)  # Exit if an instruction file is missing

    return instructions

def match_mask_to_encoding(match, mask):
    """
    Converts MATCH and MASK values into a binary encoding string with '0', '1', and '-'.

    Args:
        match (int): The MATCH_* integer value.
        mask (int): The MASK_* integer value.

    Returns:
        encoding_str (str): A 32-character string representing the encoding.
    """
    encoding = []
    for bit in range(31, -1, -1):  # From bit 31 to bit 0
        mask_bit = (mask >> bit) & 1
        if mask_bit:
            match_bit = (match >> bit) & 1
            encoding.append(str(match_bit))
        else:
            encoding.append('-')
    encoding_str = ''.join(encoding)
    return encoding_str

def format_encoding(encoding_str):
    """
    Formats the encoding string by grouping bits for readability.

    Desired format:
    match: 0000000----------000-----0110011

    Which corresponds to:
    - bits 31-25: 7 bits
    - bits 24-15: 10 bits
    - bits 14-12: 3 bits
    - bits 11-7: 5 bits
    - bits 6-0: 7 bits

    Args:
        encoding_str (str): The 32-character encoding string.

    Returns:
        formatted_str (str): The formatted encoding string with separators.
    """
    if len(encoding_str) != 32:
        print("Error: Encoding string is not 32 bits long.")
        return encoding_str  # Return as is

    group1 = encoding_str[0:7]    # bits 31-25
    group2 = encoding_str[7:17]   # bits 24-15
    group3 = encoding_str[17:20]  # bits 14-12
    group4 = encoding_str[20:25]  # bits 11-7
    group5 = encoding_str[25:32]  # bits 6-0

    # Combine groups with no separators as per desired format
    # Example: 0000000----------000-----0110011
    formatted_str = f"{group1}{group2}{group3}{group4}{group5}"
    return formatted_str

def get_instruction_names_from_directory(directory_path):
    """
    Lists all .yaml files in the specified directory and extracts instruction names.

    Args:
        directory_path (str): Path to the directory containing YAML files.

    Returns:
        instr_names (set): A set of instruction names without the .yaml extension.
    """
    try:
        files = os.listdir(directory_path)
    except FileNotFoundError:
        print(f"Error: Directory '{directory_path}' not found.")
        return set()

    instr_names = set()
    for file in files:
        if file.endswith('.yaml'):
            instr_name = os.path.splitext(file)[0]
            instr_names.add(instr_name)

    return instr_names

def main():
    """
    Main function to parse files and generate instruction encodings based on YAML directory.
    """
    # Define file paths here
    # Update these paths based on your actual file locations
    header_files = [
        'include/opcode/riscv-opc.h',
        'include/opcode/riscv.h'  # Replace with your actual additional header file names
    ]

    instruction_files = [
        'opcodes/riscv-opc.c'
        # Add more instruction definition files if necessary
    ]

    # Define the path to the directory containing YAML files
    yaml_directory = '../../arch/inst/V'  # Replace with your actual directory path

    # Get instruction names from the YAML directory
    yaml_instr_names = get_instruction_names_from_directory(yaml_directory)
    if not yaml_instr_names:
        print("No instruction names found. Exiting.")
        sys.exit(1)  # Exit if no instruction names are found

    # Parse header files to get all #define constants
    defines = parse_header_files(header_files)
    if not defines:
        print("No #define constants parsed. Exiting.")
        sys.exit(1)  # Exit if no defines are parsed

    # Parse instruction definition files to get all instructions
    instructions = parse_instruction_files(instruction_files)
    if not instructions:
        print("No instructions parsed from instruction definition files. Exiting.")
        sys.exit(1)  # Exit if no instructions are parsed

    # Group instructions by name
    instr_group = defaultdict(list)
    for instr in instructions:
        if instr['name'] in yaml_instr_names and 'INSN_ALIAS' not in instr['flags']:
            instr_group[instr['name']].append(instr)

    if not instr_group:
        print("No matching non-alias instructions found between YAML files and instruction definitions.")
        sys.exit(1)  # Exit if no matching instructions are found

    # Process each instruction group
    for name, defs in instr_group.items():
        success_encodings = []
        for d in defs:
            try:
                # Evaluate MATCH expression
                match_val = evaluate_expression(d['match_expr'], defines)
                # Evaluate MASK expression
                mask_val = evaluate_expression(d['mask_expr'], defines)
                # Generate the encoding string
                encoding_str = match_mask_to_encoding(match_val, mask_val)
                # Format the encoding string
                formatted_encoding = format_encoding(encoding_str)
                # Collect successful encodings
                success_encodings.append((d['class'], formatted_encoding))
            except Exception:
                # Skip this definition if evaluation fails
                continue

        if success_encodings:
            # Print all successful encodings for this instruction
            for class_, encoding in success_encodings:
                print(f'Instruction: {name}')
                print(f'  Class: {class_}')
                print(f'  match: {encoding}\n')
        else:
            # No valid definitions could be processed for this instruction
            print(f"Error: Could not evaluate any MATCH/MASK expressions for instruction '{name}'. Exiting.")
            sys.exit(1)  # Terminate the script

    # Optionally, notify about YAML files without corresponding instruction definitions
    defined_instr_names = set(instr['name'] for instr in instructions)
    undefined_yaml_instr = yaml_instr_names - defined_instr_names
    if undefined_yaml_instr:
        print("Warning: The following instructions from YAML directory do not have definitions:")
        for instr in undefined_yaml_instr:
            print(f"  - {instr}")

if __name__ == "__main__":
    main()
