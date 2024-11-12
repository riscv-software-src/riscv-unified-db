import re

def parse_header_files(header_files):
    """
    Parses header files to extract MATCH_* and MASK_* definitions.

    Args:
        header_files (list of str): Paths to header files.

    Returns:
        match_dict (dict): Mapping from MATCH_* name to its integer value.
        mask_dict (dict): Mapping from MASK_* name to its integer value.
    """
    match_pattern = re.compile(r'#define\s+MATCH_(\w+)\s+0x([0-9a-fA-F]+)')
    mask_pattern = re.compile(r'#define\s+MASK_(\w+)\s+0x([0-9a-fA-F]+)')

    match_dict = {}
    mask_dict = {}

    for header_file in header_files:
        try:
            with open(header_file, 'r') as file:
                for line in file:
                    # Remove inline comments
                    line = line.split('//')[0]
                    line = line.split('/*')[0]
                    match = match_pattern.match(line)
                    if match:
                        name = match.group(1)
                        value = int(match.group(2), 16)
                        match_dict[name] = value
                        continue
                    mask = mask_pattern.match(line)
                    if mask:
                        name = mask.group(1)
                        value = int(mask.group(2), 16)
                        mask_dict[name] = value
                        continue
        except FileNotFoundError:
            print(f"Error: Header file '{header_file}' not found.")
            continue

    return match_dict, mask_dict

def parse_instruction_files(instruction_files):
    """
    Parses instruction definition files to extract instruction names and their MATCH_* and MASK_* along with class.

    Args:
        instruction_files (list of str): Paths to instruction definition files.

    Returns:
        instructions (list of dict): Each dict contains 'name', 'match_name', 'mask_name', 'class'.
    """
    # Pattern to match instruction definitions
    # Example line:
    # {"add", 0, INSN_CLASS_I, "d,s,t", MATCH_ADD, MASK_ADD, match_opcode, 0 },
    instr_pattern = re.compile(
        r'\{\s*"([\w\.]+)",\s*\d+,\s*(INSN_CLASS_\w+),\s*"[^"]*",\s*MATCH_(\w+),\s*MASK_(\w+),.*\},')

    instructions = []

    for instr_file in instruction_files:
        try:
            with open(instr_file, 'r') as file:
                for line in file:
                    instr_match = instr_pattern.match(line)
                    if instr_match:
                        instr_name = instr_match.group(1)
                        instr_class = instr_match.group(2)
                        match_name = instr_match.group(3)
                        mask_name = instr_match.group(4)
                        instructions.append({
                            'name': instr_name,
                            'class': instr_class,
                            'match_name': match_name,
                            'mask_name': mask_name
                        })
        except FileNotFoundError:
            print(f"Error: Instruction file '{instr_file}' not found.")
            continue

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

def main():
    """
    Main function to parse files and generate instruction encodings.
    """
    # Define file paths ad hoc here
    # Update these paths based on your actual file locations
    header_files = [
        'riscv-opc.h',
        'includeriscv.h'  # Replace with your actual additional header file names
    ]

    instruction_files = [
        'riscv-opc.c'
        # Add more instruction definition files if necessary
    ]

    # Parse header files to get MATCH_* and MASK_* definitions
    match_dict, mask_dict = parse_header_files(header_files)

    # Parse instruction definition files to get instructions
    instructions = parse_instruction_files(instruction_files)

    # Process each instruction and print all encodings
    for instr in instructions:
        name = instr['name']
        instr_class = instr['class']
        match_key = instr['match_name']
        mask_key = instr['mask_name']

        # Retrieve MATCH and MASK values
        match_val = match_dict.get(match_key)
        mask_val = mask_dict.get(mask_key)

        if match_val is None:
            print(f"Warning: MATCH_{match_key} not found for instruction '{name}'. Skipping.")
            continue
        if mask_val is None:
            print(f"Warning: MASK_{mask_key} not found for instruction '{name}'. Skipping.")
            continue

        # Generate the encoding string
        encoding_str = match_mask_to_encoding(match_val, mask_val)

        # Format the encoding string
        formatted_encoding = format_encoding(encoding_str)

        # Print the result, including class information
        print(f'Instruction: {name}')
        print(f'  Class: {instr_class}')
        print(f'  match: {formatted_encoding}\n')

    # Optionally, verify specific instructions if needed
    # e.g., 'add' instruction
    # for instr in instructions:
    #     if instr['name'] == 'add' and instr['class'] == 'INSN_CLASS_I':
    #         encoding_str = match_mask_to_encoding(match_val, mask_val)
    #         formatted_encoding = format_encoding(encoding_str)
    #         print(f'Verification for \'add\' instruction:')
    #         print(f'  match: {formatted_encoding}\n')

if __name__ == "__main__":
    main()
