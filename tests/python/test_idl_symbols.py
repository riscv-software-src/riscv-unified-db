# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Tests for ``udb.idl.symbols`` (port of ``idlc/lib/idlc/symbol_table.rb``).

There is no dedicated Ruby test file for ``symbol_table.rb`` (it is only
exercised indirectly, via IDL parsing, in the Ruby suite), so these tests
are written directly against the documented Ruby semantics in
``symbol_table.rb`` and the deviations recorded in the ``udb.idl.symbols``
module docstring, rather than being a line-by-line port of an existing
Ruby test file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from udb.idl.errors import IdlInternalError
from udb.idl.symbols import (
    DuplicateSymbolError,
    EnumDef,
    IdlEnvironment,
    RuntimeParamLike,
    SymbolTable,
    Var,
)
from udb.idl.types import EnumerationType, Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)
BITS32 = Type(TypeKind.BITS, width=32)


# ---------------------------------------------------------------------------
# Var
# ---------------------------------------------------------------------------


def test_var_basic_construction() -> None:
    v = Var("x", BITS8, 5)
    assert v.name == "x"
    assert v.type is BITS8
    assert v.value == 5
    assert v.decode_var is False
    assert v.param is False
    assert v.for_loop_iter is False
    assert v.function_name is None


def test_var_requires_a_type_instance() -> None:
    with pytest.raises(IdlInternalError):
        Var("x", "not a type")  # type: ignore[arg-type]


def test_var_value_is_mutable() -> None:
    v = Var("x", BITS8, 1)
    v.value = 2
    assert v.value == 2


def test_var_const_eval_defaults_true_until_marked_incompatible() -> None:
    v = Var("x", BITS8, 1)
    assert v.const_eval is True
    v.const_incompatible()
    assert v.const_eval is False


def test_var_is_const_mirrors_type() -> None:
    const_bits = BITS8.make_const()
    assert Var("x", const_bits, 1).is_const is True
    assert Var("y", BITS8, 1).is_const is False


def test_var_clone_is_independent_of_original() -> None:
    v = Var("x", BITS8, [1, 2, 3])
    clone = v.clone()
    assert clone is not v
    assert clone.name == v.name
    assert clone.type is v.type  # Type is immutable; sharing is fine.
    assert clone.value == v.value
    assert clone.value is not v.value  # list value was shallow-copied.
    clone.value.append(4)
    assert v.value == [1, 2, 3]


def test_var_clone_does_not_propagate_for_loop_iter() -> None:
    v = Var("x", BITS8, 1, for_loop_iter=True)
    clone = v.clone()
    assert clone.for_loop_iter is False


def test_var_str_and_repr() -> None:
    v = Var("x", BITS8, 5)
    assert "x" in str(v)
    assert "5" in str(v)
    assert "NO VALUE" in str(Var("y", BITS8))
    assert "Var(" in repr(v)


# ---------------------------------------------------------------------------
# EnumDef
# ---------------------------------------------------------------------------


def test_enum_def_basic() -> None:
    e = EnumDef("Color", (0, 1), ("RED", "GREEN"))
    assert e.name == "Color"
    assert e.element_values == (0, 1)
    assert e.element_names == ("RED", "GREEN")


def test_enum_def_mismatched_lengths_raises() -> None:
    with pytest.raises(IdlInternalError):
        EnumDef("Color", (0, 1, 2), ("RED", "GREEN"))


def test_enum_def_is_frozen() -> None:
    e = EnumDef("Color", (0, 1), ("RED", "GREEN"))
    with pytest.raises(AttributeError):
        e.name = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IdlEnvironment
# ---------------------------------------------------------------------------


def test_idl_environment_defaults_are_empty() -> None:
    env = IdlEnvironment()
    assert env.mxlen is None
    assert env.builtin_global_vars == ()
    assert env.builtin_enums == ()
    assert env.csrs == ()
    assert env.params == ()
    assert env.register_files == ()


def test_idl_environment_is_frozen() -> None:
    env = IdlEnvironment()
    with pytest.raises(AttributeError):
        env.mxlen = 64  # type: ignore[misc]


def test_idl_environment_default_eval_register_length() -> None:
    env = IdlEnvironment()
    assert env.eval_register_length("return 64;", None) == 64
    assert env.eval_register_length("return MXLEN;", 32) == 32
    assert env.eval_register_length("return MXLEN;", None) == 64
    # Anything else (e.g. a parameter reference) is returned unevaluated.
    assert env.eval_register_length("return SOME_PARAM;", 32) == "SOME_PARAM"


# ---------------------------------------------------------------------------
# SymbolTable: construction and basic scope stack
# ---------------------------------------------------------------------------


def test_symbol_table_default_construction() -> None:
    symtab = SymbolTable()
    assert symtab.levels == 1
    assert symtab.at_global_scope is True
    assert "true" in symtab
    assert "false" in symtab
    assert "Boolean" in symtab
    assert symtab.get("true").value is True
    assert symtab.get("false").value is False


def test_symbol_table_push_pop() -> None:
    symtab = SymbolTable()
    symtab.push()
    assert symtab.levels == 2
    assert symtab.at_global_scope is False
    symtab.add("x", Var("x", BITS8, 1))
    assert "x" in symtab
    symtab.pop()
    assert symtab.levels == 1
    assert "x" not in symtab


def test_symbol_table_pop_at_global_scope_raises() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.pop()


def test_symbol_table_push_accepts_and_returns_self() -> None:
    symtab = SymbolTable()
    ast_stub = object()
    result = symtab.push(ast_stub)
    assert result is symtab


def test_symbol_table_callstack_renders_pushed_frames() -> None:
    @dataclass
    class _FakeAst:
        input_file: str
        lineno: int

    symtab = SymbolTable()
    symtab.push(_FakeAst("foo.idl", 10))
    text = symtab.callstack
    # str.splitlines() drops a trailing empty segment, so split on "\n"
    # explicitly to see the always-present global-scope entry (ast=None).
    lines = text.split("\n")
    assert lines[0] == "foo.idl:10"
    assert lines[1] == ""  # the always-present global-scope entry (ast=None)


# ---------------------------------------------------------------------------
# SymbolTable: lookup
# ---------------------------------------------------------------------------


def test_symbol_table_get_searches_innermost_first() -> None:
    symtab = SymbolTable()
    symtab.add("x", Var("x", BITS8, 1))
    symtab.push()
    symtab.add("x", Var("x", BITS8, 2))
    assert symtab.get("x").value == 2
    symtab.pop()
    assert symtab.get("x").value == 1


def test_symbol_table_get_missing_returns_none() -> None:
    symtab = SymbolTable()
    assert symtab.get("nope") is None


def test_symbol_table_get_global_only_looks_at_global_scope() -> None:
    symtab = SymbolTable()
    symtab.add("g", Var("g", BITS8, 1))
    symtab.push()
    symtab.add("g", Var("g", BITS8, 2))
    assert symtab.get_global("g").value == 1


def test_symbol_table_get_from_requires_positive_level() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.get_from("x", 0)


def test_symbol_table_get_from_rejects_out_of_range_level() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.get_from("x", 5)


def test_symbol_table_find_all() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("a", Var("a", BITS8, 1))
    symtab.add("b", Var("b", BITS32, 2))

    def is_8_bit_var(v: object) -> bool:
        return isinstance(v, Var) and v.type.kind is TypeKind.BITS and v.type.width == 8

    matches = symtab.find_all(is_8_bit_var)
    assert [m.name for m in matches] == ["a"]


def test_symbol_table_keys_pretty() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("x", Var("x", BITS8, 1))
    keys = symtab.keys_pretty()
    assert len(keys) == 2
    assert "x" in keys[1]


# ---------------------------------------------------------------------------
# SymbolTable: mutation / uniqueness
# ---------------------------------------------------------------------------


def test_symbol_table_add_overwrites_in_innermost_scope() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("x", Var("x", BITS8, 1))
    symtab.add("x", Var("x", BITS8, 2))
    assert symtab.get("x").value == 2


def test_symbol_table_add_unique_raises_on_duplicate() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add_unique("x", Var("x", BITS8, 1))
    with pytest.raises(DuplicateSymbolError):
        symtab.add_unique("x", Var("x", BITS8, 2))


def test_symbol_table_add_unique_checks_all_scopes() -> None:
    symtab = SymbolTable()
    symtab.add_unique("x", Var("x", BITS8, 1))
    symtab.push()
    with pytest.raises(DuplicateSymbolError):
        symtab.add_unique("x", Var("x", BITS8, 2))


def test_symbol_table_delete() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("x", Var("x", BITS8, 1))
    symtab.delete("x")
    assert "x" not in symtab


def test_symbol_table_delete_missing_raises() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.delete("nope")


def test_symbol_table_add_above_unique() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.push()
    symtab.add_above_unique("x", Var("x", BITS8, 1))
    symtab.pop()
    assert symtab.get("x").value == 1


def test_symbol_table_add_above_unique_requires_two_levels() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.add_above_unique("x", Var("x", BITS8, 1))


def test_symbol_table_add_above_unique_rejects_duplicate() -> None:
    symtab = SymbolTable()
    symtab.add_unique("x", Var("x", BITS8, 1))
    symtab.push()
    with pytest.raises(IdlInternalError):
        symtab.add_above_unique("x", Var("x", BITS8, 2))


def test_symbol_table_add_at_unique() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.push()
    symtab.add_at_unique(1, "x", Var("x", BITS8, 1))
    assert symtab.get_from("x", 2).value == 1


def test_symbol_table_add_at_unique_level_too_large_raises() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        symtab.add_at_unique(5, "x", Var("x", BITS8, 1))


# ---------------------------------------------------------------------------
# SymbolTable: snapshot / restore
# ---------------------------------------------------------------------------


def test_snapshot_and_restore_values_round_trip() -> None:
    symtab = SymbolTable()
    symtab.push()
    v = Var("x", BITS8, 1)
    symtab.add("x", v)
    snapshot = symtab.snapshot_values()
    v.value = 99
    assert symtab.get("x").value == 99
    symtab.restore_values(snapshot)
    assert symtab.get("x").value == 1


def test_snapshot_values_excludes_global_scope() -> None:
    symtab = SymbolTable()
    # "true"/"false" are global-scope Vars; snapshot_values only walks
    # non-global scopes (Ruby: `@scopes[1..]`).
    assert symtab.snapshot_values() == []
    symtab.push()
    symtab.add("x", Var("x", BITS8, 1))
    assert len(symtab.snapshot_values()) == 1


# ---------------------------------------------------------------------------
# SymbolTable: cloning
# ---------------------------------------------------------------------------


def test_global_clone_is_independent_but_shares_global_scope() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("local", Var("local", BITS8, 1))

    clone = symtab.global_clone()
    assert clone is not symtab
    assert clone.levels == 1
    assert "local" not in clone  # non-global scopes are not copied.
    assert "true" in clone  # global scope is present.

    # Mutating the clone's scope stack must not affect the original.
    clone.push()
    clone.add("only_in_clone", Var("only_in_clone", BITS8, 1))
    assert "only_in_clone" not in symtab
    assert symtab.levels == 2  # unaffected by clone.push()


def test_global_clone_has_independent_global_bindings() -> None:
    symtab = SymbolTable()
    symtab.add("existing", Var("existing", BITS8, 1))
    clone = symtab.global_clone()
    clone.add("clone_only", Var("clone_only", BITS8, 1))
    clone.get("existing").value = 2
    assert "clone_only" in clone
    assert "clone_only" not in symtab
    assert symtab.get("existing").value == 1
    symtab.add("original_only", Var("original_only", BITS8, 3))
    assert "original_only" not in clone


def test_deep_clone_default_has_independent_var_objects() -> None:
    symtab = SymbolTable()
    symtab.add("global_x", Var("global_x", BITS8, 7))
    symtab.push()
    symtab.add("x", Var("x", BITS8, 1))

    clone = symtab.deep_clone()
    assert clone is not symtab
    assert clone.get("x") is not symtab.get("x")
    assert clone.get("global_x") is not symtab.get("global_x")
    clone.get("x").value = 42
    clone.get("global_x").value = 9
    assert symtab.get("x").value == 1
    assert symtab.get("global_x").value == 7
    assert clone.get("x").value == 42
    assert clone.get("global_x").value == 9


@pytest.mark.parametrize("clone_values", [False, True])
def test_deep_clone_mutable_values_are_independent(clone_values: bool) -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.add("x", Var("x", BITS8, [1, [2, 3]]))

    clone = symtab.deep_clone(clone_values=clone_values)

    clone.get("x").value.append(4)
    clone.get("x").value[1].append(5)
    assert symtab.get("x").value == [1, [2, 3]]
    assert clone.get("x").value == [1, [2, 3, 5], 4]

    clone.get("x").value = [9, 9]
    assert symtab.get("x").value == [1, [2, 3]]
    assert clone.get("x").value == [9, 9]


def test_deep_clone_at_global_scope_only() -> None:
    symtab = SymbolTable()
    clone = symtab.deep_clone()
    assert clone.levels == 1
    clone.push()
    assert symtab.levels == 1  # unaffected.


def test_deep_clone_preserves_scope_count() -> None:
    symtab = SymbolTable()
    symtab.push()
    symtab.push()
    clone = symtab.deep_clone()
    assert clone.levels == symtab.levels == 3


def test_release_is_a_documented_no_op() -> None:
    symtab = SymbolTable()
    assert symtab.release() is None


def test_clones_do_not_leak_into_each_other() -> None:
    """Two independent clones of the same original must not see each other's
    non-global mutations (parallel-table independence)."""
    symtab = SymbolTable()
    symtab.push()
    symtab.add("shared_name", Var("shared_name", BITS8, 0))

    clone_a = symtab.deep_clone(clone_values=True)
    clone_b = symtab.deep_clone(clone_values=True)
    clone_a.get("shared_name").value = 1
    clone_b.get("shared_name").value = 2

    assert clone_a.get("shared_name").value == 1
    assert clone_b.get("shared_name").value == 2
    assert symtab.get("shared_name").value == 0


# ---------------------------------------------------------------------------
# SymbolTable: builtin globals/enums
# ---------------------------------------------------------------------------


def test_builtin_global_vars_are_seeded() -> None:
    v = Var("MY_CONST", BITS8, 5)
    env = IdlEnvironment(builtin_global_vars=(v,))
    symtab = SymbolTable(env)
    other = SymbolTable(env)
    assert symtab.get("MY_CONST") is not v
    assert symtab.get("MY_CONST") is not other.get("MY_CONST")
    assert symtab.get("MY_CONST").value == 5
    symtab.get("MY_CONST").value = 9
    assert v.value == 5
    assert other.get("MY_CONST").value == 5


def test_builtin_enums_are_seeded_as_enumeration_types() -> None:
    env = IdlEnvironment(builtin_enums=(EnumDef("Color", (0, 1), ("RED", "GREEN")),))
    symtab = SymbolTable(env)
    color = symtab.get("Color")
    assert isinstance(color, EnumerationType)
    assert color.element_names == ("RED", "GREEN")


def test_duplicate_builtin_global_var_raises() -> None:
    v1 = Var("DUP", BITS8, 1)
    v2 = Var("DUP", BITS8, 2)
    env = IdlEnvironment(builtin_global_vars=(v1, v2))
    with pytest.raises(DuplicateSymbolError):
        SymbolTable(env)


# ---------------------------------------------------------------------------
# SymbolTable: register files
# ---------------------------------------------------------------------------


@dataclass
class _FakeRegisterFile:
    name: str
    register_length: str
    registers: tuple[object, ...]


def test_register_file_seeds_array_and_element_globals() -> None:
    rf = _FakeRegisterFile("X", "return 64;", tuple(range(32)))
    env = IdlEnvironment(register_files=(rf,))
    symtab = SymbolTable(env)

    x_var = symtab.get("X")
    assert isinstance(x_var, Var)
    assert x_var.type.kind is TypeKind.ARRAY
    assert x_var.type.width == 32
    assert x_var.type.sub_type.width == 64

    x_reg_type = symtab.get("XReg")
    assert x_reg_type.width == 64
    assert x_reg_type.name == "X"


def test_register_file_uses_max_width_override() -> None:
    rf = _FakeRegisterFile("F", "return SOME_PARAM;", tuple(range(4)))
    env = IdlEnvironment(register_files=(rf,), register_file_max_widths={"F": 128})
    symtab = SymbolTable(env)
    assert symtab.get("FReg").width == 128


def test_register_file_unresolvable_width_without_override_raises() -> None:
    rf = _FakeRegisterFile("F", "return SOME_PARAM;", tuple(range(4)))
    env = IdlEnvironment(register_files=(rf,))
    with pytest.raises(IdlInternalError):
        SymbolTable(env)


def test_register_file_mxlen_reference_uses_environment_mxlen() -> None:
    rf = _FakeRegisterFile("X", "return MXLEN;", tuple(range(32)))
    env = IdlEnvironment(register_files=(rf,), mxlen=32)
    symtab = SymbolTable(env)
    assert symtab.get("XReg").width == 32


# ---------------------------------------------------------------------------
# SymbolTable: CSRs
# ---------------------------------------------------------------------------


@dataclass
class _FakeCsrField:
    name: str


@dataclass
class _FakeCsr:
    name: str
    max_length: int
    value: int | None = None
    fields: tuple[_FakeCsrField, ...] = ()

    def length(self, base: int | None) -> int | None:
        return self.max_length

    def dynamic_length(self) -> bool:
        return False


def test_csr_lookup() -> None:
    csr = _FakeCsr("mstatus", 64)
    env = IdlEnvironment(csrs=(csr,))
    symtab = SymbolTable(env)
    assert symtab.csr_exists("mstatus") is True
    assert symtab.csr_exists("nope") is False
    assert symtab.csr("mstatus") is csr
    assert symtab.csr("nope") is None
    assert symtab.csr_hash == {"mstatus": csr}


# ---------------------------------------------------------------------------
# SymbolTable: params
# ---------------------------------------------------------------------------


@dataclass
class _FakeSchema:
    max_val_known: bool = True
    max_val: int = 100
    min_val_known: bool = True
    min_val: int = 0
    to_idl_type: Type = field(default=BITS8)


@dataclass
class _FakeParam:
    name: str
    description: str = ""
    schema: _FakeSchema = field(default_factory=_FakeSchema)
    value_known: bool = True
    value: object = 1
    idl_type: Type = field(default=BITS8)


def test_param_lookup() -> None:
    param: RuntimeParamLike = _FakeParam("MY_PARAM")
    env = IdlEnvironment(params=(param,))
    symtab = SymbolTable(env)
    assert symtab.param("MY_PARAM") is param
    assert symtab.param("nope") is None
    assert symtab.params_hash == {"MY_PARAM": param}


def test_params_hash_is_memoized() -> None:
    param = _FakeParam("MY_PARAM")
    env = IdlEnvironment(params=(param,))
    symtab = SymbolTable(env)
    first = symtab.params_hash
    assert symtab.params_hash is first


# ---------------------------------------------------------------------------
# SymbolTable: possible_xlens / multi_xlen
# ---------------------------------------------------------------------------


def test_possible_xlens_without_callback_raises() -> None:
    symtab = SymbolTable()
    with pytest.raises(IdlInternalError):
        _ = symtab.possible_xlens


def test_possible_xlens_with_callback() -> None:
    env = IdlEnvironment(possible_xlens_cb=lambda: [32, 64])
    symtab = SymbolTable(env)
    assert symtab.possible_xlens == (32, 64)
    assert symtab.multi_xlen is True


def test_single_xlen_is_not_multi() -> None:
    env = IdlEnvironment(possible_xlens_cb=lambda: [64])
    symtab = SymbolTable(env)
    assert symtab.multi_xlen is False


def test_possible_xlens_is_memoized() -> None:
    calls = {"n": 0}

    def cb() -> list[int]:
        calls["n"] += 1
        return [64]

    env = IdlEnvironment(possible_xlens_cb=cb)
    symtab = SymbolTable(env)
    _ = symtab.possible_xlens
    _ = symtab.possible_xlens
    assert calls["n"] == 1


def test_global_clone_copies_memo_independently() -> None:
    """Deviation 2: `global_clone` copies the `_Memo`, so re-memoizing on a
    clone does not affect the original (contrast with `deep_clone`, which
    shares it -- see the module docstring and the next test)."""
    calls = {"n": 0}

    def cb() -> list[int]:
        calls["n"] += 1
        return [64]

    env = IdlEnvironment(possible_xlens_cb=cb)
    symtab = SymbolTable(env)
    clone = symtab.global_clone()
    _ = clone.possible_xlens
    assert calls["n"] == 1
    # The original's memo is untouched; computing it again calls back.
    _ = symtab.possible_xlens
    assert calls["n"] == 2


def test_deep_clone_has_independent_memo() -> None:
    calls = {"n": 0}

    def cb() -> list[int]:
        calls["n"] += 1
        return [64]

    env = IdlEnvironment(possible_xlens_cb=cb)
    symtab = SymbolTable(env)
    clone = symtab.deep_clone()
    assert clone.possible_xlens == (64,)
    assert calls["n"] == 1
    assert clone.possible_xlens == (64,)
    assert calls["n"] == 1
    assert symtab.possible_xlens == (64,)
    assert calls["n"] == 2
    assert symtab.possible_xlens == (64,)
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# SymbolTable: builtin function callbacks
# ---------------------------------------------------------------------------


def test_builtin_funcs_stored_and_callable() -> None:
    from udb.idl.symbols import BuiltinFunctionCallbacks

    callbacks = BuiltinFunctionCallbacks(
        implemented=lambda name: name == "Zicsr",
        implemented_version=lambda name, version: True,
        implemented_csr=lambda addr: addr == 0x300,
    )
    env = IdlEnvironment(builtin_funcs=callbacks)
    symtab = SymbolTable(env)
    assert symtab.builtin_funcs is callbacks
    assert symtab.builtin_funcs.implemented("Zicsr") is True
    assert symtab.builtin_funcs.implemented("Zba") is False
