import os
import re
import sys
import yaml
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
                        
                        # Skip alias entries
                        if 'INSN_ALIAS' in flags:
                            continue
                            
                        # Check if the instruction follows the naming pattern
                        if not check_match_mask_pattern(instr_name, match_expr, mask_expr):
                            continue  # Skip instructions that don't follow the pattern
                            
                        instructions.append({
                            'name': instr_name,
                            'class': instr_class,
                            'match_expr': match_expr,
                            'mask_expr': mask_expr,
                            'flags': flags,
                            'line_num': line_num,
                            'file': instr_file
                        })
        except FileNotFoundError:
            print(f"Error: Instruction file '{instr_file}' not found.")
            sys.exit(1)  # Exit if an instruction file is missing

    return instructions

def match_mask_to_encoding(match, mask, is_compressed=False):
    """
    Converts MATCH and MASK values into a binary encoding string with '0', '1', and '-'.

    Args:
        match (int): The MATCH_* integer value.
        mask (int): The MASK_* integer value.
        is_compressed (bool): Whether this is a compressed (16-bit) instruction

    Returns:
        encoding_str (str): A 16 or 32-character string representing the encoding.
    """
    encoding = []
    # Use 15 for 16-bit instructions, 31 for 32-bit instructions
    max_bit = 15 if is_compressed else 31
    
    for bit in range(max_bit, -1, -1):  # From max_bit to bit 0
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
    Handles both 32-bit and 16-bit instructions.

    Args:
        encoding_str (str): The encoding string.

    Returns:
        formatted_str (str): The formatted encoding string with separators.
    """
    if len(encoding_str) == 16:  # Compressed instruction
        # Compressed instruction format (16 bits)
        # Typical format is: func3(3) | imm/register fields | op(2)
        return encoding_str  # Return as-is for compressed instructions
    elif len(encoding_str) == 32:  # Standard instruction
        group1 = encoding_str[0:7]    # bits 31-25
        group2 = encoding_str[7:17]   # bits 24-15
        group3 = encoding_str[17:20]  # bits 14-12
        group4 = encoding_str[20:25]  # bits 11-7
        group5 = encoding_str[25:32]  # bits 6-0
        return f"{group1}{group2}{group3}{group4}{group5}"
    else:
        print(f"Error: Unexpected encoding string length: {len(encoding_str)}")
        return encoding_str 

def get_instruction_yaml_files(directory_path):
    """
    Recursively finds all .yaml files in the specified directory and its subdirectories,
    and maps instruction names to their YAML file paths.

    Args:
        directory_path (str): Path to the directory containing YAML files.

    Returns:
        instr_yaml_map (dict): Mapping from instruction name to YAML file path.
    """
    instr_yaml_map = {}
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.yaml'):
                instr_name = os.path.splitext(file)[0]
                yaml_path = os.path.join(root, file)
                if instr_name in instr_yaml_map:
                    print(f"Warning: Multiple YAML files found for instruction '{instr_name}'. "
                          f"Using '{instr_yaml_map[instr_name]}' and ignoring '{yaml_path}'.")
                else:
                    instr_yaml_map[instr_name] = yaml_path
    return instr_yaml_map

def parse_yaml_encoding(yaml_file_path):
    """
    Parses the YAML file to extract the encoding match string.
    Handles the new YAML format with top-level encoding field.

    Args:
        yaml_file_path (str): Path to the YAML file.

    Returns:
        match_encoding (str): The match encoding string.
    """
    try:
        with open(yaml_file_path, 'r') as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
            
            # Handle case where yaml_content is None
            if yaml_content is None:
                print(f"Warning: Empty YAML file '{yaml_file_path}'.")
                return ''
                
            if not isinstance(yaml_content, dict):
                print(f"Warning: Unexpected YAML format in '{yaml_file_path}'. Content type: {type(yaml_content)}")
                return ''
            
            # Get encoding section directly from top level
            encoding = yaml_content.get('encoding', {})
            
            if not isinstance(encoding, dict):
                print(f"Warning: Encoding is not a dictionary in '{yaml_file_path}'")
                return ''
            
            # Get match value directly from encoding section
            match_encoding = encoding.get('match', '')
            
            if not match_encoding:
                print(f"Warning: No 'encoding.match' found in YAML file '{yaml_file_path}'.")
            
            # Remove any whitespace in the match encoding
            match_encoding = match_encoding.replace(' ', '')
            
            return match_encoding
            
    except FileNotFoundError:
        print(f"Error: YAML file '{yaml_file_path}' not found.")
        return ''
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse YAML file '{yaml_file_path}': {e}")
        return ''
    except Exception as e:
        print(f"Error: Unexpected error processing '{yaml_file_path}': {e}")
        return ''

    
def check_match_mask_pattern(instr_name, match_expr, mask_expr):
    """
    Checks if the MATCH and MASK names follow the expected pattern based on instruction name.
    Allows both MATCH_NAME and MATCH_NAME_SUFFIX patterns.
    
    Args:
        instr_name (str): The instruction name (e.g., "add" or "vfmin.vv")
        match_expr (str): The MATCH expression (e.g., "MATCH_ADD" or "MATCH_VFMINVV")
        mask_expr (str): The MASK expression (e.g., "MASK_ADD" or "MASK_VFMINVV")
        
    Returns:
        bool: True if the pattern matches, False otherwise
    """
    # Convert instruction name to uppercase and handle special characters
    normalized_name = instr_name.replace('.', '')
    normalized_name = normalized_name.replace('_', '')
    normalized_name = normalized_name.upper()
    
    # Extract the base MATCH and MASK names (before any '|' operations)
    base_match = match_expr.split('|')[0].strip()
    base_mask = mask_expr.split('|')[0].strip()
    
    # Remove MATCH_ and MASK_ prefixes
    if base_match.startswith('MATCH_'):
        base_match = base_match[6:]  # Remove 'MATCH_'
    if base_mask.startswith('MASK_'):
        base_mask = base_mask[5:]    # Remove 'MASK_'
        
    # Remove any remaining underscores for comparison
    base_match = base_match.replace('_', '')
    base_mask = base_mask.replace('_', '')
    
    # Now compare the normalized strings
    return base_match == normalized_name and base_mask == normalized_name

def main():
    """
    Main function to parse files and generate instruction encodings based on YAML directory.
    """
    # Define file paths here
    # Update these paths based on your actual file locations
    header_files = [
        'ext/binutils-gdb/binutils/include/opcode/riscv-opc.h',
        'ext/binutils-gdb/binutils/include/opcode/riscv.h' 
    ]

    instruction_files = [
        'ext/binutils-gdb/binutils/opcodes/riscv-opc.c'
    ]

    # Define the path to the directory containing YAML files
    yaml_directory = 'arch/inst/' 

    # Get instruction YAML mappings from the YAML directory recursively
    instr_yaml_map = get_instruction_yaml_files(yaml_directory)
    if not instr_yaml_map:
        print("No YAML files found. Exiting.")
        sys.exit(1)  # Exit if no YAML files are found

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
        if instr['name'] in instr_yaml_map and 'INSN_ALIAS' not in instr['flags']:
            instr_group[instr['name']].append(instr)

    if not instr_group:
        print("No matching non-alias instructions found between YAML files and instruction definitions.")
        sys.exit(1)  # Exit if no matching instructions are found

    # Initialize a flag to track mismatches
    mismatches_found = False

    # Process each instruction group
    for name, defs in instr_group.items():
        success_encodings = []
        yaml_encoding = ''
        yaml_file_path = instr_yaml_map.get(name, '')
        
        if not yaml_file_path:
            # No YAML file found for this instruction
            print(f"Warning: No YAML file found for instruction '{name}'. Skipping comparison.")
            continue

        yaml_encoding = parse_yaml_encoding(yaml_file_path)

        if not yaml_encoding:
            # Skip comparison if YAML encoding is missing
            continue

        for d in defs:
            try:
                # Check if it's a compressed instruction
                is_compressed = name.startswith('c.') or 'CLASS_C' in d['class']
                
                # Evaluate MATCH expression
                match_val = evaluate_expression(d['match_expr'], defines)
                # Evaluate MASK expression
                mask_val = evaluate_expression(d['mask_expr'], defines)
                # Generate the encoding string with compression flag
                encoding_str = match_mask_to_encoding(match_val, mask_val, is_compressed)
                # Format the encoding string
                formatted_encoding = format_encoding(encoding_str)
                # Collect successful encodings
                success_encodings.append((d['class'], formatted_encoding))
            except Exception:
                # Skip this definition if evaluation fails
                continue


        if success_encodings:
            for class_, encoding in success_encodings:
                # Actually compare the encodings
                if yaml_encoding.replace(" ", "") != encoding.replace(" ", ""):
                    mismatches_found = True
                    print(f"Error: Encoding mismatch for instruction '{name}' in YAML file '{yaml_file_path}'.")
                    print(f"  YAML match     : {yaml_encoding}")
                    print(f"  Generated match: {encoding}\n")
                    sys.exit(1)  # Exit immediately on first mismatch
        else:
            # No valid definitions could be processed for this instruction
            print(f"Error: Could not evaluate any MATCH/MASK expressions for instruction '{name}' in YAML file '{yaml_file_path}'.\n")
            mismatches_found = True

    # Optionally, notify about YAML files without corresponding instruction definitions
    defined_instr_names = set(instr['name'] for instr in instructions)
    yaml_instr_names = set(instr_yaml_map.keys())
    undefined_yaml_instr = yaml_instr_names - defined_instr_names
    if undefined_yaml_instr:
        print("Warning: The following instructions from YAML directory do not have definitions:")
        for instr in sorted(undefined_yaml_instr):
            print(f"  - {instr}")

    # Exit with appropriate status code
    if mismatches_found:
        sys.exit(1)  # Exit with error code if any mismatches are found
    else:
        sys.exit(0)  # Successful execution

if __name__ == "__main__":
    main()
