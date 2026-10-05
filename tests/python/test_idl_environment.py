# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Tests for ``udb.idl_environment`` (the architecture-environment adapter)
and ``udb.idl_yaml_source`` (YAML->IDL source mapping).

Tests exercise the adapters' pure logic directly: schema/parameter conversion,
the structural register-width evaluator, extension-selection matching, real
configuration construction, and YAML source mapping against ``spec/`` files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from udb.configuration import Configuration
from udb.database import Database
from udb.idl import value_bounds
from udb.idl.errors import IdlInternalError, IdlSyntaxError, IdlTypeError
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.source import IdlSource
from udb.idl.symbols import BuiltinFunctionCallbacks, EnumDef, IdlEnvironment, SymbolTable, Var
from udb.idl.types import BOOL_TYPE
from udb.idl_condition_environment import add_predicate_signatures
from udb.idl_environment import (
    _param_var,
    _ParameterAdapter,
    _register_file_max_width,
    _RegisterFileAdapter,
    _SchemaAdapter,
    _selection_matches,
    idl_environment,
    symbol_table,
)
from udb.idl_yaml_source import UnsupportedYamlIdlStyle, idl_field_source
from udb.source import parse_yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# _SchemaAdapter / _ParameterAdapter
# ---------------------------------------------------------------------------


def test_schema_adapter_const_max_and_min_val() -> None:
    schema = _SchemaAdapter({"type": "integer", "const": 4})
    assert schema.max_val_known
    assert schema.max_val == 4
    assert schema.min_val_known
    assert schema.min_val == 4


def test_schema_adapter_enum_max_and_min_val() -> None:
    schema = _SchemaAdapter({"type": "integer", "enum": [1, 5, 3]})
    assert schema.max_val == 5
    assert schema.min_val == 1


def test_schema_adapter_maximum_minimum() -> None:
    schema = _SchemaAdapter({"type": "integer", "maximum": 200, "minimum": 10})
    assert schema.max_val == 200
    assert schema.min_val == 10


def test_schema_adapter_max_val_unknown_without_bound() -> None:
    schema = _SchemaAdapter({"type": "integer"})
    assert not schema.max_val_known
    assert not schema.min_val_known
    with pytest.raises(IdlInternalError):
        _ = schema.max_val


def test_schema_adapter_boolean_has_no_max_val() -> None:
    schema = _SchemaAdapter({"type": "boolean"})
    assert not schema.max_val_known
    assert not schema.min_val_known


def test_schema_adapter_array_to_idl_type() -> None:
    schema = _SchemaAdapter(
        {"type": "array", "items": {"type": "integer", "maximum": 7}, "minItems": 2, "maxItems": 2}
    )
    idl_type = schema.to_idl_type
    assert str(idl_type) == "array of Bits<3>"


class _FakeRecord:
    """Minimal ``DatabaseObject``-shaped stand-in for ``_ParameterAdapter`` tests."""

    def __init__(self, name: str, schema: dict) -> None:
        self.name = name
        self.data = {"schema": schema, "description": f"{name} description"}


def test_parameter_adapter_idl_type_is_const() -> None:
    param = _ParameterAdapter(_FakeRecord("MXLEN", {"type": "integer", "maximum": 64}))
    assert param.idl_type.is_const
    assert not param.value_known
    assert param.value is None


def test_parameter_adapter_with_value() -> None:
    param = _ParameterAdapter(_FakeRecord("MXLEN", {"type": "integer", "maximum": 64}), value=32)
    assert param.value_known
    assert param.value == 32


# ---------------------------------------------------------------------------
# udb.idl.value_bounds -- retained migration coverage
# (TestTernaryMaxMinValue)
# ---------------------------------------------------------------------------


def _bootstrap_symtab(
    *,
    mxlen: int | None = 64,
    global_vars: tuple[Var, ...] = (),
    params: tuple[_ParameterAdapter, ...] = (),
    implemented=lambda name: None,
    implemented_version=lambda name, version: None,
    implemented_csr=lambda addr: None,
) -> SymbolTable:
    env = IdlEnvironment(
        mxlen=mxlen,
        possible_xlens_cb=lambda: (mxlen,) if mxlen is not None else (32, 64),
        builtin_global_vars=global_vars,
        builtin_enums=(EnumDef("ExtensionName", (0, 1), ("Q", "D")),),
        builtin_funcs=BuiltinFunctionCallbacks(
            implemented=implemented,
            implemented_version=implemented_version,
            implemented_csr=implemented_csr,
        ),
        params=params,
        name="test/bootstrap",
    )
    symtab = SymbolTable(env)
    add_predicate_signatures(symtab)
    return symtab


def test_value_bounds_ternary_unknown_condition_explores_both_branches() -> None:
    # Ruby: `flag ? 64 : 32` where `flag` is an unvalued Boolean Var -> max=64, min=32.
    flag = Var("flag", BOOL_TYPE)
    symtab = _bootstrap_symtab(global_vars=(flag,))
    expr = parse_expression("flag ? 64 : 32")
    assert value_bounds.max_value(expr, symtab) == 64
    assert value_bounds.min_value(expr, symtab) == 32


def test_value_bounds_ternary_known_true_condition_follows_true_branch() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("true ? 32 : 64")
    assert value_bounds.max_value(expr, symtab) == 32
    assert value_bounds.min_value(expr, symtab) == 32


def test_value_bounds_ternary_known_false_condition_follows_false_branch() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("false ? 32 : 64")
    assert value_bounds.max_value(expr, symtab) == 64
    assert value_bounds.min_value(expr, symtab) == 64


def test_value_bounds_paren_expression_delegates_to_inner() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("(41)")
    assert value_bounds.max_value(expr, symtab) == 41
    assert value_bounds.min_value(expr, symtab) == 41


def test_value_bounds_id_known_value() -> None:
    param = _ParameterAdapter(_FakeRecord("MXLEN", {"type": "integer", "maximum": 64}), value=32)
    symtab = _bootstrap_symtab(global_vars=(_param_var(param),), params=(param,))
    expr = parse_expression("MXLEN")
    assert value_bounds.max_value(expr, symtab) == 32
    assert value_bounds.min_value(expr, symtab) == 32


def test_value_bounds_id_falls_back_to_param_schema() -> None:
    # No value known -> IdAst#max_value/#min_value fall back to schema.max_val/min_val.
    param = _ParameterAdapter(_FakeRecord("VLEN", {"type": "integer", "enum": [128, 65536]}))
    symtab = _bootstrap_symtab(global_vars=(_param_var(param),), params=(param,))
    expr = parse_expression("VLEN")
    assert value_bounds.max_value(expr, symtab) == 65536
    assert value_bounds.min_value(expr, symtab) == 128


def test_value_bounds_binary_expression_arithmetic_truncates_like_ruby() -> None:
    # Non-widening `+` truncates to the narrower literal-inferred width (IDL semantics,
    # not a bug): `2` and `3` each need 2 bits, so `2 + 3 == 5` truncates to 1.
    symtab = _bootstrap_symtab()
    expr = parse_expression("2 + 3")
    with pytest.warns(UserWarning, match="truncated"):
        assert value_bounds.max_value(expr, symtab) == 1
    with pytest.warns(UserWarning, match="truncated"):
        assert value_bounds.min_value(expr, symtab) == 1


def test_value_bounds_binary_expression_widening_operator() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("2 `+ 3")
    assert value_bounds.max_value(expr, symtab) == 5
    assert value_bounds.min_value(expr, symtab) == 5


def test_value_bounds_registered_builtin_predicate() -> None:
    symtab = _bootstrap_symtab(implemented=lambda name: name == "Q")
    expr = parse_expression("implemented?(ExtensionName::Q) ? 128 : 32")
    expr.type_check(symtab)
    assert value_bounds.max_value(expr, symtab) == 128
    symtab_false = _bootstrap_symtab(implemented=lambda name: False)
    assert value_bounds.max_value(expr, symtab_false) == 32


def test_value_bounds_builtin_predicate_unknown_explores_both_branches() -> None:
    symtab = _bootstrap_symtab(implemented=lambda name: None)
    expr = parse_expression("implemented?(ExtensionName::Q) ? 128 : 32")
    assert value_bounds.max_value(expr, symtab) == 128
    assert value_bounds.min_value(expr, symtab) == 32


def test_value_bounds_unsupported_operator_raises() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("5 % 2")
    with pytest.raises(IdlInternalError):
        value_bounds.max_value(expr, symtab)


def test_value_bounds_other_function_calls_raise_loudly() -> None:
    symtab = _bootstrap_symtab()
    expr = parse_expression("some_other_func(1) ? 1 : 2")
    for bound in (value_bounds.max_value, value_bounds.min_value):
        with pytest.raises(IdlTypeError, match="No symbol some_other_func"):
            bound(expr, symtab)


# ---------------------------------------------------------------------------
# _register_file_max_width against the real register files under
# spec/std/isa/register_file (F, V, X)
# ---------------------------------------------------------------------------


def _rf(name: str, register_length_body: str) -> _RegisterFileAdapter:
    record = _FakeRecord(name, {})
    record.data["register_length()"] = register_length_body
    return _RegisterFileAdapter(record)


def test_register_file_max_width_x_is_mxlen() -> None:
    mxlen_param = _ParameterAdapter(
        _FakeRecord("MXLEN", {"type": "integer", "maximum": 64}), value=64
    )
    symtab = _bootstrap_symtab(
        mxlen=64, global_vars=(_param_var(mxlen_param),), params=(mxlen_param,)
    )
    assert _register_file_max_width(_rf("X", "return MXLEN;"), symtab) == 64


def test_register_file_max_width_v_falls_back_to_vlen_schema() -> None:
    vlen_param = _ParameterAdapter(_FakeRecord("VLEN", {"type": "integer", "maximum": 0x10000}))
    symtab = _bootstrap_symtab(global_vars=(_param_var(vlen_param),), params=(vlen_param,))
    assert _register_file_max_width(_rf("V", "return VLEN;"), symtab) == 0x10000


@pytest.mark.parametrize(
    ("implemented", "expected"),
    [
        (lambda name: None, 128),  # bootstrap/unconfigured: explore both branches
        (lambda name: False, 32),  # Q and D both known-prohibited
        (lambda name: name == "Q", 128),
        (lambda name: name == "D", 64),
    ],
)
def test_register_file_max_width_f_nested_ternary(implemented, expected: int) -> None:
    symtab = _bootstrap_symtab(implemented=implemented)
    body = (
        "return implemented?(ExtensionName::Q) ? 128 : (implemented?(ExtensionName::D) ? 64 : 32);"
    )
    assert _register_file_max_width(_rf("F", body), symtab) == expected


def test_register_file_max_width_unknown_identifier_raises_type_error() -> None:
    symtab = _bootstrap_symtab()
    with pytest.raises(IdlTypeError):
        _register_file_max_width(_rf("BOGUS", "return SOME_UNKNOWN_PARAM;"), symtab)


def test_real_register_files_max_width_matches_known_values() -> None:
    root = REPOSITORY_ROOT / "spec/std/isa/register_file"
    bodies = {}
    for path in sorted(root.glob("*.yaml")):
        parsed = parse_yaml(path.read_text(), source=str(path))
        bodies[parsed.value["name"]] = parsed.value["register_length()"]

    mxlen_param = _ParameterAdapter(
        _FakeRecord("MXLEN", {"type": "integer", "maximum": 64}), value=64
    )
    vlen_param = _ParameterAdapter(_FakeRecord("VLEN", {"type": "integer", "maximum": 0x10000}))
    symtab = _bootstrap_symtab(
        mxlen=64,
        global_vars=(_param_var(mxlen_param), _param_var(vlen_param)),
        params=(mxlen_param, vlen_param),
        implemented=lambda name: None,
    )
    assert _register_file_max_width(_rf("X", bodies["X"]), symtab) == 64
    assert _register_file_max_width(_rf("F", bodies["F"]), symtab) == 128
    assert _register_file_max_width(_rf("V", bodies["V"]), symtab) == 0x10000


# ---------------------------------------------------------------------------
# idl_field_source (YAML -> IdlSource mapping)
# ---------------------------------------------------------------------------


def _corrupt_first_semicolon_line(value: str) -> tuple[str, int]:
    """Remove the first ``;`` found on some line of *value*; return (broken_text, line_index)."""
    body_lines = value.splitlines(keepends=True)
    target = next(i for i, line in enumerate(body_lines) if ";" in line)
    broken_lines = list(body_lines)
    broken_lines[target] = broken_lines[target].replace(";", "", 1)
    return "".join(broken_lines), target


def test_idl_field_source_plain_scalar_real_file() -> None:
    path = REPOSITORY_ROOT / "spec/std/isa/inst/I/addi.yaml"
    text = path.read_text()
    parsed = parse_yaml(text, source=str(path))
    span = parsed.sources.at("operation()")
    assert span is not None
    assert span.style is None  # plain scalar
    value = parsed.value["operation()"]

    source = idl_field_source(text, span, value, label=str(path))
    assert isinstance(source, IdlSource)
    assert source.text == value

    assert source.lineno(0) == span.start_line
    assert source.column(0) == span.start_column

    # `starting_offset` is still the real file byte offset of the value's
    # first character (used by `source_dict()`/documentation generation).
    lines = text.splitlines(keepends=True)
    file_offset = sum(len(line) for line in lines[: span.start_line - 1]) + (span.start_column - 1)
    assert source.starting_offset == file_offset

    # Sanity: that file line/column actually is the first char of the value
    # in the raw text.
    lines = text.splitlines()
    file_line = lines[span.start_line - 1]
    assert file_line[span.start_column - 1 :].startswith(value.splitlines()[0])


def test_idl_field_source_literal_block_scalar_real_file() -> None:
    path = REPOSITORY_ROOT / "spec/std/isa/csr/instret.yaml"
    text = path.read_text()
    parsed = parse_yaml(text, source=str(path))
    span = parsed.sources.at("sw_read()")
    assert span is not None
    assert span.style == "|"  # literal block scalar
    value = parsed.value["sw_read()"]

    source = idl_field_source(text, span, value, label=str(path))
    assert source.text == value

    # First content line of a literal block scalar is the line *after* the
    # `sw_read(): |` key line; content_line_0based == span.start_line exactly
    # (see udb.idl_yaml_source module docstring for why).
    lines = text.splitlines()
    first_content_line = lines[span.start_line]  # 0-based index == span.start_line
    assert first_content_line.strip() == value.splitlines()[0].strip()
    assert source.lineno(0) == span.start_line + 1


def test_idl_field_source_rejects_folded_style() -> None:
    text = "operation(): >\n  X[xd] = X[xs1];\n"
    parsed = parse_yaml(text, source="<synthetic>")
    span = parsed.sources.at("operation()")
    assert span is not None
    assert span.style == ">"
    with pytest.raises(UnsupportedYamlIdlStyle):
        idl_field_source(text, span, parsed.value["operation()"], label="<synthetic>")


def test_idl_field_source_rejects_quoted_style() -> None:
    text = 'operation(): "X[xd] = X[xs1];"\n'
    parsed = parse_yaml(text, source="<synthetic>")
    span = parsed.sources.at("operation()")
    assert span is not None
    assert span.style == '"'
    with pytest.raises(UnsupportedYamlIdlStyle):
        idl_field_source(text, span, parsed.value["operation()"], label="<synthetic>")


def test_idl_field_source_plain_scalar_parses_and_reports_correct_file_line() -> None:
    path = REPOSITORY_ROOT / "spec/std/isa/inst/I/addi.yaml"
    text = path.read_text()
    parsed = parse_yaml(text, source=str(path))
    span = parsed.sources.at("operation()")
    assert span is not None
    value = parsed.value["operation()"]
    source = idl_field_source(text, span, value, label=str(path))

    parse_function_body(value, source=source)
    # The parsed root's own source-derived line should equal the field's
    # real file line (a `X[xd] = ...` single-statement body starts exactly
    # where the value starts).
    assert source.lineno(0) == span.start_line


def test_idl_field_source_literal_scalar_syntax_error_reports_correct_file_line() -> None:
    path = REPOSITORY_ROOT / "spec/std/isa/csr/instret.yaml"
    text = path.read_text()
    parsed = parse_yaml(text, source=str(path))
    span = parsed.sources.at("sw_read()")
    assert span is not None
    value = parsed.value["sw_read()"]
    broken, _target = _corrupt_first_semicolon_line(value)
    source = idl_field_source(text, span, broken, label=str(path))

    # Ground truth for *which* line the parser lands on (the furthest failure
    # point isn't necessarily the corrupted line itself -- it's wherever
    # parsing can no longer continue, which may be a following line): parse
    # the same broken text standalone (`starting_line=0`) and shift by the
    # same amount `idl_field_source` shifts successful nodes by.
    with pytest.raises(IdlSyntaxError) as standalone:
        parse_function_body(broken)
    with pytest.raises(IdlSyntaxError) as excinfo:
        parse_function_body(broken, source=source)

    assert excinfo.value.line == standalone.value.line + span.start_line
    file_offset = source._pos_to_file_offset(excinfo.value.offset)
    file_line_start = text.rfind("\n", 0, file_offset) + 1
    assert excinfo.value.column == file_offset - file_line_start + 1


# ---------------------------------------------------------------------------
# _selection_matches version-requirement semantics
# ---------------------------------------------------------------------------


class _FakeSelection:
    def __init__(self, name: str, requirements) -> None:
        self.name = name
        self.requirements = requirements


class _FakeVersion:
    def __init__(self, version: str) -> None:
        self.version = version


class _FakeExtension:
    def __init__(self, versions) -> None:
        self.versions = [_FakeVersion(v) for v in versions]


class _FakeDatabase:
    def __init__(self, extensions: dict) -> None:
        self._extensions = extensions

    def extension(self, name: str) -> _FakeExtension:
        return self._extensions[name]


class _FakeCfgArch:
    def __init__(self, extensions: dict) -> None:
        self.database = _FakeDatabase(extensions)


def test_selection_matches_requires_requirement_string_not_bare_version() -> None:
    from udb.versions import VersionRequirement

    cfg_arch = _FakeCfgArch({"S": _FakeExtension(["1.9.1", "1.10.0", "1.11.0"])})
    selection = _FakeSelection("S", [VersionRequirement.parse("= 1.9.1")])

    # Bare "1.9.1" is not a valid requirement string (Ruby raises
    # `ArgumentError: Bad requirement string`); confirm Python's port also
    # requires requirement syntax by checking `VersionRequirement.parse`
    # itself accepts the requirement form used by real IDL
    # (`implemented_version?(ExtensionName::S, "<= 1.9.1")`).
    assert _selection_matches(cfg_arch, selection, "S", "<= 1.9.1")
    assert not _selection_matches(cfg_arch, selection, "S", ">= 2.0.0")
    assert _selection_matches(cfg_arch, selection, "S", "= 1.9.1")


def test_selection_matches_name_mismatch_is_false() -> None:
    cfg_arch = _FakeCfgArch({"S": _FakeExtension(["1.9.1"])})
    selection = _FakeSelection("S", [])
    assert not _selection_matches(cfg_arch, selection, "U", None)


def test_selection_matches_no_version_query_ignores_version() -> None:
    cfg_arch = _FakeCfgArch({"S": _FakeExtension(["1.9.1"])})
    selection = _FakeSelection("S", [])
    assert _selection_matches(cfg_arch, selection, "S", None)


# ---------------------------------------------------------------------------
# Real ConfiguredArchitecture construction helper
# ---------------------------------------------------------------------------


def _build_cfg_arch(name: str):
    database = Database.from_path(
        REPOSITORY_ROOT / "spec/std/isa", schemas_path=REPOSITORY_ROOT / "spec/schemas"
    )
    cfg = Configuration.from_file(REPOSITORY_ROOT / "cfgs" / f"{name}.yaml")
    overlays = [REPOSITORY_ROOT / "spec/custom/isa" / cfg.overlay] if cfg.overlay else []
    return database.resolve(overlays=overlays).configure(cfg)


@pytest.mark.parametrize("name", ["_", "rv32", "rv64", "qc_iu"])
def test_idl_environment_builds_for_real_configs(name: str) -> None:
    cfg_arch = _build_cfg_arch(name)
    env = idl_environment(cfg_arch)
    assert env.name == name
    assert len(env.builtin_global_vars) > 0
    assert len(env.csrs) > 0
    assert {rf.name for rf in env.register_files} == {"F", "V", "X"}
    assert set(env.register_file_max_widths) == {"F", "V", "X"}
    assert symbol_table(cfg_arch) is not None


_SAMPLE_VERSION_REQS = ("= 1.0.0", ">= 2.0.0", "= 0.1.0", "> 1.9.1", "<= 1.9.1")
_RV32_64_BIT_SUPERVISOR_EXTENSIONS = frozenset(
    {"Sv39", "Sv48", "Sv57", "Svnapot", "Svpbmt", "Svrsw60t59b", "Svukte"}
)


def test_rv32_sxlen_invariant_prohibits_64_bit_supervisor_extensions() -> None:
    cfg_arch = _build_cfg_arch("rv32")
    env = idl_environment(cfg_arch)
    for ext_name in sorted(_RV32_64_BIT_SUPERVISOR_EXTENSIONS):
        assert env.builtin_funcs.implemented(ext_name) is False
        for requirement in _SAMPLE_VERSION_REQS:
            assert env.builtin_funcs.implemented_version(ext_name, requirement) is False
