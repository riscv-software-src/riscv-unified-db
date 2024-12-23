import pytest
import json
import os
import re
import yaml
from pathlib import Path

def get_json_path():
    """Get the path to the JSON file relative to the test file."""
    current_dir = Path(__file__).parent
    return str(current_dir / "/home/afonsoo/llvm-project/llvm-build/pretty.json")

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

# Global variables to store loaded data
_yaml_instructions = None
_json_data = None
_repo_dir = None

def load_test_data():
    """Load test data once and cache it."""
    global _yaml_instructions, _json_data, _repo_dir
    if _yaml_instructions is None:
        # Load YAML instructions
        from parsing import get_yaml_instructions
        _repo_dir = get_yaml_directory()
        if not os.path.exists(_repo_dir):
            pytest.skip(f"Repository directory not found at {_repo_dir}")
        _yaml_instructions = get_yaml_instructions(_repo_dir)

        # Load JSON data
        json_file = get_json_path()
        if not os.path.exists(json_file):
            pytest.skip(f"JSON file not found at {json_file}")
        with open(json_file, 'r') as f:
            _json_data = json.load(f)

    return _yaml_instructions, _json_data, _repo_dir

def pytest_generate_tests(metafunc):
    """Generate test cases dynamically."""
    if "instr_name" in metafunc.fixturenames:
        yaml_instructions, _, _ = load_test_data()
        metafunc.parametrize("instr_name", list(yaml_instructions.keys()))

class TestInstructionEncoding:
    @classmethod
    def setup_class(cls):
        """Setup class-level test data."""
        cls.yaml_instructions, cls.json_data, cls.repo_dir = load_test_data()

    def _find_matching_instruction(self, yaml_instr_name):
        """Find matching instruction in JSON data by comparing instruction names."""
        yaml_instr_name = yaml_instr_name.lower().strip()
        for key, value in self.json_data.items():
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

    def test_instruction_encoding(self, instr_name):
        """Test encoding for a single instruction."""
        yaml_data = self.yaml_instructions[instr_name]
        
        # Skip if no YAML match pattern
        if not yaml_data.get("yaml_match"):
            pytest.skip(f"Instruction {instr_name} has no YAML match pattern")

        # Find matching JSON instruction
        json_key = self._find_matching_instruction(instr_name)
        if not json_key:
            pytest.skip(f"No matching JSON instruction found for {instr_name}")

        # Get JSON encoding
        json_encoding = self._get_json_encoding(self.json_data[json_key])
        
        # Compare encodings
        differences = compare_yaml_json_encoding(
            instr_name,
            yaml_data["yaml_match"],
            yaml_data.get("yaml_vars", []),
            json_encoding,
            self.repo_dir
        )

        # If there are differences, format them nicely and fail the test
        if differences and differences != ["No YAML match field available for comparison."]:
            error_msg = f"\nEncoding mismatch for instruction: {instr_name}\n"
            error_msg += f"JSON key: {json_key}\n"
            error_msg += f"YAML match: {yaml_data['yaml_match']}\n"
            error_msg += f"JSON encoding: {json_encoding}\n"
            error_msg += "Differences:\n"
            for diff in differences:
                error_msg += f"  - {diff}\n"
            pytest.fail(error_msg)

def pytest_configure(config):
    """Configure the test session."""
    print(f"\nUsing JSON file: {get_json_path()}")
    print(f"Using YAML directory: {get_yaml_directory()}\n")
