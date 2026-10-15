# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Tests for ``udb.idl.types`` (the Python port of ``idlc/lib/idlc/type.rb``).

Includes:

- direct ports of the non-parsing assertions from
  ``tools/ruby-gems/idlc/test/test_type_to_idl.rb``;
- property-style coverage of the immutability/value-semantics deviation
  (qualifier mutators return a *new* ``Type``; ``_replace``/``copy.copy``
  independence; ``EnumerationType.ref_type`` self-reference survives a
  copy);
- regression tests for the three confirmed Ruby bugs (B1/B2/B3), see the
  ``udb.idl.types`` module docstring;
- general coverage of ``to_s``/``to_idl``/``comparable_to``/``equal_to``/
  ``convertable_to``/``default``/JSON-schema conversion across
  representative kinds; and
- a Ruby-oracle differential test (gated by ``UDB_TEST_RUBY=1``) that
  builds the same types directly in Ruby via ``Idl::Type.new`` and
  compares results, using ``tests/python/ruby_idl_type_oracle.rb``.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from udb.idl.errors import IdlInternalError
from udb.idl.types import (
    BOOL_TYPE,
    STRING_TYPE,
    VOID_TYPE,
    WIDTH_UNKNOWN,
    BitfieldType,
    CsrType,
    EnumerationType,
    FunctionType,
    Qualifier,
    StructType,
    Type,
    TypeKind,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_type_oracle.rb")


class _FakeCsr:
    """Minimal stand-in for the ``CsrLike`` protocol, matching the Ruby oracle's ``FakeCsr``."""

    def __init__(self, name: str, max_length: int) -> None:
        self._name = name
        self._max_length = max_length

    @property
    def name(self) -> str:
        return self._name

    def length(self, base: int | None) -> int | None:
        return self._max_length

    @property
    def max_length(self) -> int:
        return self._max_length

    def dynamic_length(self) -> bool:
        return False

    @property
    def fields(self) -> list[object]:
        return []

    @property
    def value(self) -> int | None:
        return None


# ---------------------------------------------------------------------------
# Ported from tools/ruby-gems/idlc/test/test_type_to_idl.rb
# ---------------------------------------------------------------------------


def test_bits_to_idl_has_closing_angle_bracket() -> None:
    assert Type(TypeKind.BITS, width=32).to_idl() == "Bits<32>"


def test_string_to_idl_returns_string_name() -> None:
    assert Type(TypeKind.STRING, width=8).to_idl() == "String"


def test_json_schema_zero_integer_const_needs_one_bit() -> None:
    result = Type.from_json_schema({"const": 0})
    assert result is not None
    assert result.equal_to(Type(TypeKind.BITS, width=1))


def test_json_schema_tuple_array_widens_integer_item_types() -> None:
    result = Type.from_json_schema(
        {
            "type": "array",
            "items": [{"const": 0}],
            "additionalItems": {"type": "integer", "enum": [7, 16]},
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
        }
    )
    assert result is not None
    assert result.kind is TypeKind.ARRAY
    assert result.width == WIDTH_UNKNOWN
    assert result.sub_type.equal_to(Type(TypeKind.BITS, width=5))


# ---------------------------------------------------------------------------
# Immutability / value semantics
# ---------------------------------------------------------------------------


def test_type_setattr_raises() -> None:
    t = Type(TypeKind.BITS, width=8)
    with pytest.raises(IdlInternalError):
        t.qualifiers = (Qualifier.CONST,)  # type: ignore[misc]


def test_type_delattr_raises() -> None:
    t = Type(TypeKind.BITS, width=8)
    with pytest.raises(IdlInternalError):
        del t.qualifiers


def test_qualify_returns_new_type_and_leaves_original_unchanged() -> None:
    original = Type(TypeKind.BITS, width=8)
    made_const = original.make_const()
    assert made_const is not original
    assert original.qualifiers == ()
    assert made_const.qualifiers == (Qualifier.CONST,)
    assert made_const.is_const
    assert not original.is_const


def test_qualify_is_idempotent() -> None:
    t = Type(TypeKind.BITS, width=8).make_const()
    assert t.make_const() is t  # qualify() short-circuits if already present


def test_chained_qualifiers_accumulate_independently() -> None:
    base = Type(TypeKind.BITS, width=8)
    const_signed = base.make_const().make_signed()
    assert const_signed.qualifiers == (Qualifier.CONST, Qualifier.SIGNED)
    assert base.qualifiers == ()


def test_make_global_and_make_known() -> None:
    t = Type(TypeKind.BITS, width=8)
    assert t.make_global().is_global
    assert t.make_known().is_known
    assert not t.is_global
    assert not t.is_known


def test_copy_of_type_is_independent_and_still_immutable() -> None:
    # Exercises the __getstate__/__setstate__ + _replace mechanism directly.
    t = Type(TypeKind.BITS, width=8)
    duplicate = copy.copy(t)
    assert duplicate is not t
    assert duplicate.equal_to(t)
    with pytest.raises(IdlInternalError):
        duplicate.qualifiers = (Qualifier.CONST,)  # type: ignore[misc]


def test_enumeration_type_ref_type_is_self_referential_and_survives_replace() -> None:
    enum_type = EnumerationType("Color", ("RED", "GREEN"), (0, 1))
    assert enum_type.ref_type.enum_class is enum_type
    qualified = enum_type.make_const()
    assert qualified is not enum_type
    # The copied EnumerationType keeps its *original* ref_type (pointing back
    # at the pre-qualification object), matching Ruby's shallow `clone`-like
    # copy semantics: qualifying only ever changes `qualifiers`.
    assert qualified.ref_type is enum_type.ref_type


# ---------------------------------------------------------------------------
# Confirmed Ruby bug regressions (see module docstring in udb/idl/types.py)
# ---------------------------------------------------------------------------


def test_b1_equal_to_accepts_any_type_kind_symbol() -> None:
    """B1: Ruby crashes calling equal_to?(:bits); Python must not."""
    t = Type(TypeKind.BITS, width=8)
    assert t.equal_to(TypeKind.BITS) is False  # rhs has no width -> not equal, but no crash
    assert t.equal_to(TypeKind.BOOLEAN) is False


def test_b1_convertable_to_accepts_any_type_kind_symbol() -> None:
    """B1: Ruby crashes calling convertable_to?(:bits); Python must not."""
    t = Type(TypeKind.BITS, width=8)
    assert t.convertable_to(TypeKind.BITS) is True
    assert t.convertable_to(TypeKind.STRING) is False


def test_b2_comparable_to_csr_with_different_names_does_not_crash() -> None:
    """B2: Ruby's comparable_to? :csr branch calls a nonexistent Csr#width."""
    lhs = CsrType(_FakeCsr("mstatus", 64))
    rhs = CsrType(_FakeCsr("mtvec", 64))
    # Should not raise, and (both being 64-bit CSRs) should be comparable.
    assert lhs.comparable_to(rhs) is True


def test_b2_comparable_to_csr_with_bits_operand_does_not_crash() -> None:
    """B2: the corrected branch must not read ``csr`` from a non-CSR operand."""
    csr = CsrType(_FakeCsr("mstatus", 64))
    assert csr.comparable_to(Type(TypeKind.BITS, width=64)) is True
    assert csr.comparable_to(Type(TypeKind.STRING)) is False


def test_b3_array_default_elements_are_independent() -> None:
    """B3: Ruby's Array#default aliases the same sub_type default across all elements."""
    struct_type = StructType("Point", (Type(TypeKind.BITS, width=8),), ("x",))
    array_type = Type(TypeKind.ARRAY, width=2, sub_type=struct_type)
    default = array_type.default()
    assert isinstance(default, list)
    default[0]["x"] = 42
    assert default[1]["x"] == 0


# ---------------------------------------------------------------------------
# General coverage across representative kinds
# ---------------------------------------------------------------------------


def test_bits_str_and_default() -> None:
    t = Type(TypeKind.BITS, width=4)
    assert str(t) == "Bits<4>"
    assert t.default() == 0
    assert t.name == "Bits<4>"


def test_bits_signed_qualifier_blocks_to_idl() -> None:
    signed = Type(TypeKind.BITS, width=4).make_signed()
    with pytest.raises(IdlInternalError):
        signed.to_idl()


def test_boolean() -> None:
    assert str(BOOL_TYPE) == "Boolean"
    assert BOOL_TYPE.to_idl() == "Boolean"
    assert BOOL_TYPE.default() is False


def test_string_default() -> None:
    assert STRING_TYPE.default() == ""


def test_void_has_no_to_idl() -> None:
    assert str(VOID_TYPE) == "void"
    with pytest.raises(IdlInternalError):
        VOID_TYPE.to_idl()


def test_array_of_bits() -> None:
    sub = Type(TypeKind.BITS, width=8)
    arr = Type(TypeKind.ARRAY, width=3, sub_type=sub)
    assert str(arr) == "array of Bits<8>"
    assert arr.default() == [0, 0, 0]
    assert arr.is_array
    assert arr.ary_type() is sub


def test_nested_array_ary_type_returns_innermost_element() -> None:
    innermost = Type(TypeKind.BITS, width=8)
    inner_array = Type(TypeKind.ARRAY, width=2, sub_type=innermost)
    outer_array = Type(TypeKind.ARRAY, width=3, sub_type=inner_array)
    assert outer_array.ary_type() is innermost


def test_tuple() -> None:
    tup = Type(TypeKind.TUPLE, tuple_types=(Type(TypeKind.BITS, width=8), BOOL_TYPE))
    assert str(tup) == "(Bits<8>,Boolean)"
    with pytest.raises(IdlInternalError):
        tup.default()


def test_enum_and_enum_ref() -> None:
    enum_type = EnumerationType("Color", ("RED", "GREEN"), (0, 1))
    assert str(enum_type) == "enum definition Color"
    assert enum_type.value("RED") == 0
    assert enum_type.value("GREEN") == 1
    assert enum_type.value("BLUE") is None
    assert enum_type.element_name(1) == "GREEN"
    with pytest.raises(IdlInternalError):
        enum_type.element_name(99)

    ref = enum_type.ref_type
    assert str(ref) == "enum Color"
    assert ref.default() == 0  # min(element_values)
    assert ref.name == "Color"


def test_bitfield() -> None:
    bf = BitfieldType("MyBits", 8, ("a", "b"), (range(4), range(4, 8)))
    assert str(bf) == "bitfield MyBits"
    assert bf.width == 8
    assert bf.range("a") == range(4)
    assert bf.range("b") == range(4, 8)
    with pytest.raises(IdlInternalError):
        bf.range("c")


def test_struct() -> None:
    st = StructType(
        "Point", (Type(TypeKind.BITS, width=8), Type(TypeKind.BITS, width=8)), ("x", "y")
    )
    assert str(st) == "struct Point"
    assert st.default() == {"x": 0, "y": 0}
    assert st.has_member("x")
    assert not st.has_member("z")
    assert st.member_type("y").width == 8


def test_csr() -> None:
    csr_type = CsrType(_FakeCsr("mstatus", 64))
    assert str(csr_type) == "CSR[mstatus]"
    assert csr_type.width == 64
    assert csr_type.name == "mstatus"
    assert csr_type.fields == []


def test_qualifiers_render_before_type_body() -> None:
    t = Type(TypeKind.BITS, width=8).make_const().make_signed()
    assert str(t) == "const signed Bits<8>"


# -- comparable_to / equal_to / convertable_to matrix -----------------------


@pytest.mark.parametrize(
    ("lhs", "rhs", "expected"),
    [
        (Type(TypeKind.BITS, width=8), Type(TypeKind.BITS, width=16), True),
        # Ruby's `convertable_to?`'s `:bits` branch ignores signedness entirely
        # (only `kind == :bits || kind == :bitfield` is checked), confirmed live
        # against Ruby -- this is True, not False.
        (Type(TypeKind.BITS, width=8), Type(TypeKind.BITS, width=16).make_signed(), True),
        (Type(TypeKind.BITS, width=8), BOOL_TYPE, False),
        (BOOL_TYPE, BOOL_TYPE, True),
        (STRING_TYPE, STRING_TYPE, True),
        (STRING_TYPE, Type(TypeKind.BITS, width=8), False),
    ],
)
def test_convertable_to_matrix(lhs: Type, rhs: Type, expected: bool) -> None:
    assert lhs.convertable_to(rhs) is expected


def test_bitfield_convertable_to_exact_width_bits() -> None:
    bf = BitfieldType("MyBits", 8, ("a",), (range(8),))
    assert Type(TypeKind.BITS, width=8).convertable_to(bf) is True
    assert bf.convertable_to(Type(TypeKind.BITS, width=8)) is True
    assert bf.convertable_to(Type(TypeKind.BITS, width=4)) is False


def test_array_convertable_to_matching_array() -> None:
    sub = Type(TypeKind.BITS, width=8)
    arr_a = Type(TypeKind.ARRAY, width=2, sub_type=sub)
    arr_b = Type(TypeKind.ARRAY, width=2, sub_type=sub)
    arr_c = Type(TypeKind.ARRAY, width=3, sub_type=sub)
    assert arr_a.convertable_to(arr_b) is True
    assert arr_a.convertable_to(arr_c) is False


def test_struct_convertable_to_same_name_only() -> None:
    a = StructType("Point", (Type(TypeKind.BITS, width=8),), ("x",))
    b = StructType("Point", (Type(TypeKind.BITS, width=8),), ("x",))
    c = StructType("Other", (Type(TypeKind.BITS, width=8),), ("x",))
    assert a.convertable_to(b) is True
    assert a.convertable_to(c) is False


def test_equal_to_ignores_qualifiers() -> None:
    plain = Type(TypeKind.BITS, width=8)
    qualified = plain.make_const().make_signed()
    assert plain.equal_to(qualified)
    assert qualified.equal_to(plain)


def test_equal_to_array_recurses_into_sub_type() -> None:
    a = Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8))
    b = Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8))
    c = Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=16))
    assert a.equal_to(b)
    assert not a.equal_to(c)


def test_comparable_to_enum_requires_convertable_bits() -> None:
    """B1 (direct manifestation): comparable_to()'s ENUM branch internally calls
    ``rhs.convertable_to(TypeKind.BITS)`` -- confirmed live that Ruby's
    ``comparable_to?`` crashes here for *any* rhs (not just a bare symbol
    argument), so this exercises the exact reachable Ruby bug, not just the
    symbol-coercion API surface (see test_b1_* above and the module docstring).
    """
    enum_type = EnumerationType("Color", ("RED", "GREEN"), (0, 1))
    assert enum_type.comparable_to(Type(TypeKind.BITS, width=8)) is True
    assert enum_type.comparable_to(BOOL_TYPE) is False


def test_comparable_to_function_is_always_false() -> None:
    from udb.idl.symbols import SymbolTable

    class _FakeFuncDef:
        argument_nodes: tuple[object, ...] = ()

        def builtin(self) -> bool:
            return False

        def generated(self) -> bool:
            return False

        def external(self) -> bool:
            return False

        def num_args(self) -> int:
            return 0

        def arguments(self, symtab: object) -> list[tuple[Type, str]]:
            return []

        def return_type(self, symtab: object) -> Type:
            return BOOL_TYPE

        @property
        def body(self) -> object:
            return None

    func_type = FunctionType("my_func", _FakeFuncDef(), SymbolTable())
    assert func_type.comparable_to(BOOL_TYPE) is False
    assert func_type.comparable_to(Type(TypeKind.BITS, width=8)) is False


def test_dunder_eq_matches_bits_width_only() -> None:
    assert Type(TypeKind.BITS, width=8) == Type(TypeKind.BITS, width=8)
    assert Type(TypeKind.BITS, width=8) != Type(TypeKind.BITS, width=16)


def test_dunder_eq_raises_for_unimplemented_kinds() -> None:
    # Faithful, narrow port of Ruby's Type#== (see module docstring deviation 4).
    with pytest.raises(IdlInternalError):
        _ = Type(TypeKind.BITS, width=8) == BOOL_TYPE


def test_dunder_hash_is_identity_based() -> None:
    a = Type(TypeKind.BITS, width=8)
    b = Type(TypeKind.BITS, width=8)
    assert a == b
    assert hash(a) != hash(b)  # deliberately NOT structural, see module docstring


# -- JSON schema conversion --------------------------------------------------


def test_from_json_schema_boolean() -> None:
    result = Type.from_json_schema({"type": "boolean"})
    assert result is not None
    assert result.kind is TypeKind.BOOLEAN


def test_from_json_schema_integer_with_maximum() -> None:
    result = Type.from_json_schema({"type": "integer", "maximum": 200})
    assert result is not None
    assert result.kind is TypeKind.BITS
    assert result.width == 8  # 200 needs 8 bits


def test_from_json_schema_integer_no_bound_defaults_to_128() -> None:
    result = Type.from_json_schema({"type": "integer"})
    assert result is not None
    assert result.width == 128


def test_from_json_schema_string_enum_width_is_max_length() -> None:
    result = Type.from_json_schema({"type": "string", "enum": ["a", "bb", "ccc"]})
    assert result is not None
    assert result.kind is TypeKind.STRING
    assert result.width == 3


def test_from_json_schema_all_of_bits_picks_max_width() -> None:
    result = Type.from_json_schema({"allOf": [{"const": 1}, {"type": "integer", "maximum": 300}]})
    assert result is not None
    assert result.kind is TypeKind.BITS
    assert result.width == 9  # 300 needs 9 bits


def test_from_json_schema_all_of_disagreeing_kinds_raises() -> None:
    with pytest.raises(IdlInternalError):
        Type.from_json_schema({"allOf": [{"const": 1}, {"type": "string"}]})


def test_from_json_schema_ref_uint32_and_uint64() -> None:
    r32 = Type.from_json_schema({"$ref": "schema_defs.json#/$defs/uint32"})
    r64 = Type.from_json_schema({"$ref": "schema_defs.json#/$defs/uint64"})
    assert r32 is not None and r32.width == 32
    assert r64 is not None and r64.width == 64


def test_from_json_schema_not_returns_none() -> None:
    assert Type.from_json_schema({"not": {}}) is None


def test_from_json_schema_array_with_uniform_items_object() -> None:
    result = Type.from_json_schema(
        {"type": "array", "items": {"type": "integer", "maximum": 15}, "minItems": 2, "maxItems": 2}
    )
    assert result is not None
    assert result.kind is TypeKind.ARRAY
    assert result.width == 2
    assert result.sub_type.width == 4


def test_from_json_schema_array_unbounded_width_is_unknown() -> None:
    result = Type.from_json_schema(
        {"type": "array", "items": {"type": "integer", "maximum": 15}, "minItems": 1, "maxItems": 5}
    )
    assert result is not None
    assert result.width == WIDTH_UNKNOWN


# ---------------------------------------------------------------------------
# Ruby oracle differential test
# ---------------------------------------------------------------------------


def _bits(width: int, *quals: str) -> dict[str, Any]:
    return {"kind": "bits", "width": width, "qualifiers": list(quals)}


_MATRIX_SPECS: list[dict[str, Any]] = [
    _bits(1),
    _bits(8),
    _bits(32),
    _bits(64),
    _bits(8, "const"),
    _bits(8, "signed"),
    _bits(8, "const", "signed"),
    {"kind": "boolean"},
    {"kind": "string", "width": 8},
    {"kind": "void"},
    {"kind": "array", "width": 3, "sub_type": _bits(8)},
    {"kind": "tuple", "tuple_types": [_bits(8), {"kind": "boolean"}]},
    {
        "kind": "enum",
        "name": "Color",
        "element_names": ["RED", "GREEN"],
        "element_values": [0, 1],
    },
    {
        "kind": "enum_ref",
        "name": "Color",
        "element_names": ["RED", "GREEN"],
        "element_values": [0, 1],
    },
    {
        "kind": "bitfield",
        "name": "MyBits",
        "width": 8,
        "field_names": ["a", "b"],
        "field_ranges": [[0, 4], [4, 8]],
    },
    {
        "kind": "struct",
        "name": "Point",
        "member_types": [_bits(8), _bits(8)],
        "member_names": ["x", "y"],
    },
    {"kind": "csr", "csr_name": "mstatus", "max_length": 64},
]

_JSON_SCHEMAS: list[dict[str, Any]] = [
    {"const": 0},
    {"const": 100},
    {"type": "boolean"},
    {"type": "integer", "maximum": 300},
    {"type": "integer", "enum": [1, 2, 4, 8]},
    {"type": "string", "enum": ["a", "bb", "ccc"]},
    {"allOf": [{"const": 1}, {"type": "integer", "maximum": 300}]},
    {"$ref": "schema_defs.json#/$defs/uint32"},
    {"$ref": "schema_defs.json#/$defs/uint64"},
    {
        "type": "array",
        "items": [{"const": 0}],
        "additionalItems": {"type": "integer", "enum": [7, 16]},
        "minItems": 1,
        "maxItems": 3,
        "uniqueItems": True,
    },
]


def _build_python_type_from_spec(spec: dict[str, Any]) -> Type:
    kind = spec["kind"]
    qualifiers = tuple(Qualifier(q) for q in spec.get("qualifiers", []))
    if kind == "bits":
        return Type(TypeKind.BITS, width=spec["width"], qualifiers=qualifiers)
    if kind == "boolean":
        return Type(TypeKind.BOOLEAN, qualifiers=qualifiers)
    if kind == "string":
        return Type(TypeKind.STRING, width=spec.get("width"), qualifiers=qualifiers)
    if kind == "void":
        return Type(TypeKind.VOID, qualifiers=qualifiers)
    if kind == "array":
        return Type(
            TypeKind.ARRAY,
            width=spec["width"],
            sub_type=_build_python_type_from_spec(spec["sub_type"]),
            qualifiers=qualifiers,
        )
    if kind == "tuple":
        return Type(
            TypeKind.TUPLE,
            tuple_types=tuple(_build_python_type_from_spec(s) for s in spec["tuple_types"]),
            qualifiers=qualifiers,
        )
    if kind == "enum":
        return EnumerationType(spec["name"], spec["element_names"], spec["element_values"])
    if kind == "enum_ref":
        return EnumerationType(spec["name"], spec["element_names"], spec["element_values"]).ref_type
    if kind == "bitfield":
        return BitfieldType(
            spec["name"],
            spec["width"],
            spec["field_names"],
            [range(a, b) for a, b in spec["field_ranges"]],
        )
    if kind == "struct":
        return StructType(
            spec["name"],
            [_build_python_type_from_spec(s) for s in spec["member_types"]],
            spec["member_names"],
        )
    if kind == "csr":
        return CsrType(_FakeCsr(spec["csr_name"], spec["max_length"]), qualifiers=qualifiers)
    raise ValueError(f"unhandled spec kind {kind!r}")


def _python_type_props(t: Type) -> dict[str, Any]:
    props: dict[str, Any] = {"kind": t.kind.value}
    try:
        props["to_s"] = str(t)
    except IdlInternalError as e:
        props["to_s_error"] = str(e)
    try:
        props["to_idl"] = t.to_idl()
    except IdlInternalError as e:
        props["to_idl_error"] = str(e)
    try:
        props["width"] = t.width
    except IdlInternalError:
        # Only assert *some* error is raised, not the exact message: Ruby's
        # `width` accessor is `T.must(@width)` and raises Sorbet's generic
        # "Passed `nil` into T.must" for kinds with no width, while Python's
        # accessor raises a purpose-built `IdlInternalError` message. Same
        # observable behavior (raises when width is unset), different text.
        props["width_error"] = True
    props["qualifiers"] = sorted(q.value for q in t.qualifiers)
    try:
        props["name"] = t.name
    except IdlInternalError as e:
        props["name_error"] = str(e)
    try:
        props["default"] = t.default()
    except IdlInternalError as e:
        props["default_error"] = str(e)
    return props


def _run_ruby_oracle(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")
    result = subprocess.run(
        [mise, "exec", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
        cwd=REPOSITORY_ROOT,
        input=json.dumps({"commands": commands}),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby IDL type oracle failed:\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare against the Ruby Idl::Type oracle",
)
def test_ruby_oracle_matrix_props_match() -> None:
    commands = [{"op": "props", "type": spec} for spec in _MATRIX_SPECS]
    ruby_results = _run_ruby_oracle(commands)
    for spec, ruby_props in zip(_MATRIX_SPECS, ruby_results, strict=True):
        python_props = _python_type_props(_build_python_type_from_spec(spec))
        assert python_props == ruby_props, f"mismatch for spec {spec}"


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare against the Ruby Idl::Type oracle",
)
def test_ruby_oracle_json_schema_matches() -> None:
    commands = [{"op": "json_schema", "schema": schema} for schema in _JSON_SCHEMAS]
    ruby_results = _run_ruby_oracle(commands)
    for schema, ruby_result in zip(_JSON_SCHEMAS, ruby_results, strict=True):
        python_type = Type.from_json_schema(schema)
        if python_type is None:
            assert ruby_result == {"type": None}, f"mismatch for schema {schema}"
            continue
        assert ruby_result["type"] == _python_type_props(python_type), (
            f"mismatch for schema {schema}"
        )


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare against the Ruby Idl::Type oracle",
)
def test_ruby_oracle_convertable_to_matrix_matches() -> None:
    pairs = [
        (_bits(8), _bits(16)),
        (_bits(16), _bits(8)),
        (_bits(8), {"kind": "boolean"}),
        ({"kind": "boolean"}, {"kind": "boolean"}),
        ({"kind": "string", "width": 8}, {"kind": "string", "width": 4}),
        (
            {
                "kind": "bitfield",
                "name": "MyBits",
                "width": 8,
                "field_names": ["a"],
                "field_ranges": [[0, 8]],
            },
            _bits(8),
        ),
    ]
    commands = [
        {"op": "compare", "lhs": lhs, "rhs": rhs, "method": "convertable_to"} for lhs, rhs in pairs
    ]
    ruby_results = _run_ruby_oracle(commands)
    for (lhs, rhs), ruby_result in zip(pairs, ruby_results, strict=True):
        python_result = _build_python_type_from_spec(lhs).convertable_to(
            _build_python_type_from_spec(rhs)
        )
        assert ruby_result == {"result": python_result}, f"mismatch for {lhs} convertable_to {rhs}"


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to reproduce the confirmed Ruby bugs",
)
def test_ruby_oracle_reproduces_b1_equal_to_crash() -> None:
    commands = [
        {"op": "bug_b1_equal_to_symbol", "type": _bits(8), "other_kind": "bits"},
        {"op": "bug_b1_convertable_to_symbol", "type": _bits(8), "other_kind": "bits"},
    ]
    ruby_results = _run_ruby_oracle(commands)
    assert ruby_results[0]["error"] == "NoMethodError: undefined method 'kind' for nil"
    assert ruby_results[1]["error"] == "NoMethodError: undefined method 'kind' for nil"
    # Python does not crash for the same inputs.
    assert Type(TypeKind.BITS, width=8).equal_to(TypeKind.BITS) is False
    assert Type(TypeKind.BITS, width=8).convertable_to(TypeKind.BITS) is True


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to reproduce the confirmed Ruby bugs",
)
def test_ruby_oracle_reproduces_b2_comparable_to_csr_crash() -> None:
    commands = [
        {
            "op": "bug_b2_comparable_to_csr",
            "lhs": {"kind": "csr", "csr_name": "mstatus", "max_length": 64},
            "rhs": {"kind": "csr", "csr_name": "mtvec", "max_length": 64},
        }
    ]
    ruby_results = _run_ruby_oracle(commands)
    assert "undefined method 'width'" in ruby_results[0]["error"]
    # Python does not crash for the same inputs.
    lhs = CsrType(_FakeCsr("mstatus", 64))
    rhs = CsrType(_FakeCsr("mtvec", 64))
    assert lhs.comparable_to(rhs) is True


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to reproduce the confirmed Ruby bugs",
)
def test_ruby_oracle_reproduces_b3_array_default_aliasing() -> None:
    spec = {
        "kind": "array",
        "width": 2,
        "sub_type": {
            "kind": "struct",
            "name": "Point",
            "member_types": [_bits(8)],
            "member_names": ["x"],
        },
    }
    commands = [
        {"op": "bug_b3_array_default_aliasing", "type": spec, "member_name": "x", "new_value": 42}
    ]
    ruby_results = _run_ruby_oracle(commands)
    # Ruby's Array.new(width, sub_type.default) aliases the same Hash: mutating
    # element 0 is visible in element 1 too.
    assert ruby_results[0]["second_element"] == {"x": 42}
    # Python's default() builds independent elements.
    struct_type = StructType("Point", (Type(TypeKind.BITS, width=8),), ("x",))
    array_type = Type(TypeKind.ARRAY, width=2, sub_type=struct_type)
    default = array_type.default()
    default[0]["x"] = 42
    assert default[1]["x"] == 0
