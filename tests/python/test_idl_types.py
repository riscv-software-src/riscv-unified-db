# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Tests for ``udb.idl.types`` (the Python port of ``idlc/lib/idlc/type.rb``).

Includes:

- retained non-parsing assertions from the retired IDL implementation;
- property-style coverage of the immutability/value-semantics deviation
  (qualifier mutators return a *new* ``Type``; ``_replace``/``copy.copy``
  independence; ``EnumerationType.ref_type`` self-reference survives a
  copy);
- regression tests for the three confirmed legacy bugs (B1/B2/B3), see the
  ``udb.idl.types`` module docstring; and
- general coverage of ``to_s``/``to_idl``/``comparable_to``/``equal_to``/
  ``convertable_to``/``default``/JSON-schema conversion across
  representative kinds.
"""

from __future__ import annotations

import copy

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
# Retained migration coverage for type-to-IDL behavior
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
