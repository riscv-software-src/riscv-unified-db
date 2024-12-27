import pytest
import json
import os
from parsing import (
    get_json_path,
    get_yaml_directory,
    get_yaml_instructions,
    compare_yaml_json_encoding
)

# Global variables to store loaded data
_yaml_instructions = None
_json_data = None
_repo_dir = None

def load_test_data():
    """Load test data once and cache it."""
    global _yaml_instructions, _json_data, _repo_dir
    if _yaml_instructions is None:
        # Load YAML instructions
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

def has_aqrl_variables(yaml_vars):
    """Check if instruction has aq/rl variables."""
    if not yaml_vars:
        return False
    return any(var.get("name") in ["aq", "rl"] for var in yaml_vars)

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
        # The new JSON has top-level keys, each key is an instruction name
        cls.rv_instructions = list(cls.json_data.keys())

    def _find_matching_instruction(self, yaml_instr_name):
        """Find matching instruction in JSON data by comparing instruction names."""
        yaml_instr_name = yaml_instr_name.lower().strip()

        for def_name in self.rv_instructions:
            # In the new JSON, def_name itself is the key, e.g. "vsm3c_vi"
            # So if it matches the YAML instruction name, we consider that a match:
            if def_name.lower().strip() == yaml_instr_name:
                return def_name

        return None

    def _get_json_encoding(self, json_instr):
        """Extract encoding string from JSON instruction data."""
        # The new JSON uses a single string in `instruction["encoding"]`.
        # We'll transform it so the existing comparison code still works with the returned string.

        encoding_str = json_instr.get("encoding", "")
        # The old code used to build an array then reverse it. Let’s do similarly:
        encoding_bits = []

        for char in encoding_str:
            if char in ('0', '1'):
                encoding_bits.append(char)
            else:
                # For placeholders like '-', we can turn them into '?' so the
                # old logic for variable bits remains consistent
                encoding_bits.append('-')

        # Reverse to match the old behavior (the old code reversed at the end)

        return "".join(encoding_bits)

    def test_instruction_encoding(self, instr_name):
        if instr_name.lower().startswith("c."):
            pytest.skip(f"Skipping compressed instruction: {instr_name}")

        """Test encoding for a single instruction."""
        yaml_data = self.yaml_instructions[instr_name]

        # Skip if the instruction has aq/rl variables
        if has_aqrl_variables(yaml_data.get("yaml_vars", [])):
            pytest.skip(f"Skipping instruction {instr_name} due to aq/rl variables")

        # Skip if no YAML match pattern
        if not yaml_data.get("yaml_match"):
            pytest.skip(f"Instruction {instr_name} has no YAML match pattern")

        # Find matching JSON instruction
        json_key = self._find_matching_instruction(instr_name.replace('.', '_'))
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
