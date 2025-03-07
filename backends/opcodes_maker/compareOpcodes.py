import json
import pytest


def load_json_file(filename):
    with open(filename) as f:
        return json.load(f)


# Pre-load the JSON data from the two files.
JSON1 = load_json_file("sorted_instr_dict.json")
JSON2 = load_json_file("../../ext/riscv-opcodes/instr_dict.json")

# Compute the common instructions for parametrization.
COMMON_INSTRUCTIONS = sorted(list(set(JSON1.keys()) & set(JSON2.keys())))


@pytest.fixture
def json1():
    return JSON1


@pytest.fixture
def json2():
    return JSON2


def test_instructions_presence(json1, json2):
    """
    Ensure that both JSON files contain the same instructions.
    """
    instructions1 = set(json1.keys())
    instructions2 = set(json2.keys())

    missing_in_file2 = instructions1 - instructions2
    missing_in_file1 = instructions2 - instructions1

    assert (
        missing_in_file2 == set()
    ), f"Instructions missing in '../../ext/riscv-opcodes/instr_dict.json': {missing_in_file2}"
    assert (
        missing_in_file1 == set()
    ), f"Instructions missing in 'sorted_instr_dict.json': {missing_in_file1}"


@pytest.mark.parametrize("instr", COMMON_INSTRUCTIONS)
def test_variable_fields_exact(instr, json1, json2):
    """
    For each common instruction, verify that both JSON files:
      - Have the key 'variable_fields'
      - Contain an identical set of variable_fields (order does not matter)
    """
    entry1 = json1[instr]
    entry2 = json2[instr]

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
