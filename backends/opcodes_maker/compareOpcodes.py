import json
import pytest
import warnings


def load_json_file(filename):
    with open(filename) as f:
        return json.load(f)


# Pre-load the JSON data from the two files.
JSON1 = load_json_file("sorted_instr_dict.json")
JSON2 = load_json_file("../../ext/riscv-opcodes/instr_dict.json")

# Create lowercase versions of the keys for comparison
JSON1_LOWER = {k.lower(): v for k, v in JSON1.items()}
JSON2_LOWER = {k.lower(): v for k, v in JSON2.items()}

# Compute the common instructions for parametrization.
COMMON_INSTRUCTIONS = sorted(list(set(JSON1_LOWER.keys()) & set(JSON2_LOWER.keys())))


@pytest.fixture
def json1():
    return JSON1


@pytest.fixture
def json2():
    return JSON2


@pytest.fixture
def json1_lower():
    return JSON1_LOWER


@pytest.fixture
def json2_lower():
    return JSON2_LOWER


def test_instructions_missing_in_riscv_opcodes(json1_lower, json2_lower):
    """
    Check for instructions in sorted_instr_dict.json but missing in riscv-opcodes.
    This will issue a warning instead of failing.
    """
    instructions1 = set(json1_lower.keys())
    instructions2 = set(json2_lower.keys())

    missing_in_file2 = instructions1 - instructions2

    if missing_in_file2:
        warnings.warn(f"Instructions missing in riscv-opcodes: {missing_in_file2}")


def test_instructions_missing_in_sorted_dict(json1_lower, json2_lower):
    """
    Check for instructions in riscv-opcodes but missing in sorted_instr_dict.json.
    This will fail the test if any are found.
    """
    instructions1 = set(json1_lower.keys())
    instructions2 = set(json2_lower.keys())

    missing_in_file1 = instructions2 - instructions1

    assert (
        missing_in_file1 == set()
    ), f"Instructions missing in 'sorted_instr_dict.json': {missing_in_file1}"


@pytest.mark.parametrize("instr", COMMON_INSTRUCTIONS)
def test_variable_fields_exact(instr, json1_lower, json2_lower):
    """
    For each common instruction, verify that both JSON files:
      - Have the key 'variable_fields'
      - Contain an identical set of variable_fields (order does not matter)
    """
    entry1 = json1_lower[instr]
    entry2 = json2_lower[instr]

    assert (
        "variable_fields" in entry1
    ), f"Instruction '{instr}' is missing 'variable_fields' in 'sorted_instr_dict.json'"
    assert (
        "variable_fields" in entry2
    ), f"Instruction '{instr}' is missing 'variable_fields' in '../../ext/riscv-opcodes/instr_dict.json'"

    vf1 = entry1["variable_fields"]
    vf2 = entry2["variable_fields"]

    # Compare after sorting the lists so that order is ignored.
    assert sorted(vf1) == sorted(vf2), (
        f"Instruction '{instr}' variable_fields differ:\n"
        f"  sorted_instr_dict.json: {vf1}\n"
        f"  ../../ext/riscv-opcodes/instr_dict.json: {vf2}"
    )
