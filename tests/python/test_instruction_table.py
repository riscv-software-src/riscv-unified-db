# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import io
import shutil
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest

from udb import Configuration, ConfiguredArchitecture, Database, QueryPresence, ResolvedDatabase
from udb.instruction_fields import (
    BitRange,
    DecodeField,
    EncodingFields,
    InstructionFieldBuilder,
    InstructionFieldError,
    InstructionFields,
    OpcodeField,
    instruction_fields,
)
from udb.instruction_table import (
    generate_instruction_table,
    instruction_table_rows,
    render_instruction_table,
    render_instruction_table_rows,
)
from udb.source import SourceMap, SourceSpan

FIXTURES = Path(__file__).parent / "fixtures/instruction_table"


def database(*instructions, extra=None):
    return ResolvedDatabase(
        {
            **{
                f"inst/{item['name']}.yaml": {"kind": "instruction", **item}
                for item in instructions
            },
            **(extra or {}),
        }
    )


def inst(name="test", *, match="1--0", variables=None, **extra):
    return {
        "name": name,
        "encoding": {
            "match": match,
            "variables": [{"name": "x", "location": "2-1"}] if variables is None else variables,
        },
        **extra,
    }


@pytest.fixture
def output_dir():
    # All test writes are owned, checkout-relative, and cleaned up.
    path = Path("gen/test-instruction-table") / str(uuid4())
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def row_text(source):
    return [
        line for line in render_instruction_table(source).splitlines() if not line.startswith("#")
    ]


def test_describe_accepts_own_resolved_instruction_without_source_switching():
    source = database(inst())
    record = source.instruction("test")
    descriptor = InstructionFieldBuilder(source).describe(record)
    assert descriptor.instruction is record


def test_describe_accepts_own_raw_and_effective_records(output_dir):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "test.yaml").write_text(
        "kind: instruction\nname: test\nencoding:\n  match: '1'\n  variables: []\n"
    )
    source = Database.from_path(output_dir / "isa")
    builder = InstructionFieldBuilder(source)
    raw_record = source.instruction("test")
    effective_record = builder.database.instruction("test")
    assert builder.describe(raw_record).instruction is effective_record
    assert builder.describe(effective_record).instruction is effective_record


@pytest.mark.parametrize(
    ("name", "match"),
    [
        ("test", "0--0"),
        ("test", "1--0"),
        ("not-in-the-source", "1--0"),
    ],
)
def test_describe_rejects_foreign_record_even_when_name_and_data_agree(name, match):
    source = database(inst())
    item = inst(name, match=match)
    path = f"inst/{name}.yaml"
    foreign = ResolvedDatabase(
        {path: {"kind": "instruction", **item}},
        sources={
            path: SourceMap(
                path,
                {("name",): SourceSpan("original-foreign.yaml", 2, 7, layer="overlay")},
            )
        },
    ).instruction(name)
    builder = InstructionFieldBuilder(source)
    with pytest.raises(InstructionFieldError, match="belongs to a different database") as error:
        builder.describe(foreign)
    assert "overlay:original-foreign.yaml:2:7#/name" in str(error.value)
    assert builder.describe("test").encoding(32).match == "1--0"


def test_describe_rejects_distinct_equal_record_to_preserve_source_identity():
    first = database(inst())
    second = database(inst())
    assert first.instruction("test") == second.instruction("test")
    with pytest.raises(InstructionFieldError, match="different database"):
        instruction_fields(first, second.instruction("test"))


@pytest.mark.parametrize(
    "name",
    [
        "a b",
        "a\tb",
        "a\nb",
        "a\rb",
        "a\vb",
        "a\fb",
        "a\u00a0b",
        "a\u2028b",
        "a\0b",
        "a\x7fb",
        "a\u200bb",
        "x=y",
        "x|y",
        "x~y",
        "x!y",
        "x<y",
        "x>y",
        "#comment",
        "x#comment",
    ],
)
def test_ambiguous_instruction_names_fail_with_original_source(name):
    path = f"inst/{name}.yaml"
    source = ResolvedDatabase(
        {path: {"kind": "instruction", **inst(name)}},
        sources={
            path: SourceMap(
                path,
                {("name",): SourceSpan("unsafe-name.yaml", 2, 7)},
            )
        },
    )
    with pytest.raises(InstructionFieldError, match="instruction name is ambiguous") as error:
        render_instruction_table(source)
    assert "unsafe-name.yaml:2:7#/name" in str(error.value)


@pytest.mark.parametrize("name", ["c.nop", "vadd.vv", "x-custom.op_1", "Xvendor.op", "foo0"])
def test_unambiguous_instruction_names_are_not_rewritten_or_narrowed(name):
    assert row_text(database(inst(name))) == [f"{name} common 1<3|0<0 x=2-1"]


def test_scattered_bits_modifiers_order_alias_and_width():
    source = database(
        inst(
            match="--10----",
            variables=[
                {
                    "name": "imm",
                    "location": "0|7-6|3-1",
                    "sign_extend": True,
                    "not": [-8, 3, 0, 3],
                    "left_shift": 2,
                    "alias": "offset",
                },
            ],
            assembly="offset",
            long_name="Not the mnemonic",
        )
    )
    descriptor = instruction_fields(source, "test")
    variable = descriptor.encoding(32).variables[0]
    assert descriptor.assembly == "offset"
    assert variable.bits == (0, 7, 6, 3, 2, 1)
    assert variable.encoded_width == 6
    assert variable.width == 8
    assert variable.alias == "offset"
    assert row_text(source) == ["test common 10<4 imm~!-8!3!0!3<2=0|7-6|3-1"]
    with pytest.raises(FrozenInstanceError):
        variable.name = "new"


@pytest.mark.parametrize("length", [1, 16, 32, 48, 64])
def test_instruction_width_is_not_xlen(length):
    source = database(inst(match="1" * length, variables=[]))
    descriptor = instruction_fields(source, "test")
    assert descriptor.encoding(32).length == length
    assert descriptor.encoding(64).opcodes[0].location == BitRange(length - 1, 0)
    assert row_text(source) == [f"test common {'1' * length}<0"]


def test_four_base_layouts_and_full_row_order():
    source = database(
        inst("z32", definedBy={"xlen": 32}),
        inst("a64", definedBy={"xlen": 64}),
        inst("shared"),
        {
            "name": "different",
            "encoding": {
                "RV32": {"match": "1--0", "variables": [{"name": "x", "location": "2-1"}]},
                "RV64": {"match": "1---", "variables": [{"name": "x", "location": "2-0"}]},
            },
        },
    )
    assert row_text(source) == [
        "a64 64 1<3|0<0 x=2-1",
        "different common,32 1<3|0<0 x=2-1",
        "different common,64 1<3 x=2-0",
        "shared common 1<3|0<0 x=2-1",
        "z32 32 1<3|0<0 x=2-1",
    ]


def test_integer_locations_null_defaults_and_single_exclusion():
    source = database(
        inst(
            match="-1",
            variables=[
                {"name": "bit", "location": 1, "sign_extend": None, "left_shift": None, "not": 1},
            ],
        )
    )
    assert row_text(source) == ["test common 1<0 bit!1=1"]


def test_no_fixed_bits_and_declared_variable_order_are_preserved():
    source = database(
        inst(
            match="----",
            variables=[
                {"name": "low", "location": "1-0"},
                {"name": "high", "location": "3-2"},
            ],
        )
    )
    assert row_text(source) == ["test common  low=1-0 high=3-2"]


def test_equal_textual_columns_ignore_branch_source_metadata():
    source = database(
        {
            "name": "test",
            "encoding": {
                "RV32": {"match": "1-0", "variables": [{"name": "x", "location": 1}]},
                "RV64": {"match": "1-0", "variables": [{"name": "x", "location": "1"}]},
            },
        }
    )
    assert row_text(source) == ["test common 1<2|0<0 x=1"]


def test_logical_xlen_restriction_and_unsatisfiable_definition_match_legacy_base():
    source = database(
        inst("only32", definedBy={"not": {"xlen": 64}}),
        inst("neither", definedBy={"allOf": [{"xlen": 32}, {"xlen": 64}]}),
    )
    assert row_text(source) == [
        "neither common 1<3|0<0 x=2-1",
        "only32 32 1<3|0<0 x=2-1",
    ]


def test_deferred_structural_query_is_not_silently_omitted(monkeypatch):
    monkeypatch.setattr(
        ConfiguredArchitecture, "condition_presence", lambda *args: QueryPresence.DEFERRED
    )
    with pytest.raises(InstructionFieldError, match=r"definedBy.*undecidable"):
        instruction_fields(database(inst()), "test")


def test_config_selection_does_not_filter_or_pin_structural_base():
    source = database(
        inst("common"),
        inst("rv32", definedBy={"xlen": 32}),
        inst("rv64", definedBy={"xlen": 64}),
        extra={
            "param/MXLEN.yaml": {
                "name": "MXLEN",
                "kind": "parameter",
                "schema": {"type": "integer", "enum": [32, 64]},
            }
        },
    )
    configured = source.configure(
        Configuration(
            {
                "$schema": "config_schema.json#",
                "name": "only32",
                "description": "Single machine width does not restrict structural layouts",
                "kind": "architecture configuration",
                "type": "fully configured",
                "params": {"MXLEN": 32},
                "implemented_extensions": [],
            }
        )
    )
    assert render_instruction_table(configured) == render_instruction_table(source)
    assert "rv64 64 " in render_instruction_table(configured)


def test_stdout_and_file_prelude_no_directory_provenance(output_dir):
    source = database(inst())
    output = io.StringIO()
    text = generate_instruction_table(source, stdout=output)
    assert output.getvalue() == text
    assert '# "./bin/generate inst-table"\n' in text
    path = output_dir / "table.txt"
    path.write_text("old data")
    untouched = io.StringIO()
    generated = generate_instruction_table(source, output=path, stdout=untouched)
    assert path.read_bytes() == generated.encode()
    assert untouched.getvalue() == ""
    assert '# "./bin/generate inst-table -o table.txt"\n' in generated
    assert str(output_dir) not in generated
    with pytest.raises(FileNotFoundError):
        generate_instruction_table(source, output=output_dir / "absent/table.txt")


def test_failure_does_not_write_partial_artifact(output_dir):
    source = database(inst(), inst("broken", variables=[]))
    path = output_dir / "table.txt"
    path.write_text("keep")
    output = io.StringIO()
    with pytest.raises(InstructionFieldError):
        generate_instruction_table(source, output=path, stdout=output)
    assert path.read_text() == "keep"
    assert output.getvalue() == ""


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"match": "oops"}, "match"),
        ({"match": ""}, "match"),
        ({"silent": True}, "unsupported encoding field"),
        ({"variables": {}}, "sequence"),
        ({"variables": [{"name": "x", "location": "1-2"}]}, "descend"),
        ({"variables": [{"name": "x", "location": "4"}]}, "fit"),
        ({"variables": [{"name": "x", "location": "2|2"}]}, "repeats"),
        ({"variables": [{"name": "x", "location": "2:1"}]}, "location"),
        ({"variables": [{"name": "x", "location": True}]}, "location"),
        ({"variables": [{"name": "x", "location": "2-1", "sign_extend": 1}]}, "Boolean"),
        ({"variables": [{"name": "x", "location": "2-1", "left_shift": -1}]}, "nonnegative"),
        ({"variables": [{"name": "x", "location": "2-1", "left_shift": True}]}, "nonnegative"),
        ({"variables": [{"name": "x", "location": "2-1", "not": [True]}]}, "integers"),
        ({"variables": [{"name": "x", "location": "2-1", "unknown": 0}]}, "unsupported"),
        ({"variables": [{"name": "x", "location": "3-1"}]}, "overlaps"),
        ({"variables": []}, "without"),
        ({"variables": [{"name": "", "location": "2-1"}]}, "identifier"),
    ],
)
def test_source_aware_errors_reject_unknown_and_malformed_fields(change, message):
    item = inst()
    item["encoding"].update(change)
    with pytest.raises(InstructionFieldError, match=message) as error:
        instruction_fields(database(item), "test")
    assert "inst/test.yaml#/encoding" in str(error.value)


def test_absent_branch_is_still_validated():
    source = database(
        {
            "name": "test",
            "definedBy": {"xlen": 32},
            "encoding": {
                "RV32": {"match": "1", "variables": []},
                "RV64": {"match": "1", "variables": [], "oops": True},
            },
        }
    )
    with pytest.raises(InstructionFieldError, match="RV64/oops"):
        instruction_fields(source, "test")


def test_different_instruction_directory_does_not_change_order_or_bytes():
    first = inst("a")
    second = inst("z")
    expected = render_instruction_table(database(first, second))
    moved = ResolvedDatabase(
        {
            "inst/Z/a.yaml": {"kind": "instruction", **first},
            "inst/A/z.yaml": {"kind": "instruction", **second},
        }
    )
    assert render_instruction_table(moved) == expected


def test_captured_error_source_points_to_original_scalar(output_dir):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "test.yaml").write_text(
        "kind: instruction\nname: test\nencoding:\n  match: 1--0\n"
        "  variables:\n    - name: x\n      location: 2-1\n      left_shift: -1\n"
    )
    source = Database.from_path(output_dir / "isa").resolve()
    shutil.rmtree(output_dir / "isa")
    with pytest.raises(InstructionFieldError) as error:
        instruction_fields(source, "test")
    assert "inst/test.yaml:8:19#/encoding/variables/0/left_shift" in str(error.value)


def test_captured_source_metadata_after_input_is_removed(output_dir):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "test.yaml").write_text(
        "kind: instruction\nname: test\nencoding:\n  match: 1--0\n"
        "  variables:\n    - name: x\n      location: 2-1\n"
    )
    source = Database.from_path(output_dir / "isa").resolve()
    shutil.rmtree(output_dir / "isa")
    descriptor = instruction_fields(source, "test")
    assert descriptor.encoding(32).variables[0].source.start_line == 6
    assert row_text(source) == ["test common 1<3|0<0 x=2-1"]


def test_genuine_legacy_mock_fixture_preserves_supplied_opcode_order():
    source = database(inst("one"), inst("two"), inst("three"))
    builder = InstructionFieldBuilder(source)

    def describe(name, fixed, variables, xlens):
        record = builder.database.instruction(name)
        opcodes = tuple(
            OpcodeField(bits, BitRange(offset + len(bits) - 1, offset)) for bits, offset in fixed
        )
        fields = tuple(DecodeField(*args) for args in variables)
        return InstructionFields(
            record, None, tuple(EncodingFields(xlen, "", opcodes, fields) for xlen in xlens)
        )

    first = describe(
        "one",
        [("0100000", 31), ("111", 14), ("0110011", 6)],
        [
            ("xs2", "24-20", ()),
            ("xs1", "19-15", ()),
            ("xd", "11-7", ()),
        ],
        (32, 64),
    )
    second = describe(
        "two",
        [("1100011", 6), ("101", 14)],
        [
            ("imm", "31|7|30-25|11-8", (), True, 1),
            ("xs2", "24-20", ()),
            ("xs1", "19-15", ()),
        ],
        (32,),
    )
    third = describe(
        "three",
        [("1100011", 6), ("101", 14)],
        [
            ("imm", "31-25|11-7", ()),
            ("xs2", "24-20", (), False, 0, tuple(range(1, 32, 2))),
            ("xs1", "19-15", ()),
        ],
        (64,),
    )
    actual = render_instruction_table_rows(
        instruction_table_rows([third, second, first]),
        file_name="test_table.txt",
    )
    assert actual.encode() == (FIXTURES / "legacy-unit.txt").read_bytes()
