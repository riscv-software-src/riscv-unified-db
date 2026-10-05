# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from udb import (
    ArchitectureCheckStatus,
    ArchitectureError,
    Configuration,
    Database,
    OverlapKind,
    QueryPresence,
    ResolvedDatabase,
)
from udb.encoding import instruction_encodings

ROOT = Path(__file__).parents[2]


def extension(name, *, requirements=None):
    data = {
        "kind": "extension",
        "name": name,
        "versions": [{"version": "1.0.0", "state": "ratified"}],
    }
    if requirements is not None:
        data["requirements"] = requirements
    return data


def parameter(name, defined_by, schema, *, requirements=None):
    data = {
        "kind": "parameter",
        "name": name,
        "definedBy": defined_by,
        "schema": schema,
    }
    if requirements is not None:
        data["requirements"] = requirements
    return data


def instruction(name, defined_by, match=None, **extra):
    data = {"kind": "instruction", "name": name, "definedBy": defined_by, **extra}
    if match is not None:
        data["encoding"] = {"match": match}
    return data


def csr(name, defined_by, **extra):
    return {"kind": "csr", "name": name, "definedBy": defined_by, **extra}


@pytest.fixture(scope="module")
def database():
    ext = lambda name: {"extension": {"name": name}}
    documents = {
        "ext/A.yaml": extension("A"),
        "ext/B.yaml": extension("B", requirements=ext("A")),
        "ext/C.yaml": extension("C", requirements={"if": ext("A"), "then": ext("B")}),
        "ext/D.yaml": extension("D", requirements={"idl()": "-> P > 0;"}),
        "param/MXLEN.yaml": parameter("MXLEN", True, {"type": "integer", "enum": [32, 64]}),
        "param/P.yaml": parameter(
            "P",
            ext("B"),
            {"type": "integer", "minimum": 1, "maximum": 4},
            requirements={"param": {"name": "P", "greaterThan": 0}},
        ),
        "param/Q.yaml": parameter("Q", ext("C"), {"type": "boolean"}),
        "inst/i_a.yaml": instruction(
            "i_a", ext("A"), "0000------------0011", **{"operation()": "Bits<8> value = 1;"}
        ),
        "inst/i_b.yaml": instruction("i_b", ext("B"), "0001------------0011"),
        "inst/i_32.yaml": instruction(
            "i_32", {"allOf": [ext("B"), {"xlen": 32}]}, "0010------------0011"
        ),
        "csr/c_b.yaml": csr(
            "c_b",
            ext("B"),
            address=0x100,
            length=32,
            **{"sw_read()": "return 3;"},
            fields={
                "INHERITED": {"location": 0},
                "ONLY_A": {"location": 1, "definedBy": ext("A")},
                "ONLY_32": {"location": 2, "definedBy": {"xlen": 32}},
            },
        ),
        "exception_code/E.yaml": {
            "kind": "exception_code",
            "name": "E",
            "num": 1,
            "definedBy": ext("B"),
        },
        "interrupt_code/N.yaml": {
            "kind": "interrupt_code",
            "name": "N",
            "num": 1,
            "definedBy": ext("C"),
        },
        "profile/P1.yaml": {
            "kind": "profile",
            "name": "P1",
            "base": 32,
            "extensions": {"B": {"presence": "mandatory", "version": ">= 1"}},
            "requirements": True,
        },
        "manual/M.yaml": {"kind": "manual", "name": "M"},
        "manual_version/M/V.yaml": {
            "kind": "manual version",
            "name": "V",
            "manual": {"$ref": "manual/M.yaml#"},
            "volumes": [{"extensions": [{"name": "A", "version": "1.0.0"}]}],
        },
    }
    return ResolvedDatabase(documents)


def config(kind="partially configured", **changes):
    data = {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": kind,
        "name": "test",
        "description": "test",
    }
    if kind == "partially configured":
        data["mandatory_extensions"] = []
    data.update(changes)
    return Configuration(data)


def test_generic_repository_configurations(database):
    real = Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()
    expected = {
        "_": QueryPresence.POSSIBLE,
        "rv32": QueryPresence.MANDATORY,
        "rv64": QueryPresence.MANDATORY,
    }
    for name, add_presence in expected.items():
        architecture = real.configure(Configuration.from_file(ROOT / "cfgs" / f"{name}.yaml"))
        assert architecture.check().status is ArchitectureCheckStatus.VALID
        assert architecture.object_presence(real.instruction("add")) is add_presence


def test_full_config_checks_exact_set_domains_and_defined_parameters(database):
    valid = database.configure(
        config(
            "fully configured",
            implemented_extensions=[
                {"name": "A", "version": "1.0.0"},
                {"name": "B", "version": "1.0.0"},
            ],
            params={"MXLEN": 32, "P": 2},
        )
    )
    assert valid.check().status is ArchitectureCheckStatus.VALID
    assert valid.extension_presence("A") is QueryPresence.MANDATORY
    assert valid.extension_presence("C") is QueryPresence.ABSENT
    assert valid.validate_parameter_value("P", 4)
    assert not valid.validate_parameter_value("P", 5)

    bad_domain = database.configure(
        config(
            "fully configured",
            implemented_extensions=[{"name": "A", "version": "1.0.0"}],
            params={"MXLEN": 32, "P": 9},
        )
    )
    assert bad_domain.check().status is ArchitectureCheckStatus.UNSAT
    assert any(item.code == "parameter-domain" for item in bad_domain.check().diagnostics)


def test_implication_closure_conditional_requirements_and_unsat(database):
    required = database.configure(config(mandatory_extensions=[{"name": "B", "version": ">= 1"}]))
    assert required.extension_presence("A") is QueryPresence.MANDATORY
    assert required.implied_extensions("B")[0].name == "A"

    conditional = database.configure(
        config(
            mandatory_extensions=[
                {"name": "A", "version": ">= 1"},
                {"name": "C", "version": ">= 1"},
            ]
        )
    )
    assert conditional.extension_presence("B") is QueryPresence.MANDATORY

    impossible = database.configure(
        config(
            mandatory_extensions=[{"name": "B", "version": ">= 1"}],
            prohibited_extensions=[{"name": "A", "version": ">= 0"}],
        )
    )
    assert impossible.check().status is ArchitectureCheckStatus.UNSAT
    with pytest.raises(ArchitectureError):
        impossible.extension_presence("A")


def test_additional_extensions_false_and_compatibility(database):
    closed = database.configure(
        config(
            mandatory_extensions=[{"name": "A", "version": ">= 1"}],
            additional_extensions=False,
        )
    )
    assert closed.extension_presence("A") is QueryPresence.MANDATORY
    assert closed.extension_presence("B") is QueryPresence.ABSENT

    needs_b = config(mandatory_extensions=[{"name": "B", "version": ">= 1"}])
    assert closed.compatible_with(needs_b).status is ArchitectureCheckStatus.UNSAT


def test_parameters_and_object_queries(database):
    architecture = database.configure(
        config(mandatory_extensions=[{"name": "B", "version": ">= 1"}], params={"P": 3})
    )
    assert [item.name for item in architecture.parameters_with_values] == ["P"]
    assert "MXLEN" in {item.name for item in architecture.parameters_without_values}
    assert "Q" in {item.name for item in architecture.parameters_without_values}
    assert architecture.object_presence(database.instruction("i_a")) is QueryPresence.MANDATORY
    assert architecture.object_presence(database.instruction("i_b")) is QueryPresence.MANDATORY
    assert architecture.object_presence(database.instruction("i_32")) is QueryPresence.POSSIBLE
    assert architecture.object_presence(database.csr("c_b")) is QueryPresence.MANDATORY
    fields = {
        item.name: architecture.object_presence(item) for item in architecture.csr_fields("c_b")
    }
    assert fields == {
        "INHERITED": QueryPresence.MANDATORY,
        "ONLY_A": QueryPresence.MANDATORY,
        "ONLY_32": QueryPresence.POSSIBLE,
    }
    assert [item.name for item in architecture.possible_exception_codes] == ["E"]
    assert [item.name for item in architecture.possible_interrupt_codes] == ["N"]
    assert [
        item.name for item in architecture.direct_objects_for_extension("instruction", "A")
    ] == ["i_a"]
    assert {
        item.name for item in architecture.implied_objects_for_extension("instruction", "B")
    } == {
        "i_a",
        "i_b",
    }


def test_idl_requirements_are_compiled(database):
    architecture = database.configure(
        config(mandatory_extensions=[{"name": "D", "version": ">= 1"}])
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.VALID
    assert not any(item.code == "idl-deferred" for item in result.diagnostics)
    assert all(not condition.has_unresolved for condition, _ in architecture._constraints)
    operation = architecture.instruction_operation("i_a", effective_xlen=32)
    assert operation.effective_xlen == 32
    assert operation.source.label == "inst/i_a.yaml#/operation()"
    assert "Bits<8> value" in operation.ast.to_idl()
    behavior = architecture.csr_behavior("c_b", effective_xlen=32)
    assert behavior.source.label == "csr/c_b.yaml#/sw_read()"
    assert behavior.return_value() == 3


def test_profile_and_manual_membership(database):
    architecture = database.configure(config())
    assert architecture.profile_presence("P1") is QueryPresence.POSSIBLE
    assert [str(item) for item in architecture.manual_version_extensions("V")] == ["A@1.0.0"]
    assert [item.name for item in architecture.manual_versions_for_extension("A")] == ["V"]


def encoding_database():
    ext_a = {"extension": {"name": "A"}}
    not_a = {"not": ext_a}
    match = "0" * 28 + "0011"
    documents = {
        "ext/A.yaml": extension("A"),
        "param/MXLEN.yaml": parameter("MXLEN", True, {"type": "integer", "enum": [32, 64]}),
        "inst/base.yaml": instruction(
            "base",
            ext_a,
            match,
            hints=({"$ref": "inst/hint.yaml#"},),
        ),
        "inst/conflict.yaml": instruction("conflict", ext_a, match),
        "inst/hint.yaml": instruction("hint", ext_a, match),
        "inst/alias.yaml": instruction("alias", not_a, match),
        "inst/excluded.yaml": instruction(
            "excluded",
            ext_a,
            "-" * 28 + "0011",
        ),
        "inst/exact_zero.yaml": instruction("exact_zero", ext_a, match),
        "inst/split.yaml": instruction("split", ext_a, "-" * 28 + "0011"),
        "inst/shifted.yaml": instruction("shifted", ext_a, "-" * 28 + "0011"),
        "inst/fmt.yaml": instruction(
            "fmt",
            ext_a,
            format={
                "type": {"$ref": "inst_type/R.yaml#"},
                "subtype": {"$ref": "inst_subtype/R/R-x.yaml#"},
                "opcodes": {
                    "opcode": {
                        "location": "6-0",
                        "display_name": "OP",
                        "value": {"$ref": "inst_opcode/OP.yaml#"},
                    },
                    "upper": {"location": "31-7", "display_name": "upper", "value": 0},
                },
            },
        ),
        "inst_type/R.yaml": {"kind": "instruction_type", "name": "R", "length": 32},
        "inst_subtype/R/R-x.yaml": {"kind": "instruction_subtype", "name": "R-x"},
        "inst_opcode/OP.yaml": {
            "kind": "instruction_opcode",
            "name": "OP",
            "data": {"value": 0b0011},
        },
    }
    documents["inst/excluded.yaml"]["encoding"]["variables"] = [
        {"name": "upper", "location": "31-4", "not": 0}
    ]
    documents["inst/split.yaml"]["encoding"]["variables"] = [
        {"name": "split", "location": "7|5-4", "not": 1}
    ]
    documents["inst/shifted.yaml"]["encoding"]["variables"] = [
        {"name": "shifted", "location": "7-4", "left_shift": 2, "not": 4}
    ]
    return ResolvedDatabase(documents)


def test_encoding_exclusions_hints_aliases_and_format():
    database = encoding_database()
    architecture = database.configure(config())
    fmt = instruction_encodings(architecture, database.instruction("fmt"))
    assert fmt[0].length == 32
    assert fmt[0].value == 0b0011
    assert instruction_encodings(architecture, database.instruction("split"))[0].exclusions == (
        (0b10110000, 0b00010000),
    )
    assert instruction_encodings(architecture, database.instruction("shifted"))[0].exclusions == (
        (0b11110000, 0b00010000),
    )

    names = {
        (item.left.name, item.right.name, item.kind)
        for item in architecture.encoding_overlaps(database.instructions)
    }
    assert ("base", "hint", OverlapKind.CONFLICT) not in names
    assert ("base", "conflict", OverlapKind.CONFLICT) in names
    assert any(
        {left, right} == {"base", "alias"} and kind is OverlapKind.ALIAS
        for left, right, kind in names
    )
    assert not any({left, right} == {"excluded", "exact_zero"} for left, right, _ in names)
    assert ("base", "fmt", OverlapKind.CONFLICT) in names


def test_csr_direct_virtual_and_indirect_conflict_keys(database):
    ext_a = {"extension": {"name": "A"}}
    records = ResolvedDatabase(
        {
            "ext/A.yaml": extension("A"),
            "param/MXLEN.yaml": parameter("MXLEN", True, {"type": "integer", "enum": [32, 64]}),
            "csr/one.yaml": csr(
                "one",
                ext_a,
                address=0x100,
                virtual_address=0x200,
                indirect_address=7,
                indirect_slot=1,
                priv_mode="M",
            ),
            "csr/two.yaml": csr(
                "two",
                ext_a,
                address=0x100,
                virtual_address=0x200,
                indirect_address=7,
                indirect_slot=1,
                priv_mode="M",
            ),
            "csr/other_mode.yaml": csr(
                "other_mode", ext_a, indirect_address=7, indirect_slot=1, priv_mode="S"
            ),
        }
    )
    architecture = records.configure(config())
    overlaps = architecture.csr_address_overlaps(records.csrs)
    pair = [item for item in overlaps if {item.left.name, item.right.name} == {"one", "two"}]
    assert {(item.key.space, item.xlen) for item in pair} == {
        ("direct", 32),
        ("direct", 64),
        ("virtual", 32),
        ("virtual", 64),
        ("indirect", 32),
        ("indirect", 64),
    }
    assert not any(
        item.key.space == "indirect" and {item.left.name, item.right.name} == {"one", "other_mode"}
        for item in overlaps
    )


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
def test_generic_and_custom_mock_config_queries_match_ruby():
    names = ["_", "little_is_better", "little_is_not_better"]
    result = subprocess.run(
        [
            "bundle",
            "exec",
            "ruby",
            f"-I{ROOT / 'tools/ruby-gems/udb/lib'}",
            str(Path(__file__).with_name("ruby_architecture_oracle.rb")),
            str(ROOT),
        ],
        input=json.dumps(names),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    expected = json.loads(result.stdout)
    database = Database.from_path(
        ROOT / "tools/ruby-gems/udb/test/mock_spec/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve()
    actual = {}
    for name in names:
        architecture = database.configure(
            Configuration.from_file(ROOT / "tools/ruby-gems/udb/test/mock_cfgs" / f"{name}.yaml")
        )
        actual[name] = {
            "possible_versions": sorted(
                str(version)
                for extension in database.extensions
                for version in architecture.possible_extension_versions(extension.name)
            ),
            "params_with_value": sorted(item.name for item in architecture.parameters_with_values),
            "params_without_value": sorted(
                item.name for item in architecture.parameters_without_values
            ),
        }
    assert actual == expected
