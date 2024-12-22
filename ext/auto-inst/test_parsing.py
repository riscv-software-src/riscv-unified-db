import pytest
import json
import os
import re
import yaml
from pathlib import Path

def get_json_path():
    """Get the path to the JSON file relative to the test file."""
    current_dir = Path(__file__).parent
    return str(current_dir / "../../../llvm-project/build/unorder.json")

def get_yaml_directory():
    """Get the path to the YAML directory relative to the test file."""
    current_dir = Path(__file__).parent
    return str(current_dir / "../../arch/inst/")

def load_inherited_variable(var_path, repo_dir):
    """Load variable definition from an inherited YAML file."""
    try:
        # Parse the path to get directory and anchor
        path, anchor = var_path.split('#')
        if anchor.startswith('/'):
            anchor = anchor[1:]  # Remove leading slash
        
        # Construct full path
        full_path = os.path.join(repo_dir, path)
        
        if not os.path.exists(full_path):
            print(f"Warning: Inherited file not found: {full_path}")
            return None
            
        with open(full_path, 'r') as f:
            data = yaml.safe_load(f)
            
        # Navigate through the anchor path
        for key in anchor.split('/'):
            if key in data:
                data = data[key]
            else:
                print(f"Warning: Anchor path {anchor} not found in {path}")
                return None
                
        return data
    except Exception as e:
        print(f"Error loading inherited variable {var_path}: {str(e)}")
        return None

def resolve_variable_definition(var, repo_dir):
    """Resolve variable definition, handling inheritance if needed."""
    if 'location' in var:
        return var
    elif '$inherits' in var:
            print(f"Warning: Failed to resolve inheritance for variable: {var}")
    return None

def parse_location(loc_str):
    """Parse location string that may contain multiple ranges."""
    if not loc_str:
        return []
        
    loc_str = str(loc_str).strip()
    ranges = []
    
    # Split on pipe if there are multiple ranges
    for range_str in loc_str.split('|'):
        range_str = range_str.strip()
        if '-' in range_str:
            high, low = map(int, range_str.split('-'))
            ranges.append((high, low))
        else:
            # Single bit case
            try:
                val = int(range_str)
                ranges.append((val, val))
            except ValueError:
                print(f"Warning: Invalid location format: {range_str}")
                continue
    
    return ranges

def compare_yaml_json_encoding(instr_name, yaml_match, yaml_vars, json_encoding_str, repo_dir):
    """Compare the YAML encoding with the JSON encoding."""
    if not yaml_match:
        return ["No YAML match field available for comparison."]
    if not json_encoding_str:
        return ["No JSON encoding available for comparison."]

    # Determine expected length based on whether it's a compressed instruction (C_ or c.)
    expected_length = 16 if instr_name.lower().startswith(('c_', 'c.')) else 32

    yaml_pattern_str = yaml_match.replace('-', '.')
    if len(yaml_pattern_str) != expected_length:
        return [f"YAML match pattern length is {len(yaml_pattern_str)}, expected {expected_length}. Cannot compare properly."]

    # Process variables and their locations
    yaml_var_positions = {}
    for var in (yaml_vars or []):
        resolved_var = resolve_variable_definition(var, repo_dir)
        if not resolved_var or 'location' not in resolved_var:
            print(f"Warning: Could not resolve variable definition for {var.get('name', 'unknown')}")
            continue
        
        ranges = parse_location(resolved_var['location'])
        if ranges:
            yaml_var_positions[var['name']] = ranges

    # Tokenize the JSON encoding string
    tokens = re.findall(r'(?:[01]|[A-Za-z0-9]+(?:\[\d+\]|\[\?\])?)', json_encoding_str)
    json_bits = []
    bit_index = expected_length - 1
    for t in tokens:
        json_bits.append((bit_index, t))
        bit_index -= 1

    if bit_index != -1:
        return [f"JSON encoding does not appear to be {expected_length} bits. Ends at bit {bit_index+1}."]

    # Normalize JSON bits (handle vm[?] etc.)
    normalized_json_bits = []
    for pos, tt in json_bits:
        if re.match(r'vm\[[^\]]*\]', tt):
            tt = 'vm'
        normalized_json_bits.append((pos, tt))
    json_bits = normalized_json_bits

    differences = []

    # Check fixed bits
    for b in range(expected_length):
        yaml_bit = yaml_pattern_str[expected_length - 1 - b]
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
    for var_name, ranges in yaml_var_positions.items():
        for high, low in ranges:
            # Ensure the variable range fits within the expected_length
            if high >= expected_length or low < 0:
                differences.append(f"Variable {var_name}: location {high}-{low} is out of range for {expected_length}-bit instruction.")
                continue

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

@pytest.fixture
def yaml_instructions():
    """Load all YAML instructions from the repository."""
    from parsing import get_yaml_instructions
    repo_dir = get_yaml_directory()
    if not os.path.exists(repo_dir):
        pytest.skip(f"Repository directory not found at {repo_dir}")
    return get_yaml_instructions(repo_dir)

@pytest.fixture
def json_data():
    """Load the real JSON data from the TableGen file."""
    json_file = get_json_path()
    if not os.path.exists(json_file):
        pytest.skip(f"JSON file not found at {json_file}")
    with open(json_file, 'r') as f:
        return json.load(f)

def pytest_configure(config):
    """Configure the test session."""
    print(f"\nUsing JSON file: {get_json_path()}")
    print(f"Using YAML directory: {get_yaml_directory()}\n")

class TestEncodingComparison:
    def test_encoding_matches(self, yaml_instructions, json_data):
        """Test YAML-defined instructions against their JSON counterparts if they exist."""
        mismatches = []
        total_yaml_instructions = 0
        checked_instructions = 0
        skipped_instructions = []
        repo_dir = get_yaml_directory()
        
        for yaml_instr_name, yaml_data in yaml_instructions.items():
            total_yaml_instructions += 1
            
            # Skip if no YAML match pattern
            if not yaml_data.get("yaml_match"):
                skipped_instructions.append(yaml_instr_name)
                continue

            # Get JSON encoding from instruction data
            json_key = self._find_matching_instruction(yaml_instr_name, json_data)
            if not json_key:
                skipped_instructions.append(yaml_instr_name)
                continue

            checked_instructions += 1
            json_encoding = self._get_json_encoding(json_data[json_key])
            
            # Compare encodings using the existing function
            differences = compare_yaml_json_encoding(
                yaml_instr_name,
                yaml_data["yaml_match"],
                yaml_data["yaml_vars"],
                json_encoding,
                repo_dir
            )

            if differences and differences != ["No YAML match field available for comparison."]:
                mismatches.append({
                    'instruction': yaml_instr_name,
                    'json_key': json_key,
                    'differences': differences,
                    'yaml_match': yaml_data["yaml_match"],
                    'json_encoding': json_encoding
                })

        # Print statistics
        print(f"\nYAML instructions found: {total_yaml_instructions}")
        print(f"Instructions checked: {checked_instructions}")
        print(f"Instructions skipped: {len(skipped_instructions)}")
        print(f"Instructions with encoding mismatches: {len(mismatches)}")
        
        if skipped_instructions:
            print("\nSkipped instructions:")
            for instr in skipped_instructions:
                print(f"  - {instr}")

        if mismatches:
            error_msg = "\nEncoding mismatches found:\n"
            for m in mismatches:
                error_msg += f"\nInstruction: {m['instruction']} (JSON key: {m['json_key']})\n"
                error_msg += f"YAML match: {m['yaml_match']}\n"
                error_msg += f"JSON encoding: {m['json_encoding']}\n"
                error_msg += "Differences:\n"
                for d in m['differences']:
                    error_msg += f"  - {d}\n"
            pytest.fail(error_msg)

    def _find_matching_instruction(self, yaml_instr_name, json_data):
        """Find matching instruction in JSON data by comparing instruction names."""
        yaml_instr_name = yaml_instr_name.lower().strip()
        for key, value in json_data.items():
            if not isinstance(value, dict):
                continue
            asm_string = value.get('AsmString', '').lower().strip()
            if not asm_string:
                continue
            base_asm_name = asm_string.split()[0]
            if base_asm_name == yaml_instr_name:
                return key
        return None

    def _get_json_encoding(self, json_instr):
        """Extract encoding string from JSON instruction data."""
        encoding_bits = []
        try:
            inst = json_instr.get('Inst', [])
            for bit in inst:
                if isinstance(bit, dict):
                    encoding_bits.append(f"{bit.get('var', '?')}[{bit.get('index', '?')}]")
                else:
                    encoding_bits.append(str(bit))
            encoding_bits.reverse()
            return "".join(encoding_bits)
        except:
            return ""