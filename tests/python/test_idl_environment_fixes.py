# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Focused architecture-adapter regressions independent of compiler owner tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from udb import Configuration, Database, ResolvedDatabase
from udb.idl import value_bounds
from udb.idl.ast import FunctionCallExpression
from udb.idl.errors import IdlInternalError, IdlValueUnknown
from udb.idl.parser import parse_expression
from udb.idl.types import BOOL_TYPE, FunctionType, TypeKind
from udb.idl_environment import (
    _CsrFieldAdapter,
    condition_symbol_table,
    idl_environment,
)
from udb.source import SourceText


def _extension(name, *, requirements=None):
    return {
        "kind": "extension",
        "name": name,
        "versions": [
            {"version": "1.0.0", "state": "ratified"},
            {"version": "2.0.0", "state": "ratified"},
        ],
        **({"requirements": requirements} if requirements is not None else {}),
    }


def _parameter(name, schema):
    return {"kind": "parameter", "name": name, "definedBy": True, "schema": schema}


def _database(extra=None):
    return ResolvedDatabase(
        {
            "ext/A.yaml": _extension("A"),
            "ext/B.yaml": _extension("B"),
            "param/MXLEN.yaml": _parameter("MXLEN", {"type": "integer", "enum": [32, 64]}),
            "param/FLAGS.yaml": _parameter(
                "FLAGS", {"type": "array", "items": {"type": "boolean"}, "maxItems": 8}
            ),
            **(extra or {}),
        }
    )


def _configuration(kind="fully configured", **changes):
    data = {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": kind,
        "name": "adapter-regression",
        "description": "adapter regression",
        "params": {"MXLEN": 32},
    }
    data["implemented_extensions" if kind == "fully configured" else "mandatory_extensions"] = (
        [{"name": "A", "version": "1.0.0"}] if kind == "fully configured" else []
    )
    data.update(changes)
    data["params"] = {"FLAGS": [], **data["params"]}
    return Configuration(data)


def test_condition_bootstrap_is_symbolic_and_does_not_construct_solver(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("condition bootstrap called a configured architecture or solver")

    monkeypatch.setattr("udb.solver.ConditionSolver.__init__", forbidden)
    monkeypatch.setattr("udb.architecture.ConfiguredArchitecture.condition_presence", forbidden)
    database = _database()
    first = condition_symbol_table(database)
    second = condition_symbol_table(database)
    assert first.mxlen is None
    assert first.csr_hash == {}
    assert first.get("X") is None
    assert first.get("FLEN") is None
    assert first.get("MXLEN").value is None
    assert first.get("FLAGS").value is None
    assert first.get("FLAGS").type.kind is TypeKind.ARRAY
    assert first.get("MXLEN") is not second.get("MXLEN")
    first.get("MXLEN").value = 32
    assert second.get("MXLEN").value is None
    assert first.builtin_funcs.implemented("A") is None
    assert first.builtin_funcs.implemented_version("A", "= 1.0.0") is None
    assert first.builtin_funcs.implemented_csr(0x100) is None


@pytest.mark.parametrize(
    "name,arity", [("implemented?", 1), ("implemented_version?", 2), ("implemented_csr?", 1)]
)
def test_condition_bootstrap_registers_normal_function_type_signatures(name, arity):
    symtab = condition_symbol_table(_database())
    function = symtab.get(name)
    assert isinstance(function, FunctionType)
    assert function.func_def_ast.num_args() == arity
    args = {
        "implemented?": "ExtensionName::A",
        "implemented_version?": 'ExtensionName::A, "= 1.0.0"',
        "implemented_csr?": "0x100",
    }
    expression = parse_expression(f"{name}({args[name]})")
    assert function.return_type(expression.children, expression, symtab) is BOOL_TYPE
    argument_type = function.argument_type(0, expression.children, symtab, expression)
    if name == "implemented_csr?":
        assert argument_type.width == 12
    else:
        assert argument_type.enum_class is symtab.get("ExtensionName")
    expression.type_check(symtab)
    assert expression.type(symtab).kind is BOOL_TYPE.kind
    with pytest.raises(IdlValueUnknown):
        expression.value(symtab)


def test_condition_bootstrap_has_actual_xlen_signature_without_execution_state():
    table = condition_symbol_table(_database())
    function = table.get("xlen")
    assert isinstance(function, FunctionType)
    assert function.is_builtin
    assert function.num_args == 0
    assert parse_expression("xlen()").type(table).width == 8
    expression = parse_expression("xlen() == MXLEN")
    expression.type_check(table)
    with pytest.raises(IdlValueUnknown):
        parse_expression("xlen()").value(table)
    assert table.get("__effective_xlen") is None


def test_bounds_use_normal_call_value_when_compiler_semantics_are_available(monkeypatch):
    monkeypatch.setattr(FunctionCallExpression, "value", lambda node, symtab: False)
    table = condition_symbol_table(_database())
    expression = parse_expression("implemented?(ExtensionName::A) ? 128 : 4")
    assert value_bounds.max_value(expression, table) == 4


def test_bootstrap_reads_genuine_encoding_constant_but_does_not_specialize_other_globals():
    source = SourceText(
        "isa/globals.isa",
        "%version: 1.0\nU32 INSTR_ENC_SIZE = 16 `+ 24;\nBits<MXLEN> UNDEFINED_LEGAL;\n",
        "overlay[0]",
    )
    database = ResolvedDatabase(_database().documents, idl_sources={"isa/globals.isa": source})
    symtab = condition_symbol_table(database)
    assert symtab.get("INSTR_ENC_SIZE").value == 40
    assert symtab.get("INSTR_ENC_SIZE").type.width == 32
    assert symtab.get("INSTR_ENC_SIZE").type.is_const
    assert symtab.get("UNDEFINED_LEGAL") is None
    assert symtab.get("MXLEN").value is None
    assert condition_symbol_table(_database()).get("INSTR_ENC_SIZE") is None


def test_real_bootstrap_has_genuine_encoding_size_and_resource_safe_symbolic_arrays(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    database = Database.from_path(
        root / "spec/std/isa", schemas_path=root / "spec/schemas"
    ).resolve()

    def forbidden(*args, **kwargs):
        raise AssertionError("condition bootstrap called a solver")

    monkeypatch.setattr("udb.solver.ConditionSolver.__init__", forbidden)
    symtab = condition_symbol_table(database)
    assert symtab.get("INSTR_ENC_SIZE").value == 32
    assert symtab.get("HPM_EVENTS").value is None
    assert symtab.get("HPM_EVENTS").type.kind is TypeKind.ARRAY
    assert symtab.get("FLEN") is None


def _csr(name, condition=True, *, address=0x100, length="XLEN", fields=None):
    return {
        "kind": "csr",
        "name": name,
        "definedBy": condition,
        "address": address,
        "priv_mode": "M",
        "length": length,
        "fields": fields or {},
    }


def _adapted_csrs(database, configuration=None):
    architecture = database.configure(configuration or _configuration())
    environment = idl_environment(architecture)
    return architecture, environment, {csr.name: csr for csr in environment.csrs}


def test_fields_use_parent_and_own_presence_and_unpinned_bases():
    own = {"extension": {"name": "B"}}
    database = _database(
        {
            "csr/parent.yaml": _csr(
                "parent",
                {"extension": {"name": "A"}},
                fields={
                    "COMMON": {"location": 0},
                    "ABSENT": {"location": 1, "definedBy": own},
                    "ONLY64": {"location": 63, "definedBy": {"xlen": 64}},
                },
            ),
            "csr/absent_parent.yaml": _csr(
                "absent_parent",
                own,
                fields={
                    "INHERITED": {"location": 0},
                    "OWN_TRUE": {"location": 1, "definedBy": True},
                },
            ),
            "csr/inherited64.yaml": _csr(
                "inherited64",
                {"xlen": 64},
                fields={
                    "INHERITED": {"location": 63},
                },
            ),
        }
    )
    _, _, csrs = _adapted_csrs(database)
    fields = {field.name: field for field in csrs["parent"].fields}
    assert fields["COMMON"].exists
    assert fields["COMMON"].defined_in_all_bases
    assert not fields["COMMON"].base32_only  # config MXLEN=32 is not an intrinsic base
    assert not fields["ABSENT"].exists
    assert not fields["ONLY64"].exists
    assert fields["ONLY64"].base64_only
    assert not fields["ONLY64"].defined_in_base32
    assert fields["ONLY64"].defined_in_base64
    assert all(not field.exists for field in csrs["absent_parent"].fields)
    assert csrs["inherited64"]._base == 64
    assert csrs["inherited64"].fields[0].base64_only


def test_partial_field_existence_means_possible_not_necessarily_mandatory():
    database = _database(
        {
            "csr/optional.yaml": _csr(
                "optional",
                {"extension": {"name": "A"}},
                fields={
                    "FIELD": {"location": 0, "definedBy": {"extension": {"name": "B"}}},
                },
            )
        }
    )
    _, _, csrs = _adapted_csrs(database, _configuration("partially configured"))
    assert csrs["optional"].fields[0].exists


def test_base_inference_includes_structural_extension_requirements():
    database = _database(
        {
            "ext/A.yaml": _extension("A", requirements={"xlen": 64}),
            "csr/restricted.yaml": _csr(
                "restricted",
                {"extension": {"name": "A"}},
                fields={
                    "FIELD": {"location": 63},
                },
            ),
        }
    )
    _, _, csrs = _adapted_csrs(database, _configuration("partially configured"))
    assert csrs["restricted"]._base == 64
    assert csrs["restricted"].fields[0].base64_only
    assert not csrs["restricted"].fields[0].exists


@pytest.mark.parametrize("mxlen", [32, 64])
def test_xlen_maximum_follows_possible_machine_width(mxlen):
    database = _database({"csr/c.yaml": _csr("c")})
    _, _, csrs = _adapted_csrs(database, _configuration(params={"MXLEN": mxlen}))
    assert csrs["c"].max_length == mxlen


def test_xlen_maximum_uses_supervisor_mode_when_machine_mode_is_absent():
    database = _database(
        {
            "ext/Sm.yaml": _extension("Sm"),
            "ext/S.yaml": _extension("S"),
            "param/SXLEN.yaml": _parameter(
                "SXLEN",
                {
                    "type": "array",
                    "items": {"type": "integer", "enum": [32, 64]},
                    "maxItems": 2,
                },
            ),
            "csr/c.yaml": _csr("c"),
        }
    )
    _, _, csrs = _adapted_csrs(
        database,
        _configuration(
            params={"MXLEN": 64, "SXLEN": [32]},
            implemented_extensions=[{"name": "S", "version": "1.0.0"}],
        ),
    )
    assert csrs["c"].max_length == 32


def test_csr_address_presence_is_a_disjunction_not_last_definition():
    database = _database(
        {
            "csr/a.yaml": _csr("a", {"extension": {"name": "A"}}),
            "csr/z.yaml": _csr("z", {"extension": {"name": "B"}}),
        }
    )
    _, env, _ = _adapted_csrs(database)
    assert env.builtin_funcs.implemented_csr(0x100) is True
    assert env.builtin_funcs.implemented_csr(0xFFF) is False


def test_csr_address_disjunction_can_be_mandatory_when_each_record_is_optional():
    condition = {"extension": {"name": "A"}}
    database = _database(
        {
            "csr/a.yaml": _csr("a", condition),
            "csr/z.yaml": _csr("z", {"not": condition}),
        }
    )
    _, env, _ = _adapted_csrs(database, _configuration("partially configured"))
    assert env.builtin_funcs.implemented_csr(0x100) is True
    assert env.builtin_funcs.implemented_csr(0xFFF) is False


def test_version_prohibition_does_not_invent_extension_absence():
    _, env, _ = _adapted_csrs(
        _database(),
        _configuration(
            "partially configured",
            prohibited_extensions=[{"name": "A", "version": "= 1.0.0"}],
        ),
    )
    assert env.builtin_funcs.implemented("A") is None
    assert env.builtin_funcs.implemented_version("A", "= 2.0.0") is None
    assert env.builtin_funcs.implemented_version("A", "= 1.0.0") is False
    assert env.builtin_funcs.implemented_version("A", "= 3.0.0") is False


def test_version_presence_accounts_for_solver_inferred_mandatory_choices():
    database = _database(
        {
            "ext/A.yaml": _extension("A", requirements={"extension": {"name": "B"}}),
        }
    )
    _, env, _ = _adapted_csrs(database)
    # In a partial config, A's requirement makes B mandatory even when not listed.
    partial = _configuration(
        "partially configured",
        mandatory_extensions=[{"name": "A", "version": "= 1.0.0"}],
    )
    _, env, _ = _adapted_csrs(database, partial)
    assert env.builtin_funcs.implemented("B") is True


def test_location_requires_valid_explicit_base_but_width_retains_nil_default():
    field = _CsrFieldAdapter("FIELD", {"location_rv32": "3-0", "location_rv64": "11-4"})
    with pytest.raises(ValueError, match="effective XLEN"):
        field.location()
    with pytest.raises(ValueError, match="effective XLEN"):
        field.location(128)
    assert field.location(32) == range(4)
    assert field.location(64) == range(4, 12)
    assert field.width(None) == 4
    assert field.width(64) == 8
    common = _CsrFieldAdapter("COMMON", {"location": 5})
    assert common.location() == common.location(32) == common.location(64) == range(5, 6)


def test_structural_csr_values_are_exact_and_dynamic_types_require_genuine_enum_metadata():
    database = _database(
        {
            "csr/constant.yaml": _csr(
                "constant",
                fields={
                    "FIELD": {"location": "4-1", "type": "RO", "reset_value": 3},
                },
            ),
            "csr/dynamic.yaml": _csr(
                "dynamic",
                fields={
                    "FIELD": {
                        "location": 0,
                        "type()": "return CsrFieldType::RO;",
                        "reset_value()": "return 1;",
                    },
                },
            ),
        }
    )
    _, _, csrs = _adapted_csrs(database)
    assert csrs["constant"].value == 6
    field = csrs["dynamic"].fields[0]
    with pytest.raises(IdlInternalError, match="Global CsrFieldType is missing"):
        field.type(None)
    assert field.reset_value == 1


def test_compiled_csr_field_results_are_computed_once_per_environment(monkeypatch):
    database = _database(
        {
            "csr/dynamic.yaml": _csr(
                "dynamic",
                fields={"FIELD": {"location": 0, "type": "RO", "reset_value()": "return 1;"}},
            ),
        }
    )
    _, _, csrs = _adapted_csrs(database)
    compiler = csrs["dynamic"]._bases.compiler
    calls = []
    original = compiler.compile_field

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(compiler, "compile_field", counting)
    assert csrs["dynamic"].fields[0].reset_value == 1
    assert csrs["dynamic"].fields[0].reset_value == 1
    assert calls == [("dynamic", "FIELD", "reset_value()")]


def _real_architecture(name):
    root = Path(__file__).resolve().parents[2]
    configuration = Configuration.from_file(root / "cfgs" / f"{name}.yaml")
    overlays = [root / "spec/custom/isa" / configuration.overlay] if configuration.overlay else []
    return (
        Database.from_path(root / "spec/std/isa", schemas_path=root / "spec/schemas")
        .resolve(overlays=overlays)
        .configure(configuration)
    )


def _csr_semantics(environment):
    csrs = {csr.name: csr for csr in environment.csrs}
    samples = {
        "mstatush": [],
        "scontext": [],
        "tselect": [],
        "mstatus": ["SXL", "MIE"],
        "satp": ["PPN"],
    }
    result = {}
    for csr_name, names in samples.items():
        csr = csrs[csr_name]
        fields = {}
        for field in csr.fields:
            if field.name not in names:
                continue
            try:
                field.location()
                requires_base = False
            except ValueError:
                requires_base = True
            bases = [base for base in (32, 64) if field.defined_in_base(base)]
            fields[field.name] = {
                "exists": field.exists,
                "base32": field.defined_in_base32,
                "base64": field.defined_in_base64,
                "all_bases": field.defined_in_all_bases,
                "widths": {str(base): field.width(base) for base in bases},
                "locations": {str(base): list(field.location(base)) for base in bases},
                "location_requires_base": requires_base,
            }
        result[csr_name] = {
            "base": csr._base,
            "length": csr.length(),
            "length32": csr.length(32),
            "length64": csr.length(64),
            "max_length": csr.max_length,
            "dynamic": csr.dynamic_length(),
            "fields": fields,
        }
    return result


@pytest.mark.parametrize("name", ["_", "rv32", "rv64", "qc_iu"])
def test_real_csr_structural_regressions(name):
    env = idl_environment(_real_architecture(name))
    semantics = _csr_semantics(env)
    assert semantics["mstatush"]["base"] == 32
    assert semantics["mstatus"]["fields"]["SXL"]["base32"] is False
    assert semantics["mstatus"]["fields"]["SXL"]["base64"] is True
    assert semantics["satp"]["fields"]["PPN"]["location_requires_base"] is True
    if name in ("rv32", "qc_iu"):
        assert semantics["scontext"]["max_length"] == 32
        assert semantics["tselect"]["max_length"] == 32
        assert semantics["mstatus"]["fields"]["SXL"]["exists"] is False
    if name == "rv64":
        assert semantics["tselect"]["dynamic"] is False


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
@pytest.mark.parametrize("name", ["_", "rv32", "rv64", "qc_iu"])
def test_relevant_csr_semantics_match_actual_ruby_methods(name):
    root = Path(__file__).resolve().parents[2]
    output = subprocess.run(
        [
            "mise",
            "exec",
            "--",
            "bundle",
            "exec",
            "ruby",
            str(Path(__file__).with_name("ruby_idl_environment_oracle.rb")),
            name,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    expected = json.loads(output.stdout)["csr_semantics"]
    actual = _csr_semantics(idl_environment(_real_architecture(name)))
    assert actual == expected
