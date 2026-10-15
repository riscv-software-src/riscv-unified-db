# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from copy import deepcopy

import pytest

from udb import ReferenceError, ResolvedDatabase
from udb.instruction_fields import InstructionFieldError, instruction_fields
from udb.instruction_table import render_instruction_table


def documents():
    return {
        "inst_type/T.yaml": {"kind": "instruction_type", "name": "T", "length": 16},
        "inst_var_type/V.yaml": {
            "kind": "instruction_variable_type",
            "name": "V",
            "type": "immediate",
        },
        "inst_opcode/Op.yaml": {
            "kind": "instruction_opcode",
            "name": "Op",
            "data": {"value": 2},
        },
        "inst_subtype/T/Sub.yaml": {
            "kind": "instruction_subtype",
            "name": "Sub",
            "data": {
                "variables": {
                    "imm": {
                        "location": "11-8|7-4",
                        "sign_extend": True,
                        "left_shift": 1,
                        "not": 0,
                        "type": {"$ref": "inst_var_type/V.yaml#"},
                    },
                    "rs": {"location": "3-2", "alias": "rd"},
                },
            },
        },
        "inst/test.yaml": {
            "kind": "instruction",
            "name": "test",
            "assembly": "rd, imm",
            "format": {
                "type": {"$ref": "inst_type/T.yaml#"},
                "subtype": {"$ref": "inst_subtype/T/Sub.yaml#"},
                "opcodes": {
                    # Deliberately LSB first; adjacent MSB fields must merge.
                    "op": {"location": "1-0", "value": {"$ref": "inst_opcode/Op.yaml#"}},
                    "high": {"location": "15-14", "value": 1, "display_name": "high"},
                    "middle": {"location": "13-12", "value": 3},
                },
            },
        },
    }


def test_reference_format_uses_subtype_order_and_merges_adjacent_opcodes():
    source = ResolvedDatabase(documents())
    descriptor = instruction_fields(source, "test")
    assert descriptor.assembly == "rd, imm"
    assert descriptor.encoding(32).match == "0111----------10"
    assert descriptor.encoding(32).variables[0].width == 9
    assert render_instruction_table(source).splitlines()[-1] == (
        "test common 0111<12|10<0 imm~!0<1=11-8|7-4 rs=3-2"
    )


def test_equivalent_format_local_annotations_are_validated():
    data = documents()
    data["inst/test.yaml"]["format"]["variables"] = deepcopy(
        data["inst_subtype/T/Sub.yaml"]["data"]["variables"]
    )
    assert instruction_fields(ResolvedDatabase(data), "test").encoding(64).length == 16


def test_per_xlen_type_widths_and_formats():
    data = documents()
    raw = data["inst/test.yaml"].pop("format")
    rv64 = deepcopy(raw)
    rv64["type"] = {"$ref": "inst_type/Wide.yaml#"}
    rv64["opcodes"]["prefix"] = {"location": "23-16", "value": 255}
    data["inst_type/Wide.yaml"] = {
        "kind": "instruction_type",
        "name": "Wide",
        "length": 24,
    }
    data["inst/test.yaml"]["format"] = {"RV32": raw, "RV64": rv64}
    source = ResolvedDatabase(data)
    assert instruction_fields(source, "test").encoding(64).length == 24
    assert render_instruction_table(source).splitlines()[-2:] == [
        "test common,32 0111<12|10<0 imm~!0<1=11-8|7-4 rs=3-2",
        "test common,64 111111110111<12|10<0 imm~!0<1=11-8|7-4 rs=3-2",
    ]


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("inst/test.yaml", "format", "extra"), True, "unsupported"),
        (("inst_type/T.yaml", "length"), 0, "positive"),
        (("inst_type/T.yaml", "length"), True, "positive"),
        (("inst/test.yaml", "format", "opcodes", "high", "value"), 4, "fit"),
        (("inst/test.yaml", "format", "opcodes", "high", "value"), -1, "fit"),
        (("inst/test.yaml", "format", "opcodes", "high", "value"), True, "fit"),
        (("inst/test.yaml", "format", "opcodes", "high", "location"), "15|14", "contiguous"),
        (("inst/test.yaml", "format", "opcodes", "high", "location"), "14-13", "overlap"),
        (("inst/test.yaml", "format", "opcodes", "high", "future"), True, "unsupported"),
        (("inst/test.yaml", "format", "opcodes", "high", "display_name"), 9, "string"),
        (("inst/test.yaml", "format", "variables"), {"new": {"location": "3-2"}}, "disagrees"),
        (("inst_opcode/Op.yaml", "data"), 0, "mapping"),
        (("inst_subtype/T/Sub.yaml", "data", "variables", "rs", "name"), "other", "disagrees"),
    ],
)
def test_format_errors_have_source_and_pointer(path, value, message):
    data = documents()
    current = data
    for token in path[:-1]:
        current = current[token]
    current[path[-1]] = value
    with pytest.raises(InstructionFieldError, match=message) as error:
        instruction_fields(ResolvedDatabase(data), "test")
    assert ".yaml#/" in str(error.value)


def test_missing_reference_never_falls_back_to_bundled_data():
    data = documents()
    del data["inst_type/T.yaml"]
    with pytest.raises(ReferenceError, match="missing document"):
        instruction_fields(ResolvedDatabase(data), "test")
