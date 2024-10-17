#!/usr/bin/env python3
import sys
import os
from db_const import *
from itertools import groupby
from operator import itemgetter

# Save the current working directory
original_cwd = os.getcwd()

# Change the working directory to the location of parse.py and constants.py
module_path = os.path.abspath(os.path.join('..', 'riscv-opcodes'))
os.chdir(module_path)

# Ensure that the directory containing parse.py is in sys.path
sys.path.append(module_path)

# Now import the parse.py module, which will also import constants.py
from parse import *

# After importing, change back to the original working directory
os.chdir(original_cwd)


def combine_imm_fields(imm_fields):
    '''
    Combine multiple immediate fields into a single representation.

    Args:
    imm_fields (list): List of immediate field strings

    Returns:
    str: Combined immediate field representation
    '''
    if not imm_fields:
        return ''
    
    all_bits = set()
    for field in imm_fields:
        if '[' in field and ']' in field:
            range_str = field.split('[')[1].split(']')[0]
            parts = range_str.split('|')
            for part in parts:
                if ':' in part:
                    start, end = map(int, part.split(':'))
                    all_bits.update(range(min(start, end), max(start, end) + 1))
                else:
                    all_bits.add(int(part))
        elif field == 'imm':
            return 'imm'  # If there's a generic 'imm', just return it
    
    if all_bits:
        min_bit, max_bit = min(all_bits), max(all_bits)
        return f'imm[{max_bit}:{min_bit}]'
    else:
        return 'imm'    



def make_yaml(instr_dict):
    def get_yaml_long_name(instr_name):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        synopsis_file = os.path.join(current_dir, "synopsis")
        
        if os.path.exists(synopsis_file):
            with open(synopsis_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2 and parts[0].lower() == instr_name.lower():
                        return parts[1]
        
        return 'No synopsis available.'

    def get_yaml_description(instr_name):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        desc_file = os.path.join(current_dir, "description")

        if os.path.exists(desc_file):
            with open(desc_file, 'r') as f:
                lines = f.readlines()
                # Skip the first line as it's the header
                for line in lines[1:]:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2 and parts[0].lower() == instr_name.lower():
                        return parts[1]
        
        return "No description available."
        

    def get_yaml_assembly(instr_name, instr_dict):
        instr_data = instr_dict[instr_name]
        var_fields = instr_data.get('variable_fields', [])
        reg_args = []
        imm_args = []

        for field in var_fields:
            mapped_field = asciidoc_mapping.get(field, field)
            if ('imm' in field) or ('offset' in field):
                imm_args.append(mapped_field)
            else:
                reg_args.append(mapped_field.replace('rs', 'xs').replace('rd', 'xd'))

        # Combine immediate fields
        combined_imm = combine_imm_fields(imm_args)
    
        # Combine all arguments, registers first then immediates
        all_args = reg_args + (['imm'] if combined_imm else [])
        # Create the assembly string
        assembly = f"{', '.join(all_args)}" if all_args else instr_name

        return assembly

    
    def process_extension(ext):
        parts = ext.split('_')
        if len(parts) == 2:
            return [parts[1].capitalize()]
        elif len(parts) == 3:
            return [parts[1].capitalize(), parts[2].capitalize()]
        else:
            return [ext.capitalize()]  # fallback for unexpected formats
        
    def parse_imm_location(field_name, imm_str):
        parts = imm_str.split('[')[1].split(']')[0].split('|')
        location_parts = []
        start_bit, end_bit = arg_lut[field_name]
        total_bits = start_bit - end_bit + 1
        current_encoding_bit = start_bit

        for part in parts:
            if ':' in part:
                part_start, part_end = map(int, part.split(':'))
                start, end = max(part_start, part_end), min(part_start, part_end)
                for i in range(start, end-1, -1):
                    real_bit = i
                    encoding_bit = current_encoding_bit
                    location_parts.append((real_bit, encoding_bit))
                    current_encoding_bit -= 1
            else:
                real_bit = int(part)
                encoding_bit = current_encoding_bit
                location_parts.append((real_bit, encoding_bit))
                current_encoding_bit -= 1

        # Sort the location_parts by real_bit in descending order
        location_parts.sort(key=lambda x: x[0], reverse=True)
        return location_parts

    def make_yaml_encoding(instr_name, instr_data):
        encoding = instr_data['encoding']
        var_fields = instr_data.get('variable_fields', [])

        match = ''.join([bit if bit != '-' else '-' for bit in encoding])

        variables = []
        imm_locations = []

        for field_name in var_fields:
            if field_name in asciidoc_mapping:
                mapped_name = asciidoc_mapping[field_name]
                if '[' in mapped_name and ']' in mapped_name and (mapped_name.startswith('imm') or mapped_name.startswith('uimm') or mapped_name.startswith('nzimm')):
                    # This is an immediate field
                    imm_locations.extend(parse_imm_location(field_name, mapped_name))
                else:
                    # This is a regular field
                    start_bit, end_bit = arg_lut[field_name]
                    variables.append({
                        'name': mapped_name,
                        'location': f'{start_bit}-{end_bit}'
                    })
            else:
                # If not in asciidoc_mapping, use the original field name and bit range
                start_bit, end_bit = arg_lut[field_name]
                variables.append({
                    'name': field_name,
                    'location': f'{start_bit}-{end_bit}'
                })

        # Add merged immediate field if there are any immediate parts
        if imm_locations:
            # Sort immediate parts by their real bit position (descending order)
            imm_locations.sort(key=lambda x: x[0], reverse=True)
            
            # Merge adjacent ranges based on encoding bits
            merged_parts = []
            current_range = None
            for real_bit, encoding_bit in imm_locations:
                if current_range is None:
                    current_range = [encoding_bit, encoding_bit, real_bit, real_bit]
                elif encoding_bit == current_range[1] - 1:
                    current_range[1] = encoding_bit
                    current_range[3] = real_bit
                else:
                    merged_parts.append(tuple(current_range))
                    current_range = [encoding_bit, encoding_bit, real_bit, real_bit]
            if current_range:
                merged_parts.append(tuple(current_range))
            
            # Convert merged parts to string representation
            imm_location = '|'.join([f'{start}' if start == end else f'{start}-{end}' 
                                    for start, end, _, _ in merged_parts])
            
            variables.append({
                'name': 'imm',
                'location': imm_location
            })

        # Sort variables in descending order based on the start of the bit range
        variables.sort(key=lambda x: int(x['location'].split('-')[0].split('|')[0]), reverse=True)

        result = {
            'match': match,
            'variables': variables
        }

        return result
        
    def get_yaml_encoding_diff(instr_data_original, pseudo_instructions):
        def get_variables(instr_data):
            encoding = instr_data['encoding']
            var_fields = instr_data.get('variable_fields', [])
            
            variables = {}
            for field_name in var_fields:
                if field_name in arg_lut:
                    start_bit, end_bit = arg_lut[field_name]
                    variables[field_name] = {
                        'field_name': field_name,
                        'match': encoding[31-start_bit:32-end_bit],
                        'start_bit': start_bit,
                        'end_bit': end_bit
                    }
            return variables

        original_vars = get_variables(instr_data_original)
        differences = {}

        for pseudo_name, pseudo_data in pseudo_instructions.items():
            pseudo_vars = get_variables(pseudo_data)
            field_differences = {}

            # Find fields that are different or unique to each instruction
            all_fields = set(original_vars.keys()) | set(pseudo_vars.keys())
            for field in all_fields:
                if field not in pseudo_vars:
                    field_differences[field] = {
                        'pseudo_value': pseudo_data['encoding'][31-original_vars[field]['start_bit']:32-original_vars[field]['end_bit']]
                    }
                elif field not in original_vars:
                    field_differences[field] = {
                        'pseudo_value': pseudo_vars[field]['match']
                    }
                elif original_vars[field]['match'] != pseudo_vars[field]['match']:
                    field_differences[field] = {
                        'pseudo_value': pseudo_vars[field]['match']
                    }

            if field_differences:
                differences[pseudo_name] = field_differences

        return differences

    def get_yaml_definedby(instr_data):
        defined_by = set()
        for ext in instr_data['extension']:
            parts = ext.split('_')
            if len(parts) > 1:
                # Handle cases like 'rv32_d_zicsr'
                for part in parts[1:]:
                    defined_by.add(part.capitalize())
            else:
                defined_by.add(ext.capitalize())
        
        return f"[{', '.join(sorted(defined_by))}]"



    def get_yaml_base(instr_data):
        for ext in instr_data['extension']:
            if ext.startswith('rv32'):
                return 32
            elif ext.startswith('rv64'):
                return 64
        return None


    # Group instructions by extension
    extensions = {}
    rv32_instructions = {}
    for instr_name, instr_data in instr_dict.items():
        if instr_name.endswith('_rv32'):
            base_name = instr_name[:-5]
            rv32_instructions[base_name] = instr_name
        else:
            for ext in instr_data['extension']:
                ext_letters = process_extension(ext)
                for ext_letter in ext_letters:
                    if ext_letter not in extensions:
                        extensions[ext_letter] = {}
                    extensions[ext_letter][instr_name] = instr_data


    # Create a directory to store the YAML files
    base_dir = 'yaml_output'
    os.makedirs(base_dir, exist_ok=True)

    # Generate and save YAML for each extension
    for ext, ext_dict in extensions.items():
        ext_dir = os.path.join(base_dir, ext)
        os.makedirs(ext_dir, exist_ok=True)
    
        
        for instr_name, instr_data in ext_dict.items():
            yaml_content = {}
            instr_name_with_periods = instr_name.replace('_', '.')
            yaml_content[instr_name_with_periods] = {
                'long_name': get_yaml_long_name(instr_name),
                'description': get_yaml_description(instr_name),
                'definedBy': get_yaml_definedby(instr_data),
                'base': get_yaml_base(instr_data),
                'assembly': get_yaml_assembly(instr_name, instr_dict),
                'encoding': make_yaml_encoding(instr_name, instr_data),
                'access': {
                            's': 'TODO',
                            'u': 'TODO',
                            'vs': 'TODO',
                            'vu': 'TODO'
                },
            }

            # Add pseudoinstruction field for origin instructions
            if 'pseudo_ops' in instr_data:
                pseudo_list = [pseudo.replace('_', '.') for pseudo in instr_data['pseudo_ops']]
                if pseudo_list:
                    yaml_content[instr_name_with_periods]['pseudoinstructions'] = []
                    pseudo_instructions = {pseudo.replace('.', '_'): instr_dict[pseudo.replace('.', '_')] for pseudo in pseudo_list}
                    encoding_diffs = get_yaml_encoding_diff(instr_data, pseudo_instructions)
                    for pseudo in pseudo_list:
                        assembly = get_yaml_assembly(pseudo.replace('.', '_'), instr_dict)
                        diff_info = encoding_diffs.get(pseudo.replace('.', '_'), {})
                        when_condition = get_yaml_assembly(instr_name, instr_dict).replace(assembly,"").replace(",","")
                        if diff_info:
                            diff_str = ", ".join([f"{field}=={details['pseudo_value']}" for field, details in diff_info.items()])
                            when_condition = f"{diff_str}"
                        yaml_content[instr_name_with_periods]['pseudoinstructions'].append({
                            'when': when_condition,
                            'to': f"{pseudo} {assembly}",
                        })
            
            
            #  Add origininstruction field for pseudo instructions
            if instr_data.get('is_pseudo', False):
                yaml_content[instr_name_with_periods]['origininstruction'] = instr_data['orig_inst'].replace('_', '.')

            # Add operation field last
            yaml_content[instr_name_with_periods]['operation'] = None

            # Handle encoding for RV32 and RV64 versions
            if instr_name in rv32_instructions:
                yaml_content[instr_name_with_periods]['encoding'] = {
                    'RV32': make_yaml_encoding(rv32_instructions[instr_name], instr_dict[rv32_instructions[instr_name]]),
                    'RV64': make_yaml_encoding(instr_name, instr_data)
                }
            else:
                yaml_content[instr_name_with_periods]['encoding'] = make_yaml_encoding(instr_name, instr_data)

            if yaml_content[instr_name_with_periods]['base'] is None or (instr_name in rv32_instructions):
                yaml_content[instr_name_with_periods].pop('base')


        
            yaml_string = "# yaml-language-server: $schema=../../../schemas/inst_schema.json\n\n"
            yaml_string += yaml.dump(yaml_content, default_flow_style=False, sort_keys=False)
            yaml_string = yaml_string.replace("'[", "[").replace("]'","]").replace("'-","-").replace("0'","0").replace("1'","1").replace("-'","-")
            yaml_string = re.sub(r'description: (.+)', lambda m: f'description: |\n      {m.group(1)}', yaml_string)
            yaml_string = re.sub(r'operation: (.+)', lambda m: f'operation(): |\n      {""}', yaml_string)



            # Write to file
            filename = f'{instr_name_with_periods}.yaml'
            filepath = os.path.join(ext_dir, filename)
            with open(filepath, 'w') as outfile:
                outfile.write(yaml_string)
    
    print("Summary of all extensions saved as yaml_output/extensions_summary.yaml")


if __name__ == "__main__":
    print(f'Running with args : {sys.argv}')

    extensions = sys.argv[1:]
    for i in ['-c','-latex','-chisel','-sverilog','-rust', '-go', '-spinalhdl','-asciidoc', '-yaml']:
        if i in extensions:
            extensions.remove(i)
    print(f'Extensions selected : {extensions}')

    if '-yaml' in sys.argv[1: ]:
        instr_dict = create_inst_dict(extensions)  # make sure instr_dict is created
        make_yaml(instr_dict)
        logging.info('instr.yaml generated successfully')

