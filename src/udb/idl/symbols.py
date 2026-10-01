# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Python port of the IDL symbol table (Ruby ``idlc/lib/idlc/symbol_table.rb``).

Like ``types.py``, this module has no dependency on ``udb.idl.parser``/
``udb.idl.ast`` or on ``udb.architecture``. Ruby's ``SymbolTable#initialize``
reaches directly into an ``Architecture``/``Udb::Cfg`` (for params, CSRs,
register files, builtin enums/functions, and ``possible_xlens``); here that
is replaced by an explicit :class:`IdlEnvironment` value that the caller
(the architecture-integration slice) builds and passes in.

Ruby -> Python surface mapping
-------------------------------

======================================  =========================================
Ruby (``symbol_table.rb``)              Python (this module)
======================================  =========================================
``Idl::Var``                            ``Var``
``Var#const_incompatible!``             ``Var.const_incompatible()``
``Var#const_eval?``                     ``Var.const_eval`` (property)
``Var#for_loop_iter?``                  ``Var.for_loop_iter`` (field)
``Var#clone``                           ``Var.clone()``
``Var#const?``                          ``Var.is_const`` (property)
``Var#decode_var?``                     ``Var.decode_var`` (field)
``Var#param?``                          ``Var.param`` (field)
``Var#value=``                          ``Var.value = ...`` (still mutable, see below)
``Idl::SymbolTable::EnumDef``           ``EnumDef``
``Idl::SymbolTable::DuplicateSymError`` ``DuplicateSymbolError``
``Idl::SymbolTable::BuiltinFunctionCallbacks``  ``BuiltinFunctionCallbacks``
``Idl::SymbolTable::PossibleXlensCallbackType``  ``PossibleXlensCallback``
``Idl::SymbolTable::Implemented*CallbackType``  ``Implemented*Callback``
``Idl::RuntimeParam`` (interface)       ``RuntimeParamLike`` (``Protocol``)
``Idl::Schema`` (interface)             ``SchemaLike`` (``Protocol``)
(register file YAML object)             ``RegisterFileLike`` (``Protocol``)
(architecture/config wiring)             ``IdlEnvironment`` (new; see below)
``SymbolTable#initialize``              ``SymbolTable.__init__`` (takes an ``IdlEnvironment``)
``SymbolTable#push``                    ``SymbolTable.push()``
``SymbolTable#pop``                     ``SymbolTable.pop()``
``SymbolTable#callstack``               ``SymbolTable.callstack`` (property)
``SymbolTable#key?``                    ``SymbolTable.has_key()`` / ``name in symtab``
``SymbolTable#keys_pretty``             ``SymbolTable.keys_pretty()``
``SymbolTable#get``                     ``SymbolTable.get()``
``SymbolTable#get_from``                ``SymbolTable.get_from()``
``SymbolTable#get_global``              ``SymbolTable.get_global()``
``SymbolTable#find_all``                ``SymbolTable.find_all()``
``SymbolTable#add``                     ``SymbolTable.add()``
``SymbolTable#add!``                    ``SymbolTable.add_unique()``
``SymbolTable#del``                     ``SymbolTable.delete()``
``SymbolTable#add_above!``              ``SymbolTable.add_above_unique()``
``SymbolTable#add_at!``                 ``SymbolTable.add_at_unique()``
``SymbolTable#levels``                  ``SymbolTable.levels`` (property)
``SymbolTable#at_global_scope?``        ``SymbolTable.at_global_scope`` (property)
``SymbolTable#snapshot_values``         ``SymbolTable.snapshot_values()``
``SymbolTable#restore_values``          ``SymbolTable.restore_values()``
``SymbolTable#global_clone``            ``SymbolTable.global_clone()`` (no pool; always fresh)
``SymbolTable#deep_clone``              ``SymbolTable.deep_clone()``
``SymbolTable#release``                 ``SymbolTable.release()`` (documented no-op)
``SymbolTable#in_use?``                 *not ported* (clone-pool bookkeeping; see below)
``SymbolTable#deep_freeze``             *not ported* (clone-pool bookkeeping; see below)
``SymbolTable#csr?``                    ``SymbolTable.csr_exists()``
``SymbolTable#csr_hash``                ``SymbolTable.csr_hash`` (property, read-only mapping)
``SymbolTable#csr``                     ``SymbolTable.csr()``
``SymbolTable#param``                   ``SymbolTable.param()``
``SymbolTable#params_hash``             ``SymbolTable.params_hash`` (property)
``SymbolTable#possible_xlens``          ``SymbolTable.possible_xlens`` (property)
``SymbolTable#multi_xlen?``             ``SymbolTable.multi_xlen`` (property)
``SymbolTable#eval_register_length_idl``  ``IdlEnvironment.eval_register_length`` (injected callable)
======================================  =========================================

Deviations from Ruby (semantics)
---------------------------------

1. **No clone pool, no semaphore, no ``deep_freeze``.** Ruby's
   ``global_clone`` hands out pre-allocated ``SymbolTable`` copies from
   ``@global_clone_pool`` (growing it 5-at-a-time via
   ``SymbolTable.allocate`` + ``instance_variable_set``), guarded by a
   ``Concurrent::Semaphore`` per clone and a ``Thread::Mutex`` on
   ``release``; ``deep_freeze`` is what originally seeds that pool. Per
   ``doc/stage4-idl.md``, none of that is ported: ``global_clone()`` always
   returns a brand-new, independent ``SymbolTable`` with copied global
   bindings and mutable values (see point 3).
   ``release()`` is kept only as a documented no-op for call-site API
   parity (a caller that used to write ``symtab.release`` after finishing
   with a clone can still call it; it does nothing because there is no pool
   to return the clone to, and Python's GC reclaims it once unreferenced).
   ``in_use?``/``deep_freeze`` are not ported at all — there is no
   equivalent state to query.

2. **Independent memoization.** Both cloning methods copy their memo
   state and cached parameter mappings. Immutable architecture metadata
   and callback hooks remain shared; warming or mutating a table's caches
   does not change another table.

3. **Independent mutable scopes.** The Stage 4 contract deliberately does
   not reproduce Ruby's shared global dict or shallow binding aliases.
   Clones copy every scope, mutable ``Var`` and nested value container,
   including globals. Immutable types and source objects remain shared.
   ``FunctionType`` signatures retain their AST but bind to the cloned
   global context, so function evaluation sees that table's globals.

4. **``Var`` stays mutable.** Unlike ``Type``, ``Var`` is not made
   immutable: IDL's compile-time evaluator needs ``var.value = new_value``
   to model assignment (mirroring Ruby's ``Var#value=``). ``Var.type`` is
   safe to share freely since :class:`~udb.idl.types.Type` is itself
   immutable, so (unlike Ruby, which calls ``@type.freeze`` defensively in
   ``Var#initialize``) there is nothing to freeze here.

5. **``Var`` does not override ``__eq__``/``__hash__``.** Ruby's ``Var#hash``
   is ``[@name, @type, @value, @decode_var, @function_name, @param].hash``
   — a *structural* hash that ignores object identity. Ruby's
   ``SymbolTable#snapshot_values`` builds a plain ``Hash`` keyed by ``Var``
   objects using that structural hash/``eql?``; two distinct ``Var``
   instances that happen to have the same name/type/value/decode_var/
   function_name/param at snapshot time would collide as the *same* hash
   key, silently dropping one of them from the snapshot (and then
   ``restore_values`` would restore the wrong instance's value, or fail to
   restore one of the two vars). We did not confirm this is reachable in
   practice — scope dicts normally hold at most one ``Var`` per name so
   colliding entries would need different names but identical
   type/value/decode_var/function_name/param, and to be looked up together
   via the *same* snapshot — but it is a latent hazard we chose not to
   reproduce. Python's ``Var`` uses default identity-based ``__eq__``/
   ``__hash__`` (no override), and ``snapshot_values()``/``restore_values()``
   here use a ``list[tuple[Var, object]]`` (not a dict keyed by ``Var``) so
   there is no possibility of key collision regardless.

6. **``Var#to_cxx``, ``SymbolTable#print``, ``SymbolTable#inspect`` are not
   ported.** These are backend/debugging conveniences (a C++ codegen hook
   and two pretty-printers) with no semantic content; a later slice can add
   them trivially against whatever repr conventions it wants if needed.

7. **The ``@global`` dead code in ``Var#const_eval?`` is not ported.**
   Ruby's ``const_eval?`` branches on ``@global``, an instance variable
   that ``Var#initialize`` *never sets* (there is no ``global:`` keyword
   argument) — so ``@global`` is always ``nil``/falsy and the ``if @global``
   branch (``@name[0].upcase == @name[0]``) is unreachable dead code. Only
   the reachable ``else`` branch (return ``@const_compatible``) is ported,
   as ``Var.const_eval``.

8. **The architecture/config environment is an explicit, injected value.**
   Ruby's ``SymbolTable#initialize`` takes loose keyword arguments
   (``mxlen:``, ``possible_xlens_cb:``, ``csrs:``, ``params:``,
   ``register_files:``, ``register_file_max_widths:``, ...) built ad hoc by
   whatever caller constructs the table (normally ``Architecture``/
   ``Udb::Cfg``). Here they are bundled into one :class:`IdlEnvironment`
   value (a frozen dataclass) so ``SymbolTable.__init__`` has a single,
   explicit, structurally-typed argument and this module never imports
   ``udb.architecture``.

9. **``eval_register_length_idl`` becomes an injectable callable, not a
   private method that "compiles" a literal string with regexes.** Ruby's
   version is not real IDL compilation — it strips ``return``/``;`` and
   pattern-matches an integer literal or the identifier ``MXLEN`` (falling
   back to the raw expression string for anything else — e.g. a parameter
   name). We port the exact same regex heuristic as the *default* value of
   ``IdlEnvironment.eval_register_length`` (see ``_default_eval_register_length``)
   so behavior matches out of the box, but callers (in particular the
   architecture-integration slice, once real IDL evaluation exists) can
   supply a different callable — e.g. one that actually compiles and
   evaluates the register-length IDL expression against a parameter table —
   without this module needing to change.

Ruby oddities noted but not treated as bugs
--------------------------------------------

- See deviation 5 (``Var`` structural hash collision hazard in
  ``snapshot_values``) above.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .errors import IdlError, IdlInternalError
from .source import IdlSource
from .types import (
    BOOL_TYPE,
    CsrLike,
    EnumerationType,
    FunctionType,
    Qualifier,
    RegFileElementType,
    Type,
    TypeKind,
)

__all__ = [
    "BuiltinFunctionCallbacks",
    "DuplicateSymbolError",
    "EnumDef",
    "IdlEnvironment",
    "ImplementedCallback",
    "ImplementedCsrCallback",
    "ImplementedVersionCallback",
    "PossibleXlensCallback",
    "RegisterFileLike",
    "RuntimeParamLike",
    "SchemaLike",
    "SymbolTable",
    "Var",
]


class DuplicateSymbolError(IdlError):
    """Raised by ``add_unique``/``add_above_unique``/``add_at_unique`` on a name collision.

    Mirrors ``Idl::SymbolTable::DuplicateSymError``.
    """


@runtime_checkable
class SchemaLike(Protocol):
    """Structural counterpart of Ruby's ``Idl::Schema`` interface module."""

    @property
    def max_val_known(self) -> bool: ...
    @property
    def max_val(self) -> int: ...
    @property
    def min_val_known(self) -> bool: ...
    @property
    def min_val(self) -> int: ...
    @property
    def to_idl_type(self) -> Type: ...


@runtime_checkable
class RuntimeParamLike(Protocol):
    """Structural counterpart of Ruby's ``Idl::RuntimeParam`` interface module."""

    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def schema(self) -> SchemaLike: ...
    @property
    def value_known(self) -> bool: ...
    @property
    def value(self) -> object: ...
    @property
    def idl_type(self) -> Type: ...


@runtime_checkable
class RegisterFileLike(Protocol):
    """Structural counterpart of the register-file YAML object Ruby's ``SymbolTable#initialize`` reads.

    Ruby reads ``rf.name``, ``rf.register_length`` (an IDL function-body
    string like ``"return 64;"``), and ``rf.registers.count`` (the number
    of registers in the file, i.e. the array width).
    """

    @property
    def name(self) -> str: ...
    @property
    def register_length(self) -> str: ...
    @property
    def registers(self) -> Sequence[object]: ...


class Var:
    """A compile-time variable binding (``Idl::Var``).

    Unlike :class:`~udb.idl.types.Type`, ``Var`` is intentionally mutable:
    ``value`` may be reassigned to model IDL compile-time assignment. See
    the module docstring (deviations 4-5) for what was *not* ported
    (``to_cxx``, structural ``__eq__``/``__hash__``).
    """

    __slots__ = (
        "_const_compatible",
        "decode_var",
        "for_loop_iter",
        "function_name",
        "name",
        "param",
        "type",
        "value",
    )

    def __init__(
        self,
        name: str,
        type_: Type,
        value: object = None,
        *,
        decode_var: bool = False,
        function_name: str | None = None,
        param: bool = False,
        for_loop_iter: bool = False,
    ) -> None:
        if not isinstance(type_, Type):
            raise IdlInternalError(f"Expecting a Type, got {type(type_).__name__}")
        self.name = name
        self.type = type_
        self.value = value
        self.decode_var = decode_var
        self.function_name = function_name
        self.param = param
        self.for_loop_iter = for_loop_iter
        self._const_compatible = True  # until otherwise known

    def const_incompatible(self) -> None:
        """Mark this ``Var`` as no longer usable in a ``const`` context. Mirrors ``const_incompatible!``."""
        self._const_compatible = False

    @property
    def const_eval(self) -> bool:
        """Whether this ``Var``'s current value may be used in a ``const`` expression.

        Mirrors ``Var#const_eval?``. See module docstring deviation 7 for
        the Ruby dead-code branch (``@global``) intentionally not ported.
        """
        return self._const_compatible

    @property
    def is_const(self) -> bool:
        """Mirrors ``Var#const?``."""
        return self.type.is_const

    @property
    def decode_var_(self) -> bool:
        """Mirrors ``Var#decode_var?``. Prefer the ``decode_var`` field directly; kept for parity."""
        return self.decode_var

    @property
    def param_(self) -> bool:
        """Mirrors ``Var#param?``. Prefer the ``param`` field directly; kept for parity."""
        return self.param

    @property
    def for_loop_iter_(self) -> bool:
        """Mirrors ``Var#for_loop_iter?``. Prefer the ``for_loop_iter`` field directly; kept for parity."""
        return self.for_loop_iter

    def clone(self) -> Var:
        """Return an independent copy of this ``Var``. Mirrors ``Var#clone``.

        Deviation: since :class:`~udb.idl.types.Type` is immutable in this
        port, ``self.type`` needs no cloning (Ruby calls ``type.clone`` to
        avoid aliasing a *mutable* ``Type``; that concern doesn't apply
        here). ``self.value`` is shallow-copied with :func:`copy.copy` when
        not ``None``, matching Ruby's ``value&.clone``. Like Ruby,
        ``for_loop_iter`` is intentionally *not* propagated to the clone
        (Ruby's ``Var#clone`` doesn't pass ``for_loop_iter:`` either).
        """
        return Var(
            self.name,
            self.type,
            copy.copy(self.value) if self.value is not None else None,
            decode_var=self.decode_var,
            function_name=self.function_name,
            param=self.param,
        )

    def __str__(self) -> str:
        value_str = "NO VALUE" if self.value is None else str(self.value)
        return f"VAR: {self.type} {self.name} {value_str}"

    def __repr__(self) -> str:
        return f"Var({self.name!r}, {self.type!r}, {self.value!r})"


@dataclass(frozen=True, slots=True)
class EnumDef:
    """A builtin enum definition to seed into a :class:`SymbolTable`'s global scope.

    Mirrors ``Idl::SymbolTable::EnumDef``.
    """

    name: str
    element_values: tuple[int, ...]
    element_names: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "element_values", tuple(self.element_values))
        object.__setattr__(self, "element_names", tuple(self.element_names))
        if len(self.element_values) != len(self.element_names):
            raise IdlInternalError("element_values and element_names are not the same size")


#: Mirrors ``Idl::SymbolTable::PossibleXlensCallbackType``.
PossibleXlensCallback = Callable[[], Sequence[int]]

#: Mirrors ``Idl::SymbolTable::ImplementedCallbackType``.
ImplementedCallback = Callable[[str], bool | None]

#: Mirrors ``Idl::SymbolTable::ImplementedVersionCallbackType``.
ImplementedVersionCallback = Callable[[str, str], bool | None]

#: Mirrors ``Idl::SymbolTable::ImplementedCsrCallbackType``.
ImplementedCsrCallback = Callable[[int], bool | None]


@dataclass(frozen=True, slots=True)
class BuiltinFunctionCallbacks:
    """Bundles the three "is this implemented" callbacks builtin IDL functions use.

    Mirrors ``Idl::SymbolTable::BuiltinFunctionCallbacks``.
    """

    implemented: ImplementedCallback
    implemented_version: ImplementedVersionCallback
    implemented_csr: ImplementedCsrCallback


#: Matches Ruby's ``eval_register_length_idl`` literal-integer case.
_LITERAL_WIDTH_RE = re.compile(r"\A\d+\Z")
#: Matches Ruby's ``eval_register_length_idl`` ``MXLEN``-reference case.
_MXLEN_WIDTH_RE = re.compile(r"\AMXLEN\Z")


def _default_eval_register_length(idl_body: str, mxlen: int | None) -> int | str:
    """Default ``IdlEnvironment.eval_register_length``: a literal/``MXLEN`` regex heuristic.

    Port of ``SymbolTable#eval_register_length_idl``. Not real IDL
    compilation — see module docstring deviation 9. Strips a leading
    ``return`` and trailing ``;`` then recognizes a bare integer literal or
    the identifier ``MXLEN``; anything else (e.g. a parameter name) is
    returned unevaluated as a string, matching Ruby exactly.
    """
    expr = idl_body.strip()
    expr = re.sub(r"\Areturn\s+", "", expr)
    expr = re.sub(r";\Z", "", expr)
    expr = expr.strip()
    if _LITERAL_WIDTH_RE.match(expr):
        return int(expr)
    if _MXLEN_WIDTH_RE.match(expr):
        return mxlen if mxlen is not None else 64
    return expr


@dataclass(frozen=True, slots=True)
class IdlEnvironment:
    """The architecture/config context a :class:`SymbolTable` is built from.

    Bundles everything Ruby's ``SymbolTable#initialize`` reached into an
    ``Architecture``/``Udb::Cfg`` for (params, CSRs, register files,
    builtin globals/enums/functions, ``mxlen``, ``possible_xlens``). See
    module docstring deviation 8. All fields are optional/defaulted so a
    minimal environment (e.g. for unit tests) can be built with no
    arguments.
    """

    mxlen: int | None = None
    possible_xlens_cb: PossibleXlensCallback | None = None
    builtin_global_vars: tuple[Var, ...] = ()
    builtin_enums: tuple[EnumDef, ...] = ()
    builtin_funcs: BuiltinFunctionCallbacks | None = None
    csrs: tuple[CsrLike, ...] = ()
    params: tuple[RuntimeParamLike, ...] = ()
    name: str = ""
    register_files: tuple[RegisterFileLike, ...] = ()
    register_file_max_widths: dict[str, int] = field(default_factory=dict)
    eval_register_length: Callable[[str, int | None], int | str] = _default_eval_register_length

    def __post_init__(self) -> None:
        object.__setattr__(self, "builtin_global_vars", tuple(self.builtin_global_vars))
        object.__setattr__(self, "builtin_enums", tuple(self.builtin_enums))
        object.__setattr__(self, "csrs", tuple(self.csrs))
        object.__setattr__(self, "params", tuple(self.params))
        object.__setattr__(self, "register_files", tuple(self.register_files))


class _Memo:
    """Mutable memoization cache for ``possible_xlens``/``params_hash``. Mirrors ``MemoizedState``."""

    __slots__ = ("params_hash", "possible_xlens")

    def __init__(
        self,
        possible_xlens: tuple[int, ...] | None = None,
        params_hash: dict[str, RuntimeParamLike] | None = None,
    ) -> None:
        self.possible_xlens = possible_xlens
        self.params_hash = params_hash

    def copy(self) -> _Memo:
        """A new ``_Memo`` with the same current values (Ruby's ``@memo.dup``)."""
        return _Memo(
            self.possible_xlens, None if self.params_hash is None else dict(self.params_hash)
        )


def _clone_binding(value: object, memo: dict[int, object]) -> object:
    """Copy mutable bindings/containers while retaining immutable semantic objects."""
    if id(value) in memo:
        return memo[id(value)]
    if isinstance(value, (Type, IdlSource)):
        return value
    if isinstance(value, Var):
        result = copy.copy(value)
        memo[id(value)] = result
        result.value = _clone_binding(value.value, memo)
        return result
    if isinstance(value, list):
        result = []
        memo[id(value)] = result
        result.extend(_clone_binding(element, memo) for element in value)
        return result
    if isinstance(value, dict):
        result = {}
        memo[id(value)] = result
        result.update(
            (_clone_binding(key, memo), _clone_binding(element, memo))
            for key, element in value.items()
        )
        return result
    if isinstance(value, tuple):
        result = tuple(_clone_binding(element, memo) for element in value)
        memo[id(value)] = result
        return result
    return copy.deepcopy(value, memo)


def _unchanged(value: object, original: object) -> bool:
    """Whether a binding copied from ``original`` still has identical state."""
    return (
        type(value) is Var
        and type(original) is Var
        and value.value is original.value
        and value.type is original.type
        and value._const_compatible is original._const_compatible
        and value.param is original.param
        and value.decode_var is original.decode_var
        and value.function_name is original.function_name
        and value.for_loop_iter is original.for_loop_iter
        and value.name is original.name
    )


class _GlobalScope:
    """Global bindings that are copied from an immutable base on first access.

    A clone shares its source's frozen ``base`` and copies a binding only
    when it is read or replaced. Each table therefore still owns independent
    mutable ``Var`` objects and ``FunctionType`` bindings bound to itself,
    while cloning costs time proportional to the bindings that differ from
    the base rather than to the size of the global scope.
    """

    __slots__ = ("_base", "_deleted", "_lazy", "_memo", "_own", "_table")

    def __init__(
        self,
        table: SymbolTable,
        own: dict[str, object] | None = None,
        base: dict[str, object] | None = None,
    ) -> None:
        self._table = table
        self._base: dict[str, object] = {} if base is None else base
        self._own: dict[str, object] = {} if own is None else own
        self._lazy: set[str] = set()
        self._deleted: set[str] = set()
        self._memo: dict[int, object] = {}

    def _materialize(self, name: str) -> object | None:
        if name in self._deleted:
            return None
        value = self._base.get(name)
        if value is None:
            return None
        if isinstance(value, FunctionType):
            if value._symtab is not self._table:
                value = value.bound_to(self._table)
        elif isinstance(value, (Type, IdlSource)):
            return value
        else:
            value = _clone_binding(value, self._memo)
        self._own[name] = value
        self._lazy.add(name)
        return value

    def get(self, name: str, default: object | None = None) -> object | None:
        value = self._own.get(name)
        if value is None and name not in self._own:
            value = self._materialize(name)
            if value is None:
                return default
        return value

    def __contains__(self, name: object) -> bool:
        return name in self._own or (name in self._base and name not in self._deleted)

    def __getitem__(self, name: str) -> object:
        if name not in self:
            raise KeyError(name)
        return self.get(name)

    def __setitem__(self, name: str, value: object) -> None:
        self._own[name] = value
        self._lazy.discard(name)
        self._deleted.discard(name)

    def __delitem__(self, name: str) -> None:
        if name not in self:
            raise KeyError(name)
        self._own.pop(name, None)
        self._lazy.discard(name)
        if name in self._base:
            self._deleted.add(name)

    def keys(self) -> list[str]:
        own = self._own
        deleted = self._deleted
        keys = [name for name in self._base if name not in deleted]
        keys.extend(name for name in own if name not in self._base)
        return keys

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    def values(self) -> list[object]:
        return [self.get(name) for name in self.keys()]

    def items(self) -> list[tuple[str, object]]:
        return [(name, self.get(name)) for name in self.keys()]

    def freeze(self) -> None:
        """Make the current bindings the shared base of this table and its clones."""
        merged = {name: value for name, value in self._base.items() if name not in self._deleted}
        merged.update(self._own)
        self._base = merged
        self._own = {}
        self._lazy = set()
        self._deleted = set()
        self._memo = {}

    def clone(self, table: SymbolTable, memo: dict[int, object]) -> _GlobalScope:
        result = _GlobalScope(table, base=self._base)
        result._deleted = set(self._deleted)
        for name, value in self._own.items():
            if name in self._lazy and (
                isinstance(value, FunctionType) or _unchanged(value, self._base.get(name))
            ):
                continue
            result._own[name] = (
                value.bound_to(table)
                if isinstance(value, FunctionType)
                else _clone_binding(value, memo)
            )
        return result


class SymbolTable:
    """A scoped symbol table holding known symbols at a point during IDL compilation.

    Mirrors ``Idl::SymbolTable``. See the module docstring for the full
    Ruby -> Python mapping and documented deviations (no clone pool/
    semaphore; architecture context is an injected :class:`IdlEnvironment`).
    """

    def __init__(self, environment: IdlEnvironment | None = None) -> None:
        env = environment if environment is not None else IdlEnvironment()
        self._env = env
        self._mxlen = env.mxlen
        self._name = env.name
        self._callstack: list[object | None] = [None]
        self._memo = _Memo()

        scope0: dict[str, object] = {
            "Boolean": BOOL_TYPE,
            "true": Var("true", BOOL_TYPE, True),
            "false": Var("false", BOOL_TYPE, False),
        }
        self._scopes: list[dict[str, object]] = [_GlobalScope(self, scope0)]  # type: ignore[list-item]

        for rf in env.register_files:
            if rf.name in env.register_file_max_widths:
                int_width = env.register_file_max_widths[rf.name]
            else:
                width = env.eval_register_length(rf.register_length, self._mxlen)
                if not isinstance(width, int):
                    raise IdlInternalError(
                        f"Cannot determine max register width for '{rf.name}'. "
                        "Pass register_file_max_widths= to IdlEnvironment."
                    )
                int_width = width
            elem_type = RegFileElementType(rf.name, int_width, max_width=int_width)
            array_type = Type(
                TypeKind.ARRAY,
                sub_type=elem_type,
                width=len(rf.registers),
                qualifiers=(Qualifier.GLOBAL,),
            )
            scope0[rf.name] = Var(rf.name, array_type)
            scope0[f"{rf.name}Reg"] = elem_type

        for builtin_var in env.builtin_global_vars:
            self.add_unique(builtin_var.name, _clone_binding(builtin_var, {}))
        for enum_def in env.builtin_enums:
            self.add_unique(
                enum_def.name,
                EnumerationType(
                    enum_def.name, enum_def.element_names, enum_def.element_values, builtin=True
                ),
            )

        self._builtin_funcs = env.builtin_funcs
        self._csrs = tuple(env.csrs)
        csr_hash: dict[str, CsrLike] = {}
        for csr in self._csrs:
            csr_hash[csr.name] = csr
        self._csr_hash = csr_hash

    # -- basic accessors -------------------------------------------------

    @property
    def mxlen(self) -> int | None:
        return self._mxlen

    @property
    def name(self) -> str:
        return self._name

    @property
    def builtin_funcs(self) -> BuiltinFunctionCallbacks | None:
        return self._builtin_funcs

    @property
    def possible_xlens(self) -> tuple[int, ...]:
        """Mirrors ``SymbolTable#possible_xlens``."""
        if self._memo.possible_xlens is None:
            if self._env.possible_xlens_cb is None:
                raise IdlInternalError(
                    "Symbol table was not initialized with a possible xlens callback, "
                    "so possible_xlens is not available"
                )
            self._memo.possible_xlens = tuple(self._env.possible_xlens_cb())
        return self._memo.possible_xlens

    @property
    def multi_xlen(self) -> bool:
        """Mirrors ``SymbolTable#multi_xlen?``."""
        return len(self.possible_xlens) > 1

    # -- CSRs --------------------------------------------------------------

    def csr_exists(self, csr_name: str) -> bool:
        """Mirrors ``SymbolTable#csr?``."""
        return csr_name in self._csr_hash

    @property
    def csr_hash(self) -> dict[str, CsrLike]:
        """Mirrors ``SymbolTable#csr_hash``. Returns the live mapping (Ruby exposes it directly too)."""
        return self._csr_hash

    def csr(self, csr_name: str) -> CsrLike | None:
        """Mirrors ``SymbolTable#csr``."""
        return self._csr_hash.get(csr_name)

    # -- params --------------------------------------------------------------

    @property
    def params_hash(self) -> dict[str, RuntimeParamLike]:
        """Mirrors ``SymbolTable#params_hash``."""
        if self._memo.params_hash is None:
            self._memo.params_hash = {p.name: p for p in self._env.params}
        return self._memo.params_hash

    def param(self, param_name: str) -> RuntimeParamLike | None:
        """Mirrors ``SymbolTable#param``."""
        return self.params_hash.get(param_name)

    # -- scope stack -------------------------------------------------------

    def push(self, ast: object | None = None) -> SymbolTable:
        """Push a new (empty) scope. Mirrors ``SymbolTable#push``."""
        self._scopes.append({})
        self._callstack.append(ast)
        return self

    def pop(self) -> None:
        """Pop the innermost scope. Mirrors ``SymbolTable#pop``."""
        if len(self._scopes) == 1:
            raise IdlInternalError("popping the symbol table would remove global scope")
        self._scopes.pop()
        self._callstack.pop()

    @property
    def callstack(self) -> str:
        """Mirrors ``SymbolTable#callstack``.

        Renders each pushed scope's associated AST node as
        ``{input_file}:{lineno}`` (or ``""`` for ``None``, e.g. the
        always-present global-scope entry), most-recent first. Uses
        ``getattr`` rather than a ``Protocol`` since this is purely a
        diagnostic string and any future AST node need only expose these
        two attributes.
        """
        lines: list[str] = []
        for ast in reversed(self._callstack):
            if ast is None:
                lines.append("")
            else:
                input_file = getattr(ast, "input_file", None)
                lineno = getattr(ast, "lineno", None)
                lines.append(f"{input_file}:{lineno}")
        return "\n".join(lines)

    @property
    def levels(self) -> int:
        """Mirrors ``SymbolTable#levels``."""
        return len(self._scopes)

    @property
    def at_global_scope(self) -> bool:
        """Mirrors ``SymbolTable#at_global_scope?``."""
        return len(self._scopes) == 1

    # -- lookup --------------------------------------------------------------

    def has_key(self, name: str) -> bool:
        """Mirrors ``SymbolTable#key?``."""
        return any(name in scope for scope in self._scopes)

    def __contains__(self, name: str) -> bool:
        return self.has_key(name)

    def keys_pretty(self) -> list[list[str]]:
        """Mirrors ``SymbolTable#keys_pretty``."""
        return [list(scope.keys()) for scope in self._scopes]

    def get(self, name: str) -> object | None:
        """Mirrors ``SymbolTable#get``: search scope-by-scope, innermost first."""
        for scope in reversed(self._scopes):
            value = scope.get(name)
            if value is not None:
                return value
        return None

    def get_from(self, name: str, level: int) -> object | None:
        """Mirrors ``SymbolTable#get_from``."""
        if level <= 0:
            raise IdlInternalError("level must be positive")
        if level >= self.levels:
            raise IdlInternalError(f"There is no level {level}")
        for scope in reversed(self._scopes[0:level]):
            if name in scope:
                return scope[name]
        return None

    def get_global(self, name: str) -> object | None:
        """Mirrors ``SymbolTable#get_global``."""
        return self.get_from(name, 1)

    def find_all(
        self, predicate: Callable[[object], bool], *, single_scope: bool = False
    ) -> list[object]:
        """Mirrors ``SymbolTable#find_all``."""
        matches: list[object] = []
        for scope in reversed(self._scopes):
            for value in scope.values():
                if predicate(value):
                    matches.append(value)
            if single_scope and matches:
                break
        return matches

    # -- mutation --------------------------------------------------------------

    def add(self, name: str, value: object) -> None:
        """Add (or overwrite) a symbol at the innermost scope. Mirrors ``SymbolTable#add``."""
        self._scopes[-1][name] = value

    def defined_in_current_scope(self, name: str) -> bool:
        """Whether a declaration would replace a binding in its own scope."""
        return name in self._scopes[-1]

    def add_unique(self, name: str, value: object) -> None:
        """Like :meth:`add`, but raises if ``name`` is already defined at any scope.

        Mirrors ``SymbolTable#add!``.
        """
        if any(name in scope for scope in self._scopes):
            raise DuplicateSymbolError(f"Symbol {name} already defined as {self.get(name)}")
        self._scopes[-1][name] = value

    def delete(self, name: str) -> None:
        """Delete a symbol from the innermost scope. Mirrors ``SymbolTable#del``."""
        if name not in self._scopes[-1]:
            raise IdlInternalError(f"No symbol {name} at outer scope")
        del self._scopes[-1][name]

    def add_above_unique(self, name: str, value: object) -> None:
        """Add to the scope above the innermost one, unique across all scopes but the innermost.

        Mirrors ``SymbolTable#add_above!``.
        """
        if len(self._scopes) <= 1:
            raise IdlInternalError("There is only one scope")
        if any(name in scope for scope in self._scopes[:-1]):
            raise IdlInternalError(f"Symbol {name} already defined")
        self._scopes[-2][name] = value

    def add_at_unique(self, level: int, name: str, value: object) -> None:
        """Add at a specific scope level, unique across scopes below it. Mirrors ``SymbolTable#add_at!``."""
        if level >= len(self._scopes):
            raise IdlInternalError(f"Level {level} is too large {len(self._scopes)}")
        if any(name in scope for scope in self._scopes[:level]):
            raise IdlInternalError(f"Symbol {name} already defined")
        self._scopes[level][name] = value

    # -- snapshotting --------------------------------------------------------------

    def snapshot_values(self) -> list[tuple[Var, object]]:
        """Capture the current value of every ``Var`` in non-global scopes.

        Mirrors ``SymbolTable#snapshot_values``. Deviation: returns a
        ``list[tuple[Var, object]]`` rather than a ``Hash``/``dict`` keyed
        by ``Var`` -- see module docstring deviation 5 (avoids a structural-
        hash-collision hazard present in the Ruby original).
        """
        snapshot: list[tuple[Var, object]] = []
        for scope in self._scopes[1:]:
            for value in scope.values():
                if isinstance(value, Var):
                    snapshot.append((value, value.value))
        return snapshot

    def restore_values(self, snapshot: Iterable[tuple[Var, object]]) -> None:
        """Restore ``Var`` values from a snapshot produced by :meth:`snapshot_values`."""
        for var, value in snapshot:
            var.value = value

    # -- cloning --------------------------------------------------------------

    def global_clone(self) -> SymbolTable:
        """Return an independent table containing only copied global bindings."""
        return self._clone_scopes(self._scopes[:1], self._callstack[:1])

    def _clone_scopes(
        self, scopes: Sequence[dict[str, object]], callstack: Sequence[object | None]
    ) -> SymbolTable:
        clone = object.__new__(SymbolTable)
        clone._callstack = list(callstack)
        clone._mxlen = self._mxlen
        clone._name = self._name
        clone._memo = self._memo.copy()
        clone._env = self._env
        clone._builtin_funcs = self._builtin_funcs
        clone._csrs = self._csrs
        clone._csr_hash = dict(self._csr_hash)
        memo: dict[int, object] = {}
        clone._scopes = [scopes[0].clone(clone, memo)]  # type: ignore[attr-defined]
        clone._scopes.extend(
            {key: _clone_binding(value, memo) for key, value in scope.items()}
            for scope in scopes[1:]
        )
        return clone

    def freeze_globals(self) -> None:
        """Share the current global bindings with later clones without copying them.

        The table and each clone still receive independent copies of mutable
        bindings when they first access them, so callers must not retain
        global ``Var`` objects obtained before freezing.
        """
        self._scopes[0].freeze()  # type: ignore[attr-defined]

    def release(self) -> None:
        """No-op. Mirrors ``SymbolTable#release``; see module docstring deviation 1."""

    def deep_clone(self, *, clone_values: bool = True) -> SymbolTable:
        """Return independent scopes, bindings and nested values.

        ``clone_values`` is retained for API compatibility. Mutable values
        are always isolated, including when a legacy caller passes ``False``.
        """
        return self._clone_scopes(self._scopes, self._callstack)

    def __repr__(self) -> str:
        return f"SymbolTable[{self._name}]"
