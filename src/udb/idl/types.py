# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Python port of the IDL semantic type system (Ruby ``idlc/lib/idlc/type.rb``).

This module has no dependency on ``udb.idl.parser``/``udb.idl.ast`` (still
being written on ``migration/python-13-idl-syntax``) or on ``udb.architecture``.
Anywhere the Ruby implementation reached into an AST node or an architecture
object, this module instead declares a small ``typing.Protocol`` describing
exactly the members used, so the real classes (``FunctionDefAst``, ``Csr``,
``CsrField``, ...) can satisfy the protocol structurally once they exist.

Ruby -> Python surface mapping
-------------------------------

======================================  =========================================
Ruby (``type.rb``)                     Python (this module)
======================================  =========================================
``Idl::Type::KINDS``                    ``TypeKind`` (``StrEnum``)
``Idl::Type::QUALIFIERS``               ``Qualifier`` (``StrEnum``)
``Type#kind``                           ``Type.kind``
``Type#qualifiers``                     ``Type.qualifiers`` (``tuple[Qualifier, ...]``)
``Type#width``                          ``Type.width`` (raises if unset, like ``T.must``)
``Type#width_ast``                      ``Type.width_ast``
``Type#max_width``                      ``Type.max_width``
``Type#sub_type``                       ``Type.sub_type`` (raises if unset)
``Type#tuple_types``                    ``Type.tuple_types`` (raises if unset)
``Type#enum_class``                     ``Type.enum_class`` (raises if unset)
``Type#integral?``                      ``Type.is_integral``
``Type#runtime?``                       ``Type.is_runtime``
``Type#ary?``                           ``Type.is_array``
``Type#const?`` / ``#mutable?``         ``Type.is_const`` / ``Type.is_mutable``
``Type#signed?``                        ``Type.is_signed``
``Type#global?``                        ``Type.is_global``
``Type#known?``                         ``Type.is_known``
``Type#default``                        ``Type.default()``
``Type#name``                           ``Type.name`` (property; dispatches on ``kind``)
``Type#to_s`` / ``#fully_qualified_name``  ``Type.__str__`` / ``Type.fully_qualified_name()``
``Type#to_idl``                         ``Type.to_idl()``
``Type#comparable_to?``                 ``Type.comparable_to()``
``Type#equal_to?``                      ``Type.equal_to()``
``Type#convertable_to?``                ``Type.convertable_to()``
``Type#ary_type``                       ``Type.ary_type()``
``Type#qualify``                        ``Type.qualify()`` (returns a new ``Type``)
``Type#make_const!`` / ``#make_const``  ``Type.make_const()`` (returns a new ``Type``)
``Type#make_signed``                    ``Type.make_signed()`` (returns a new ``Type``)
``Type#make_global``                    ``Type.make_global()`` (returns a new ``Type``)
``Type#make_known``                     ``Type.make_known()`` (returns a new ``Type``)
``Type.unsigned_bits_needed``           ``_unsigned_bits_needed()`` (module-private)
``Type.from_json_schema_scalar_type``   ``_from_json_schema_scalar_type()`` (module-private)
``Type.merge_json_schema_scalar_types`` ``_merge_json_schema_scalar_types()`` (module-private)
``Type.from_json_schema_array_type``    ``_from_json_schema_array_type()`` (module-private)
``Type.from_json_schema``               ``Type.from_json_schema()`` (classmethod)
``StructType``                          ``StructType``
``EnumerationType``                     ``EnumerationType``
``BitfieldType``                        ``BitfieldType``
``CsrType``                             ``CsrType``
``FunctionType``                        ``FunctionType``
``RegFileElementType`` / ``XregType``   ``RegFileElementType`` / ``XregType``
``Bits1Type``, ``Bits32Type``, ...      ``BITS1_TYPE``, ``BITS32_TYPE``, ... (module constants)
======================================  =========================================

Deviations from Ruby (semantics)
---------------------------------

1. **Value semantics, not mutation.** Ruby's ``Type`` is a plain mutable
   object; ``qualify``, ``make_const!``, ``make_signed``, ``make_global``,
   and ``make_known`` mutate ``@qualifiers`` in place and return ``self``.
   Here every ``Type`` is immutable (custom ``__setattr__`` raises after
   construction) and each of those methods returns a **new** ``Type`` with
   the qualifier added, built via a private ``_replace()`` helper
   (``copy.copy`` + ``__setstate__``, bypassing the frozen guard). Ruby's
   ``make_const`` (clone-then-mutate, non-bang) and ``make_const!``
   (mutate-in-place) collapse to the single method ``make_const()`` since
   there is no meaningful difference once values are immutable. Ruby's
   ``Type#clone`` (and the ``StructType``/``EnumerationType``/
   ``BitfieldType``/``FunctionType`` overrides of it) exist only to avoid
   aliasing a mutable ``Type``; because ``Type`` is frozen here, no
   ``clone()`` method is ported — sharing a ``Type`` instance is always
   safe.

   **Ruby call sites that relied on the clone-then-mutate/aliasing pattern**
   (for the AST slice to review when porting these nodes):

   - ``ast.rb:3602`` — ``type_name.type(symtab).clone.make_global`` (global
     variable declaration type). Becomes
     ``type_name.type(symtab).make_global()``.
   - ``ast.rb:3902-3910`` (``VariableDeclarationWithInitializationAst#lhs_type``) —
     ``decl_type = type_name.type(symtab).clone`` followed by a loop
     ``qualifiers.each { |q| decl_type.qualify(q) }`` that mutates
     ``decl_type`` in place once per qualifier. Becomes
     ``decl_type = type_name.type(symtab)`` then
     ``for q in qualifiers: decl_type = decl_type.qualify(q)``.
   - ``ast.rb:3936`` / ``ast.rb:3942`` / ``ast.rb:3945`` — each passes
     ``decl_type.clone`` into a new ``Var`` so that later qualifying one
     sibling declaration's type (``Bits<32> a, b;``) can't leak into
     another ``Var``'s type. Becomes passing ``decl_type`` directly.
   - ``ast.rb:4370`` — ``expression.type(symtab).clone.make_signed`` (signed
     cast). Becomes ``expression.type(symtab).make_signed()``.
   - ``ast.rb:6449`` — ``t.make_const!`` (ternary result forced const when
     both branches are const). Becomes ``t = t.make_const()``.

   ``ast.rb:1232`` and ``ast.rb:1309`` also call ``.make_global`` but on an
   *AST node* (``VarDeclarationAst#make_global``, a different, unrelated
   method that just sets an ``@global`` flag on the node itself, not on a
   ``Type``); they are not part of this list.

2. **``Type.name`` field vs. the ``name`` dispatch method.** Ruby's
   ``Type#name`` is a *method* that dispatches on ``kind`` (for ``:bits`` it
   computes ``"Bits<#{width}>"``; for ``:enum``/``:bitfield``/``:function``
   it reads the ``@name`` ivar; for ``:csr``/``:enum_ref`` it delegates).
   Because a Python ``@property`` and a same-named constructor field can't
   coexist cleanly, the raw stored value is the private field ``raw_name``
   and ``name`` is a read-only ``@property`` performing the same dispatch.
   Likewise ``width``, ``sub_type``, ``tuple_types``, and ``enum_class`` are
   private fields (``_width``, ``_sub_type``, ``_tuple_types``,
   ``_enum_class``) exposed by "must be set" properties, mirroring Ruby's
   ``T.must(@width)`` etc.

3. **Hand-written immutable classes, not ``@dataclass``.** Most of this
   codebase uses ``@dataclass(frozen=True, slots=True)`` (see
   ``udb/domains.py``). ``Type`` and its subclasses are hand-written classes
   with ``__slots__`` instead, because: (a) each subclass has its own
   positional constructor mirroring Ruby's ``initialize`` exactly (e.g.
   ``EnumerationType(type_name, element_names, element_values, *,
   builtin=False)``), which does not map onto dataclass field
   *inheritance* without kw-only contortions; and (b)
   ``EnumerationType.ref_type`` is `self`-referential (``ref_type =
   Type(ENUM_REF, enum_class=self)``), which would make a naively
   dataclass-derived structural ``__hash__``/``__eq__`` recurse forever.
   Every subclass still has no public mutator and enforces immutability via
   a shared ``__setattr__`` override.

4. **Equality is two separate, intentional things.** Ruby's ``Type#==`` is a
   narrow, partial implementation: it switches on *``other.kind``* (not
   ``self.kind``!) and only implements ``:bits``/``:enum_ref``, raising for
   every other kind (see ``BUGS`` below). Python's ``__eq__``/``__hash__``
   are a faithful, deliberately-narrow port of that same partial ``==``
   (including its "switch on the other operand's kind" quirk and its raise
   for anything else), used for e.g. ``assert type_a == type_b`` in tests
   that only ever compare ``:bits``/``:enum_ref`` types (mirroring the
   actual Ruby test suite). ``equal_to()`` is the separate, complete port of
   Ruby's ``equal_to?`` (qualifier-blind structural equality), used
   wherever code needs to compare types of any kind. Do not rely on ``==``
   for kinds other than ``bits``/``enum_ref``; use ``equal_to()``.

5. **``Type.from_typename`` is not ported.** It is dead code in Ruby (never
   called anywhere in ``idlc`` or by any other gem), takes a ``cfg_arch``
   (an ``Architecture``), and its regex (``/Bits<((?:0x)?[0-9a-fA-F]+)>/``
   with ``$1.to_i``) mis-parses a hex width like ``"Bits<0x20>"`` as ``0``
   (Ruby's ``String#to_i`` stops at the first non-digit, so ``"0x20".to_i``
   is ``0``, not 32). Porting an unused, architecture-coupled, buggy method
   would add an unwanted ``udb.architecture`` dependency edge for no
   benefit; if a later slice needs it, port it fresh against whatever
   ``cfg_arch``-like protocol that slice defines.

Confirmed Ruby bugs found while porting (kept correct in Python; see
``tests/python/test_idl_types.py`` for regression tests and
``tests/python/ruby_idl_type_oracle.rb`` for the reproductions)
----------------------------------------------------------------

- **B1**: ``Type#equal_to?`` and ``Type#convertable_to?`` coerce a ``Symbol``
  argument via ``TYPE_FROM_KIND[type]``, a hash pre-built for only
  ``:boolean``/``:void``/``:dontcare``. Calling either method with any other
  kind symbol (e.g. ``some_type.convertable_to?(:bits)``) looks up ``nil``
  and then crashes with ``NoMethodError: undefined method 'kind' for nil``.
  ``comparable_to?`` coerces differently (``type = Type.new(type)``, not the
  frozen hash) but is *not* actually safer in practice: ``Type.new(:bits)``
  (no ``width:``) itself raises ``"Bits type must have width"`` in Ruby's own
  constructor (confirmed live), and worse, ``comparable_to?``'s own ``:enum``
  branch (``type.rb`` ~line 222, ``return type.convertable_to?(:bits)``)
  *always* calls ``convertable_to?`` with the bare symbol ``:bits``
  internally -- so **every** call to ``some_enum_type.comparable_to?(x)``
  crashes via the ``TYPE_FROM_KIND`` path today, for *any* ``x``, confirmed
  live: ``enum_type.comparable_to?(bits_type)`` raises the same
  ``NoMethodError: undefined method 'kind' for nil`` as the symbol-argument
  case. This is the most directly reachable manifestation of B1: any
  real-world `EnumerationType#comparable_to?` call is broken in Ruby today.
  Python's ``equal_to()``/``comparable_to()``/``convertable_to()`` all
  coerce a bare ``TypeKind`` via the module-level ``_type_from_kind()``
  helper, which builds a real placeholder ``Type`` for kinds the
  constructor can build without extra data, and special-cases ``BITS``
  with ``width=WIDTH_UNKNOWN`` (a legal placeholder -- every dispatch
  branch that inspects a bare ``:bits`` kind only reads ``rhs.kind``, never
  the placeholder's width), so the internal ``ENUM`` branch of
  ``comparable_to()`` (and any direct caller) works correctly instead of
  crashing.
- **B2**: ``Type#comparable_to?``'s ``:csr`` branch calls
  ``type.csr.width``, but the ``Csr`` interface
  (``idlc/lib/idlc/interfaces.rb``) has no ``width`` method (only
  ``max_length``/``length(base)``). Comparing two *different-named* CSR
  types raises ``NoMethodError: undefined method 'width'``. Python's
  ``comparable_to()`` uses ``other.csr.max_length`` (matching the working
  ``:csr`` branch of ``convertable_to?``, which uses the CSR type's own
  ``width``).
- **B3**: ``Type#default`` for ``:array`` uses Ruby's ``Array.new(width,
  sub_type.default)``, which fills every slot with the *same* default
  object when ``sub_type.default`` returns a mutable value (e.g. a
  ``StructType``'s ``Hash`` default). Mutating one array element's default
  then mutates every element. Python's ``default()`` calls
  ``sub_type.default()`` once per element, producing independent values.

None of these are exercised by ``tools/ruby-gems/idlc/test/test_ast_type.rb``
or ``test_type_to_idl.rb`` (the ported test files), so nothing in the
existing Ruby suite currently depends on the buggy behavior.
"""

from __future__ import annotations

import copy
import warnings
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import (
    Any,
    Final,
    Literal,
    NoReturn,
    Protocol,
    runtime_checkable,
)

from .errors import IdlInternalError

__all__ = [
    "BITS1_TYPE",
    "BITS32_TYPE",
    "BITS64_TYPE",
    "BITS_UNKNOWN_TYPE",
    "BOOL_TYPE",
    "CONST_BITS_UNKNOWN_TYPE",
    "CONST_BOOL_TYPE",
    "POSSIBLY_UNKNOWN_BITS1_TYPE",
    "STRING_TYPE",
    "VOID_TYPE",
    "WIDTH_UNKNOWN",
    "BitfieldType",
    "CsrFieldLike",
    "CsrLike",
    "CsrType",
    "EnumerationType",
    "FunctionBodyLike",
    "FunctionCallLike",
    "FunctionDefinitionLike",
    "FunctionType",
    "Qualifier",
    "RegFileElementType",
    "RvalueLike",
    "StructType",
    "SymbolTableLike",
    "Type",
    "TypeKind",
    "Width",
    "WidthExpression",
    "XregType",
]

#: Sentinel used where Ruby stores the symbol ``:unknown`` as a ``Type``'s width
#: (e.g. a dynamically-sized CSR or register). A plain string, not a dedicated
#: sentinel object, so it round-trips trivially through JSON/YAML in later slices.
WIDTH_UNKNOWN: Final = "unknown"

#: A ``Type``'s width: either a compile-time-known bit count, or ``WIDTH_UNKNOWN``.
Width = int | Literal["unknown"]


class TypeKind(StrEnum):
    """Kinds of IDL type, mirroring ``Idl::Type::KINDS``."""

    VOID = "void"
    BOOLEAN = "boolean"
    BITS = "bits"
    ENUM = "enum"
    ENUM_REF = "enum_ref"
    BITFIELD = "bitfield"
    STRUCT = "struct"
    ARRAY = "array"
    TUPLE = "tuple"
    FUNCTION = "function"
    CSR = "csr"
    DONTCARE = "dontcare"
    STRING = "string"


class Qualifier(StrEnum):
    """Type qualifiers, mirroring ``Idl::Type::QUALIFIERS``."""

    CONST = "const"
    SIGNED = "signed"
    GLOBAL = "global"
    KNOWN = "known"


@runtime_checkable
class WidthExpression(Protocol):
    """A parsed IDL expression whose value determines an unknown-width ``Type``'s width.

    Corresponds to the ``AstNode`` stored in Ruby's ``width_ast`` (set, for
    example, at ``ast.rb:7218``: ``Type.new(:bits, width: :unknown,
    width_ast: bits_expression)``). Nothing in ``Type`` calls a method on
    this value; it is carried only so a later (expression/statement) slice
    can evaluate it. No members are required yet, but the protocol exists so
    call sites can be typed precisely once the AST slice lands.
    """


@runtime_checkable
class CsrFieldLike(Protocol):
    """Structural counterpart of Ruby's ``Idl::CsrField`` interface module."""

    @property
    def name(self) -> str: ...
    def defined_in_all_bases(self) -> bool: ...
    def defined_in_base32(self) -> bool: ...
    def defined_in_base64(self) -> bool: ...
    def defined_in_base(self, xlen: int) -> bool: ...
    def base64_only(self) -> bool: ...
    def base32_only(self) -> bool: ...
    def location(self, base: int | None = None) -> range: ...
    def width(self, base: int | None) -> int: ...
    def field_type(self, base: int | None) -> str | None: ...
    def exists(self) -> bool: ...
    def reset_value(self) -> object: ...


@runtime_checkable
class CsrLike(Protocol):
    """Structural counterpart of Ruby's ``Idl::Csr`` interface module."""

    @property
    def name(self) -> str: ...
    def length(self, base: int | None) -> int | None: ...
    @property
    def max_length(self) -> int: ...
    def dynamic_length(self) -> bool: ...
    @property
    def fields(self) -> Sequence[CsrFieldLike]: ...
    @property
    def value(self) -> int | None: ...


@runtime_checkable
class SymbolTableLike(Protocol):
    """Minimal structural counterpart of ``Idl::SymbolTable`` that ``FunctionType`` needs.

    Kept here (rather than importing ``udb.idl.symbols``) so ``types.py``
    has no dependency direction on ``symbols.py``; ``symbols.SymbolTable``
    satisfies this protocol structurally.
    """

    @property
    def levels(self) -> int: ...
    @property
    def name(self) -> str: ...
    @property
    def mxlen(self) -> int | None: ...
    def global_clone(self) -> SymbolTableLike: ...
    def push(self, ast: object) -> None: ...
    def pop(self) -> None: ...
    def release(self) -> None: ...
    def add(self, name: str, value: object) -> None: ...


@runtime_checkable
class RvalueLike(Protocol):
    """Structural counterpart of an IDL ``Rvalue`` AST node (an argument expression)."""

    def value(self, symtab: SymbolTableLike) -> object: ...


@runtime_checkable
class FunctionCallLike(Protocol):
    """Structural counterpart of ``FunctionCallExpressionAst`` (only what ``FunctionType`` needs)."""

    def type_error(self, reason: str) -> NoReturn: ...


@runtime_checkable
class FunctionBodyLike(Protocol):
    """Structural counterpart of ``FunctionBodyAst`` (only what ``FunctionType`` needs)."""

    def return_value(self, symtab: SymbolTableLike) -> object: ...


@runtime_checkable
class FunctionDefinitionLike(Protocol):
    """Structural counterpart of ``Idl::FunctionDefAst`` (only what ``FunctionType`` needs)."""

    @property
    def argument_nodes(self) -> Sequence[object]: ...
    def builtin(self) -> bool: ...
    def generated(self) -> bool: ...
    def external(self) -> bool: ...
    def num_args(self) -> int: ...
    def arguments(self, symtab: SymbolTableLike) -> Sequence[tuple[Type, str]]: ...
    def return_type(self, symtab: SymbolTableLike) -> Type: ...
    @property
    def body(self) -> FunctionBodyLike: ...


def _dedupe_qualifiers(qualifiers: Sequence[Qualifier]) -> tuple[Qualifier, ...]:
    seen: set[Qualifier] = set()
    ordered: list[Qualifier] = []
    for qualifier in qualifiers:
        if not isinstance(qualifier, Qualifier):
            raise IdlInternalError(f"Invalid qualifier {qualifier!r}")
        if qualifier not in seen:
            seen.add(qualifier)
            ordered.append(qualifier)
    return tuple(ordered)


def _type_from_kind(kind: TypeKind) -> Type:
    """Build a placeholder ``Type`` from a bare ``TypeKind``.

    Used by :meth:`Type.equal_to`, :meth:`Type.comparable_to`, and
    :meth:`Type.convertable_to` to coerce a bare-kind argument (Ruby's
    ``:boolean``/``:bits``-as-symbol calling convention) into a real
    ``Type`` instance. This is deviation (B1) from ``type.rb``: Ruby's
    ``equal_to?``/``convertable_to?`` look the symbol up in the frozen
    ``TYPE_FROM_KIND`` hash (which only contains ``:boolean``, ``:void``,
    ``:dontcare``) and silently get ``nil`` for any other kind, crashing
    later with ``NoMethodError: undefined method 'kind' for nil``. Worse,
    ``comparable_to?``'s own ``:enum`` branch (type.rb ~line 222) always
    calls ``type.convertable_to?(:bits)`` internally -- so *every* call to
    ``comparable_to?`` on an enum type crashes in Ruby today, regardless of
    what is passed in, confirmed live (see stage4 report).

    Python fixes this by constructing a real placeholder ``Type`` for any
    kind the constructor can build without further data (``BOOLEAN``,
    ``VOID``, ``DONTCARE``, ``STRING``, ``ENUM_REF``, ``STRUCT``,
    ``BITFIELD``), and by special-casing ``BITS`` with ``width=WIDTH_UNKNOWN``
    (a legal placeholder width) since every branch that dispatches on a
    bare ``:bits`` kind only inspects ``rhs.kind`` and never the placeholder's
    width. Kinds that Ruby's own constructor could never build from a bare
    kind either (``ENUM``, ``ARRAY``, ``TUPLE``, ``CSR``, ``FUNCTION``) still
    raise here, but as a clear :class:`IdlInternalError` instead of Ruby's
    obscure ``NoMethodError``.
    """
    if kind is TypeKind.BITS:
        return Type(TypeKind.BITS, width=WIDTH_UNKNOWN)
    return Type(kind)


class Type:
    """An IDL type. Immutable: there are no public mutators.

    See the module docstring for the full Ruby -> Python mapping and the
    list of documented deviations.
    """

    __slots__ = (
        "_csr",
        "_enum_class",
        "_sub_type",
        "_tuple_types",
        "_width",
        "kind",
        "max_width",
        "qualifiers",
        "raw_name",
        "width_ast",
    )

    def __init__(
        self,
        kind: TypeKind,
        *,
        qualifiers: Sequence[Qualifier] = (),
        width: Width | None = None,
        width_ast: WidthExpression | None = None,
        max_width: int | None = None,
        sub_type: Type | None = None,
        name: str | None = None,
        tuple_types: Sequence[Type] | None = None,
        enum_class: EnumerationType | None = None,
        csr: CsrLike | None = None,
    ) -> None:
        if not isinstance(kind, TypeKind):
            raise IdlInternalError(f"Invalid kind {kind!r}")
        if kind is TypeKind.FUNCTION and not isinstance(self, FunctionType):
            raise IdlInternalError("Should be a FunctionType")
        if kind is TypeKind.TUPLE and tuple_types is None:
            raise IdlInternalError("Tuples need a type list")
        if kind is TypeKind.BITS:
            if width is None:
                raise IdlInternalError("Bits type must have width")
            if width != WIDTH_UNKNOWN and not (isinstance(width, int) and width > 0):
                raise IdlInternalError(f"Bits type must have positive width (has {width})")
        if kind is TypeKind.ENUM and width is None:
            raise IdlInternalError("Enum type must have width")
        if kind is TypeKind.ARRAY and width != 0 and sub_type is None:
            raise IdlInternalError("Array must have a subtype")
        if kind is TypeKind.CSR:
            if csr is None:
                raise IdlInternalError("CSR type must have a csr argument")
            if width is None:
                raise IdlInternalError("CSR types must have a width")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "qualifiers", _dedupe_qualifiers(qualifiers))
        object.__setattr__(self, "_width", width)
        object.__setattr__(self, "width_ast", width_ast)
        object.__setattr__(self, "max_width", max_width)
        object.__setattr__(self, "_sub_type", sub_type)
        object.__setattr__(self, "raw_name", name)
        object.__setattr__(
            self, "_tuple_types", None if tuple_types is None else tuple(tuple_types)
        )
        object.__setattr__(self, "_enum_class", enum_class)
        object.__setattr__(self, "_csr", csr)

    # -- immutability -----------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise IdlInternalError(f"Type is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise IdlInternalError(f"Type is immutable; cannot delete {name!r}")

    def __getstate__(self) -> dict[str, object]:
        state: dict[str, object] = {}
        for klass in type(self).__mro__:
            for slot in getattr(klass, "__slots__", ()):
                state[slot] = getattr(self, slot)
        return state

    def __setstate__(self, state: Mapping[str, object]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)

    def _replace(self, **changes: object) -> Type:
        """Return a shallow copy of ``self`` with ``changes`` applied.

        Used to implement the value-returning qualifier mutators. Works
        uniformly across every subclass because it copies via
        ``__getstate__``/``__setstate__`` rather than re-invoking any
        subclass's positional ``__init__``.
        """

        new = copy.copy(self)
        for key, value in changes.items():
            object.__setattr__(new, key, value)
        return new

    # -- "must be set" accessors (mirror Ruby's T.must(@ivar)) -------------

    @property
    def width(self) -> Width:
        if self._width is None:
            raise IdlInternalError("width is not set on this Type", node=self)
        return self._width

    @property
    def sub_type(self) -> Type:
        if self._sub_type is None:
            raise IdlInternalError("sub_type is not set on this Type", node=self)
        return self._sub_type

    @property
    def tuple_types(self) -> tuple[Type, ...]:
        if self._tuple_types is None:
            raise IdlInternalError("tuple_types is not set on this Type", node=self)
        return self._tuple_types

    @property
    def enum_class(self) -> EnumerationType:
        if self._enum_class is None:
            raise IdlInternalError("enum_class is not set on this Type", node=self)
        return self._enum_class

    # -- predicates ---------------------------------------------------------

    @property
    def is_integral(self) -> bool:
        """True for any type generally treated as a scalar integer (``Type#integral?``)."""

        return self.kind is TypeKind.BITS

    @property
    def is_runtime(self) -> bool:
        """True if this type's value can only be known at runtime (``Type#runtime?``)."""

        if self.kind is TypeKind.ARRAY:
            return self.sub_type.is_runtime
        return self.kind is TypeKind.BITS and not isinstance(self._width, int)

    @property
    def is_array(self) -> bool:
        return self.kind is TypeKind.ARRAY

    @property
    def is_const(self) -> bool:
        return Qualifier.CONST in self.qualifiers

    @property
    def is_mutable(self) -> bool:
        return not self.is_const

    @property
    def is_signed(self) -> bool:
        return Qualifier.SIGNED in self.qualifiers

    @property
    def is_global(self) -> bool:
        return Qualifier.GLOBAL in self.qualifiers

    @property
    def is_known(self) -> bool:
        return Qualifier.KNOWN in self.qualifiers

    # -- default value --------------------------------------------------

    def default(self) -> object:
        """The default (zero) value of this type (``Type#default``).

        See deviation B3 in the module docstring: unlike Ruby, an array's
        default is built with one independent call to ``sub_type.default()``
        per element rather than one shared, aliased default object.
        """

        match self.kind:
            case TypeKind.BITS | TypeKind.BITFIELD:
                return 0
            case TypeKind.BOOLEAN:
                return False
            case TypeKind.ARRAY:
                if self._width == WIDTH_UNKNOWN:
                    return []
                assert isinstance(self._width, int)
                return [self.sub_type.default() for _ in range(self._width)]
            case TypeKind.STRING:
                return ""
            case TypeKind.ENUM_REF:
                return min(self.enum_class.element_values)
            case TypeKind.ENUM:
                raise IdlInternalError("?")
            case _:
                raise IdlInternalError(f"No default for {self.kind}")

    # -- names and rendering ------------------------------------------------

    @property
    def name(self) -> str:
        """Dispatching name accessor (``Type#name``, see deviation 2 above)."""

        match self.kind:
            case TypeKind.BITS:
                return f"Bits<{self.width}>"
            case TypeKind.ENUM | TypeKind.BITFIELD | TypeKind.FUNCTION:
                if self.raw_name is None:
                    raise IdlInternalError(f"name is not set for {self.kind}", node=self)
                return self.raw_name
            case TypeKind.CSR:
                if self._csr is None:
                    raise IdlInternalError("csr is not set on this Type", node=self)
                return self._csr.name
            case TypeKind.ENUM_REF:
                return self.enum_class.name
            case _:
                raise IdlInternalError(str(self.kind))

    def to_idl(self) -> str:
        """Render valid IDL source for this type (``Type#to_idl``)."""

        match self.kind:
            case TypeKind.BITS:
                if self._width == WIDTH_UNKNOWN:
                    raise IdlInternalError("Cannot generate an IDL type with an unknown width")
                if self.is_signed:
                    raise IdlInternalError("Cannot directly represent a signed bits")
                return f"Bits<{self._width}>"
            case TypeKind.STRING:
                return "String"
            case TypeKind.BOOLEAN:
                return "Boolean"
            case _:
                raise IdlInternalError("TODO")

    def __str__(self) -> str:
        prefix = "" if not self.qualifiers else f"{' '.join(q.value for q in self.qualifiers)} "
        match self.kind:
            case TypeKind.BITS:
                body = f"Bits<{self._width}>"
            case TypeKind.ENUM:
                body = f"enum definition {self.raw_name}"
            case TypeKind.BOOLEAN:
                body = "Boolean"
            case TypeKind.ENUM_REF:
                body = f"enum {self.enum_class.name}"
            case TypeKind.TUPLE:
                body = f"({','.join(str(t) for t in self.tuple_types)})"
            case TypeKind.BITFIELD:
                body = f"bitfield {self.raw_name}"
            case TypeKind.ARRAY:
                body = f"array of {self.sub_type}"
            case TypeKind.CSR:
                body = f"CSR[{self._csr.name if self._csr is not None else '?'}]"
            case TypeKind.VOID:
                body = "void"
            case TypeKind.STRING:
                body = "string"
            case TypeKind.STRUCT:
                # Only valid for a `StructType` instance, matching Ruby's `T.cast(self, StructType)`.
                body = f"struct {self.type_name}"  # type: ignore[attr-defined]
            case TypeKind.FUNCTION:
                body = f"function {self.name}"
            case _:
                raise IdlInternalError(str(self.kind))
        return prefix + body

    def fully_qualified_name(self) -> str:
        """Alias of ``__str__`` (``Type#fully_qualified_name``)."""

        return str(self)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self}>"

    # -- equality (see deviation 4 above) ------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type):
            return NotImplemented
        if other.kind is TypeKind.BITS:
            return self.kind is TypeKind.BITS and self.width == other.width
        if other.kind is TypeKind.ENUM_REF:
            return self.kind is TypeKind.ENUM_REF and self.enum_class.name == other.name
        raise IdlInternalError(f"TODO: Type == for {other.kind}")

    def __hash__(self) -> int:
        # Deliberately identity-based, mirroring Ruby's default `Object#hash`
        # (`Type` does not override `#hash`, only `#==`).
        return object.__hash__(self)

    def equal_to(self, other: Type | TypeKind) -> bool:
        """True if identical to ``other``, excluding qualifiers (``Type#equal_to?``).

        Note the ``:array``/``:struct`` branches complete gaps Ruby's
        version raised on for the same reasons as ``comparable_to``.
        """

        rhs = _type_from_kind(other) if isinstance(other, TypeKind) else other
        match self.kind:
            case TypeKind.BOOLEAN:
                return rhs.kind is TypeKind.BOOLEAN
            case TypeKind.ENUM_REF:
                return rhs.kind is TypeKind.ENUM_REF and rhs.name == self.enum_class.name
            case TypeKind.DONTCARE:
                return True
            case TypeKind.BITS:
                return rhs.kind is TypeKind.BITS and rhs.width == self._width
            case TypeKind.STRING:
                return rhs.kind is TypeKind.STRING and rhs.width == self._width
            case TypeKind.ARRAY:
                return rhs.kind is TypeKind.ARRAY and rhs.sub_type.equal_to(self.sub_type)
            case TypeKind.STRUCT:
                return rhs.kind is TypeKind.STRUCT and rhs.type_name == self.type_name  # type: ignore[attr-defined]
            case _:
                raise IdlInternalError(f"unimplemented type {self.kind!r}")

    def comparable_to(self, other: Type | TypeKind) -> bool:
        """True if ``other`` can be compared (``>=``, ``<``, ...) to ``self`` (``Type#comparable_to?``)."""

        rhs = _type_from_kind(other) if isinstance(other, TypeKind) else other
        match self.kind:
            case TypeKind.BOOLEAN:
                return rhs.kind is TypeKind.BOOLEAN
            case TypeKind.ENUM_REF:
                return (
                    rhs.kind is TypeKind.ENUM_REF and rhs.enum_class.name == self.enum_class.name
                ) or (rhs.kind is TypeKind.ENUM and rhs.name == self.enum_class.name)
            case TypeKind.BITS:
                return rhs.convertable_to(self) and (self.is_signed == rhs.is_signed)
            case TypeKind.ENUM:
                return rhs.convertable_to(TypeKind.BITS)
            case TypeKind.FUNCTION:
                return False
            case TypeKind.CSR:
                # See deviation B2: Ruby calls `type.csr.width`, which does not exist on
                # `Csr`; we use `max_length`, matching the intent (and `convertable_to`'s
                # working `:csr` branch, which compares against `self.width`).
                if rhs.kind is TypeKind.CSR:
                    return rhs.csr.name == self.csr.name or rhs.convertable_to(  # type: ignore[attr-defined]
                        Type(TypeKind.BITS, width=rhs.csr.max_length)  # type: ignore[attr-defined]
                    )
                return rhs.convertable_to(Type(TypeKind.BITS, width=self.width))
            case TypeKind.STRING:
                return rhs.kind is TypeKind.STRING
            case _:
                raise IdlInternalError(f"unimplemented {self.kind!r}")

    def convertable_to(self, other: Type | TypeKind) -> bool:
        """True if ``self`` can be converted to ``other`` (``Type#convertable_to?``)."""

        rhs = _type_from_kind(other) if isinstance(other, TypeKind) else other
        match self.kind:
            case TypeKind.BOOLEAN:
                return rhs.kind is TypeKind.BOOLEAN
            case TypeKind.ENUM_REF:
                return (rhs.kind is TypeKind.ENUM and rhs.name == self.enum_class.name) or (
                    rhs.kind is TypeKind.ENUM_REF and rhs.enum_class.name == self.enum_class.name
                )
            case TypeKind.DONTCARE:
                return True
            case TypeKind.BITS:
                if rhs.kind is TypeKind.ENUM_REF:
                    warnings.warn("You seem to be missing an $enum cast", stacklevel=2)
                    return False
                return rhs.kind in (TypeKind.BITS, TypeKind.BITFIELD)
            case TypeKind.ENUM:
                if rhs.kind is TypeKind.BITS:
                    return False
                if rhs.kind is TypeKind.ENUM:
                    return rhs.enum_class == self.enum_class
                return False
            case TypeKind.TUPLE:
                self_types = self.tuple_types
                if rhs.kind is TypeKind.TUPLE and len(self_types) == len(rhs.tuple_types):
                    return all(
                        self_types[i].convertable_to(rhs.tuple_types[i])
                        for i in range(len(self_types))
                    )
                return False
            case TypeKind.CSR:
                return (
                    rhs.kind is TypeKind.CSR and rhs.csr.name == self.csr.name
                ) or rhs.convertable_to(  # type: ignore[attr-defined]
                    Type(TypeKind.BITS, width=self.width)
                )
            case TypeKind.BITFIELD:
                if rhs.kind is TypeKind.BITFIELD and self.name == rhs.name:
                    return True
                # Be strict with bitfields -- only accept integrals that are exact-width Bits types.
                return rhs.kind is TypeKind.BITS and rhs.width == self._width
            case TypeKind.ARRAY:
                return (
                    rhs.kind is TypeKind.ARRAY
                    and rhs.sub_type.convertable_to(self.sub_type)
                    and rhs.width == self._width
                )
            case TypeKind.STRING:
                return rhs.kind is TypeKind.STRING
            case TypeKind.VOID:
                return rhs.kind is TypeKind.VOID
            case TypeKind.STRUCT:
                return rhs.kind is TypeKind.STRUCT and rhs.name == self.type_name  # type: ignore[attr-defined]
            case _:
                raise IdlInternalError(f"unimplemented type {self.kind!r}")

    def ary_type(self) -> Type:
        """Given an N-dimensional array type, return the primitive element type (``Type#ary_type``)."""

        current: Type = self
        while current.sub_type.kind is TypeKind.ARRAY:
            current = current.sub_type
        return current.sub_type

    # -- qualifier mutators (value-returning; see deviation 1 above) --------

    def qualify(self, qualifier: Qualifier) -> Type:
        if qualifier in self.qualifiers:
            return self
        return self._replace(qualifiers=(*self.qualifiers, qualifier))

    def make_const(self) -> Type:
        return self.qualify(Qualifier.CONST)

    def make_signed(self) -> Type:
        return self.qualify(Qualifier.SIGNED)

    def make_global(self) -> Type:
        return self.qualify(Qualifier.GLOBAL)

    def make_known(self) -> Type:
        return self.qualify(Qualifier.KNOWN)

    # -- JSON Schema conversion ----------------------------------------------

    @classmethod
    def from_json_schema(cls, schema: Mapping[str, Any]) -> Type | None:
        """The ``Type`` of a value described by JSON Schema ``schema`` (``Type.from_json_schema``)."""

        hsh = dict(schema)
        if "type" in hsh:
            match hsh["type"]:
                case "boolean" | "integer" | "string":
                    return _from_json_schema_scalar_type(hsh)
                case "array":
                    return _from_json_schema_array_type(hsh)
                case _:
                    raise IdlInternalError("unexpected")
        return _from_json_schema_scalar_type(hsh)


def _unsigned_bits_needed(value: int) -> int:
    if value < 0:
        raise IdlInternalError("unsigned JSON schema integer cannot be negative")
    return 1 if value == 0 else value.bit_length()


def _from_json_schema_scalar_type(schema: Mapping[str, Any]) -> Type | None:
    if "type" in schema:
        match schema["type"]:
            case "boolean":
                return Type(TypeKind.BOOLEAN)
            case "integer":
                if "enum" in schema:
                    width = max(_unsigned_bits_needed(e) for e in schema["enum"])
                elif "maximum" in schema:
                    width = _unsigned_bits_needed(schema["maximum"])
                else:
                    width = 128
                return Type(TypeKind.BITS, width=width)
            case "string":
                if "enum" in schema:
                    width = max(len(e) for e in schema["enum"])
                else:
                    width = 4096
                return Type(TypeKind.STRING, width=width)
            case _:
                raise IdlInternalError("Unhandled JSON schema type")
    if "const" in schema:
        const = schema["const"]
        if isinstance(const, bool):
            return Type(TypeKind.BOOLEAN)
        if isinstance(const, int):
            return Type(TypeKind.BITS, width=_unsigned_bits_needed(const))
        if isinstance(const, str):
            return Type(TypeKind.STRING, width=len(const))
        raise IdlInternalError("Unhandled const type")
    if "enum" in schema:
        values = schema["enum"]
        first = values[0]
        if not all(isinstance(v, type(first)) for v in values):
            raise IdlInternalError("Mixed types in enum")
        if isinstance(first, bool):
            return Type(TypeKind.BOOLEAN)
        if isinstance(first, int):
            return Type(TypeKind.BITS, width=max(_unsigned_bits_needed(e) for e in values))
        if isinstance(first, str):
            return Type(TypeKind.STRING, width=max(len(e) for e in values))
        raise IdlInternalError("unhandled enum type")
    if "allOf" in schema:
        subschema_types = [
            t for t in (_from_json_schema_scalar_type(s) for s in schema["allOf"]) if t is not None
        ]
        if not subschema_types:
            raise IdlInternalError("No subschema has a defined type")
        first_kind = subschema_types[0].kind
        if first_kind is TypeKind.STRING:
            if not all(t.kind is TypeKind.STRING for t in subschema_types[1:]):
                raise IdlInternalError("Subschema types do not agree")
            return subschema_types[0]
        if first_kind is TypeKind.BOOLEAN:
            if not all(t.kind is TypeKind.BOOLEAN for t in subschema_types[1:]):
                raise IdlInternalError("Subschema types do not agree")
            return subschema_types[0]
        if first_kind is TypeKind.BITS:
            if not all(t.kind is TypeKind.BITS for t in subschema_types[1:]):
                raise IdlInternalError("Subschema types do not agree")
            unknown_width_type = next(
                (t for t in subschema_types if t.width == WIDTH_UNKNOWN), None
            )
            if unknown_width_type is not None:
                return unknown_width_type
            return max(subschema_types, key=lambda t: t.width)
        raise IdlInternalError("unhandled subschema type")
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref == "schema_defs.json#/$defs/uint32":
            return Type(TypeKind.BITS, width=32)
        if ref == "schema_defs.json#/$defs/uint64":
            return Type(TypeKind.BITS, width=64)
        raise IdlInternalError(f"unhandled ref: {ref}")
    if "not" in schema:
        return None
    raise IdlInternalError(f"unhandled scalar schema:\n{schema}")


def _merge_json_schema_scalar_types(types: Sequence[Type]) -> Type:
    if not types:
        raise IdlInternalError("No scalar types")
    kind = types[0].kind
    if not all(t.kind is kind for t in types):
        raise IdlInternalError("Schema error: Array elements must be the same type")
    if kind is TypeKind.BITS:
        unknown_width_type = next((t for t in types if t.width == WIDTH_UNKNOWN), None)
        if unknown_width_type is not None:
            return unknown_width_type
        return Type(TypeKind.BITS, width=max(t.width for t in types))
    first = types[0]
    if not all(first.equal_to(t) for t in types):
        raise IdlInternalError("Schema error: Array elements must be the same type")
    return first


def _from_json_schema_array_type(schema: Mapping[str, Any]) -> Type:
    width: Width
    if (
        "minItems" not in schema
        or "maxItems" not in schema
        or schema["minItems"] != schema["maxItems"]
    ):
        width = WIDTH_UNKNOWN
    else:
        width = schema["minItems"]

    items = schema["items"]
    if isinstance(items, Mapping):
        return Type(TypeKind.ARRAY, width=width, sub_type=Type.from_json_schema(items))
    if not isinstance(items, Sequence):
        raise IdlInternalError(f"unexpected {schema}")

    item_types = [_from_json_schema_scalar_type(item) for item in items]
    if "additionalItems" in schema:
        item_types.append(_from_json_schema_scalar_type(schema["additionalItems"]))
    sub_type = _merge_json_schema_scalar_types([t for t in item_types if t is not None])
    return Type(TypeKind.ARRAY, width=width, sub_type=sub_type)


class StructType(Type):
    """A structure type (``Idl::StructType``)."""

    __slots__ = ("member_names", "member_types", "type_name")

    def __init__(
        self, type_name: str, member_types: Sequence[Type], member_names: Sequence[str]
    ) -> None:
        super().__init__(TypeKind.STRUCT)
        object.__setattr__(self, "type_name", type_name)
        object.__setattr__(self, "member_types", tuple(member_types))
        object.__setattr__(self, "member_names", tuple(member_names))

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.type_name

    def default(self) -> dict[str, object]:  # type: ignore[override]
        return {
            member_name: member_type.default()
            for member_name, member_type in zip(self.member_names, self.member_types, strict=True)
        }

    def has_member(self, name: str) -> bool:
        return name in self.member_names

    def member_type(self, member_name: str) -> Type:
        try:
            index = self.member_names.index(member_name)
        except ValueError:
            raise IdlInternalError(f"No member named {member_name!r}") from None
        return self.member_types[index]

    @property
    def is_runtime(self) -> bool:  # type: ignore[override]
        """Whether this struct has any member whose type depends on a runtime parameter."""

        return any(member_type.is_runtime for member_type in self.member_types)


class EnumerationType(Type):
    """An enumeration class type (``Idl::EnumerationType``)."""

    __slots__ = ("_builtin", "element_names", "element_values", "ref_type")

    def __init__(
        self,
        type_name: str,
        element_names: Sequence[str],
        element_values: Sequence[int],
        *,
        builtin: bool = False,
    ) -> None:
        if len(element_names) != len(element_values):
            raise IdlInternalError("names and values aren't the same size")
        width = max(element_values).bit_length() if element_values else 0
        if width == 0:
            width = 1  # can happen if only enum member has value 0
        super().__init__(TypeKind.ENUM, width=width, name=type_name)
        object.__setattr__(self, "element_names", tuple(element_names))
        object.__setattr__(self, "element_values", tuple(element_values))
        object.__setattr__(self, "_builtin", bool(builtin))
        object.__setattr__(self, "ref_type", Type(TypeKind.ENUM_REF, enum_class=self))

    @property
    def is_builtin(self) -> bool:
        return self._builtin

    def value(self, element_name: str) -> int | None:
        try:
            index = self.element_names.index(element_name)
        except ValueError:
            return None
        return self.element_values[index]

    def element_name(self, element_value: int) -> str | None:
        try:
            index = self.element_values.index(element_value)
        except ValueError:
            raise IdlInternalError(f"? {element_value}") from None
        return self.element_names[index]


class BitfieldType(Type):
    """A bitfield type (``Idl::BitfieldType``)."""

    __slots__ = ("_field_names", "_field_ranges")

    def __init__(
        self,
        type_name: str,
        width: int,
        field_names: Sequence[str],
        field_ranges: Sequence[range],
    ) -> None:
        if len(field_names) != len(field_ranges):
            raise IdlInternalError("unexpected")
        super().__init__(TypeKind.BITFIELD, name=type_name, width=width)
        object.__setattr__(self, "_field_names", tuple(field_names))
        object.__setattr__(self, "_field_ranges", tuple(field_ranges))

    @property
    def width(self) -> int:  # type: ignore[override]
        return sum(len(field_range) for field_range in self._field_ranges)

    def range(self, field_name: str) -> range:
        try:
            index = self._field_names.index(field_name)
        except ValueError:
            raise IdlInternalError(f"Could not find {field_name} in {self.raw_name}") from None
        return self._field_ranges[index]

    @property
    def field_names(self) -> tuple[str, ...]:
        return self._field_names


class CsrType(Type):
    """A CSR register type (``Idl::CsrType``)."""

    __slots__ = ()

    def __init__(self, csr: CsrLike, *, qualifiers: Sequence[Qualifier] = ()) -> None:
        super().__init__(
            TypeKind.CSR, name=csr.name, csr=csr, width=csr.max_length, qualifiers=qualifiers
        )

    @property
    def csr(self) -> CsrLike:
        if self._csr is None:
            raise IdlInternalError("csr is not set on this Type", node=self)
        return self._csr

    @property
    def fields(self) -> Sequence[CsrFieldLike]:
        if self._csr == WIDTH_UNKNOWN:
            raise IdlInternalError("fields are unknown")
        return self.csr.fields


class FunctionType(Type):
    """A function type (``Idl::FunctionType``).

    Behavioral methods (``return_type``, ``return_value``, ``argument_type``,
    ``argument_name``, ``apply_arguments``, ``argument_values``) need a live
    ``SymbolTableLike`` and evaluate AST argument nodes, so they raise
    ``IdlValueUnknown`` where Ruby used ``AstNode.value_try``/``value_else``
    (``throw``/``catch(:value_error)``); see ``errors.py``.
    """

    __slots__ = ("_symtab", "func_def_ast")

    def __init__(
        self, func_name: str, func_def_ast: FunctionDefinitionLike, symtab: SymbolTableLike
    ) -> None:
        super().__init__(TypeKind.FUNCTION, name=func_name)
        if symtab.levels != 1:
            raise IdlInternalError("symtab should be at level 1")
        object.__setattr__(self, "func_def_ast", func_def_ast)
        object.__setattr__(self, "_symtab", symtab)

    @property
    def argument_nodes(self) -> Sequence[object]:
        return self.func_def_ast.argument_nodes

    @property
    def is_builtin(self) -> bool:
        return self.func_def_ast.builtin()

    @property
    def is_generated(self) -> bool:
        return self.func_def_ast.generated()

    @property
    def is_external(self) -> bool:
        return self.func_def_ast.external()

    @property
    def num_args(self) -> int:
        return self.func_def_ast.num_args()

    def apply_arguments(
        self,
        symtab: SymbolTableLike,
        argument_nodes: Sequence[RvalueLike],
        call_site_symtab: SymbolTableLike,
        func_call_ast: FunctionCallLike,
    ) -> list[object]:
        """Bind each argument as a ``Var`` in ``symtab``; return the argument values.

        A missing (compile-time-unknown) value is recorded as the string
        ``"unknown"``, matching Ruby's ``:unknown`` symbol placeholder.
        """

        from .errors import IdlValueUnknown
        from .symbols import Var  # local import: symbols.py imports types.py

        values: list[object] = []
        arguments = self.func_def_ast.arguments(symtab)
        for index, (atype, aname) in enumerate(arguments):
            if index >= len(argument_nodes):
                func_call_ast.type_error(f"Missing argument {index}")
            try:
                value = argument_nodes[index].value(call_site_symtab)
                symtab.add(aname, Var(aname, atype, value))
                values.append(value)
            except IdlValueUnknown:
                symtab.add(aname, Var(aname, atype))
                values.append("unknown")
        return values

    def argument_values(
        self,
        symtab: SymbolTableLike,
        argument_nodes: Sequence[RvalueLike],
        call_site_symtab: SymbolTableLike,
        func_call_ast: FunctionCallLike,
    ) -> list[object] | None:
        """Return every argument's compile-time value, or ``None`` if any is unknown."""

        from .errors import IdlValueUnknown

        values: list[object] = []
        arguments = self.func_def_ast.arguments(symtab)
        for index in range(len(arguments)):
            if index >= len(argument_nodes):
                func_call_ast.type_error(f"Missing argument {index}")
            try:
                values.append(argument_nodes[index].value(call_site_symtab))
            except IdlValueUnknown:
                return None
        return values

    def return_type(
        self, argument_nodes: Sequence[RvalueLike], func_call_ast: FunctionCallLike
    ) -> Type:
        symtab = self._symtab.global_clone()
        symtab.push(func_call_ast)
        try:
            rtype = self.func_def_ast.return_type(symtab)
        finally:
            symtab.pop()
            symtab.release()
        return rtype

    def return_value(
        self,
        argument_nodes: Sequence[RvalueLike],
        call_site_symtab: SymbolTableLike,
        func_call_ast: FunctionCallLike,
    ) -> object:
        symtab = self._symtab.global_clone()
        symtab.push(func_call_ast)
        self.apply_arguments(symtab, argument_nodes, call_site_symtab, func_call_ast)
        try:
            value = self.func_def_ast.body.return_value(symtab)
        finally:
            symtab.pop()
            symtab.release()
        return value

    def argument_type(
        self,
        index: int,
        argument_nodes: Sequence[RvalueLike],
        call_site_symtab: SymbolTableLike,
        func_call_ast: FunctionCallLike,
    ) -> Type | None:
        if index >= self.func_def_ast.num_args():
            return None
        symtab = self._symtab.global_clone()
        symtab.push(func_call_ast)
        try:
            arguments = self.func_def_ast.arguments(symtab)
        finally:
            symtab.pop()
            symtab.release()
        return arguments[index][0]

    def argument_name(self, index: int, func_call_ast: FunctionCallLike) -> str | None:
        if index >= self.func_def_ast.num_args():
            return None
        symtab = self._symtab.global_clone()
        symtab.push(func_call_ast)
        try:
            arguments = self.func_def_ast.arguments(symtab)
        finally:
            symtab.pop()
            symtab.release()
        return arguments[index][1]

    @property
    def body(self) -> FunctionBodyLike:
        return self.func_def_ast.body


class RegFileElementType(Type):
    """The type of one element in a named register file (e.g. ``F``, ``V``, ``X``).

    Extra Ruby class not explicitly requested by the slice plan, but needed
    so ``symbols.SymbolTable`` can construct the register-file element and
    array globals exactly like Ruby's ``SymbolTable#initialize`` does.
    """

    __slots__ = ("register_file_name",)

    def __init__(self, name: str, width: int, *, max_width: int | None = None) -> None:
        super().__init__(
            TypeKind.BITS, width=width, max_width=max_width if max_width is not None else width
        )
        object.__setattr__(self, "register_file_name", name)

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.register_file_name

    def __str__(self) -> str:
        return f"{self.register_file_name}Reg"


class XregType(RegFileElementType):
    """``XReg`` is really a ``Bits<>`` type; kept as a named alias for backwards compatibility."""

    __slots__ = ()

    def __init__(self, xlen: int) -> None:
        super().__init__("X", xlen, max_width=64)


# Pre-defined common types (``type.rb``'s `Bits1Type`, `Bits32Type`, ...).
#
# Ruby's ``ast.rb`` also defines same-named constants nested inside ``class AstNode`` with a
# ``:known`` qualifier (``AstNode::Bits1Type``, etc.), but a bare reference to e.g. ``Bits1Type``
# from any *sibling* ``AstNode`` subclass resolves lexically to the top-level ``Idl`` module's
# unqualified constant here, never to ``AstNode``'s shadowed one (Ruby's lexical constant lookup
# checks enclosing modules before the ancestor chain). The ``AstNode``-nested, ``:known``-tagged
# versions are therefore unreachable dead code in every real call site; these constants mirror
# the one that is actually observable (confirmed via the oracle: e.g. ``(8'hff)[0]``'s type is
# ``"Bits<1>"``, never ``"known Bits<1>"``).
BITS1_TYPE = Type(TypeKind.BITS, width=1)
BITS32_TYPE = Type(TypeKind.BITS, width=32)
BITS64_TYPE = Type(TypeKind.BITS, width=64)
#: Ruby's ``PossiblyUnknownBits1Type``: structurally identical to ``BITS1_TYPE`` (both are an
#: unqualified 1-bit type), kept as a distinct name only to mirror Ruby's separate constant.
POSSIBLY_UNKNOWN_BITS1_TYPE = Type(TypeKind.BITS, width=1)
BITS_UNKNOWN_TYPE = Type(TypeKind.BITS, width=WIDTH_UNKNOWN)
CONST_BITS_UNKNOWN_TYPE = Type(TypeKind.BITS, width=WIDTH_UNKNOWN, qualifiers=(Qualifier.CONST,))
CONST_BOOL_TYPE = Type(TypeKind.BOOLEAN, qualifiers=(Qualifier.CONST,))
BOOL_TYPE = Type(TypeKind.BOOLEAN)
VOID_TYPE = Type(TypeKind.VOID)
STRING_TYPE = Type(TypeKind.STRING)
