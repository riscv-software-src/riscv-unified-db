# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Variable/global declarations and enum/bitfield/struct definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ..types import (
    WIDTH_UNKNOWN,
    BitfieldType,
    EnumerationType,
    Qualifier,
    StructType,
    Type,
    TypeKind,
)
from ._base import RESERVED_WORDS, Node, _check_kind, _idl_join, _source_and_span, from_h
from ._leaves import BuiltinTypeName, Id, IntLiteral, UserTypeName


def _wrap_array_decl_type(type_name: Node, ary_size: Node | None) -> dict[str, Any]:
    if ary_size is None:
        return type_name.to_h()
    return {"kind": "array_decl", "array_size": ary_size.to_h(), "element_type": type_name.to_h()}


def _unwrap_array_decl_type(
    data: Mapping[str, Any], sources: Mapping[str, str]
) -> tuple[Node, Node | None]:
    if data.get("kind") == "array_decl":
        return from_h(data["element_type"], sources), from_h(data["array_size"], sources)
    return from_h(data, sources), None


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDeclaration(Node):
    """A variable declaration without initialization (``type name;`` or ``type name[size];``).

    Ruby's ``VariableDeclarationAst``. ``global_scope`` mirrors Ruby's
    ``@global`` ivar (set post-construction by ``make_global`` there); since
    Python nodes are immutable, :class:`Global` passes ``global_scope=True``
    explicitly when it builds its own wrapper node instead (see ``Global``).
    """

    kind: ClassVar[str] = "var_decl"

    global_scope: bool = False

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def id(self) -> Id:
        return self.children[1]  # type: ignore[return-value]

    @property
    def ary_size(self) -> Node | None:
        return self.children[2] if len(self.children) > 2 else None

    @property
    def is_declaration(self) -> bool:
        return True

    def to_idl(self) -> str:
        if self.ary_size is None:
            return f"{self.type_name.to_idl()} {self.id.to_idl()}"
        return f"{self.type_name.to_idl()} {self.id.to_idl()}[{self.ary_size.to_idl()}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "type": _wrap_array_decl_type(self.type_name, self.ary_size),
            "name": self.id.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> VariableDeclaration:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name, ary_size = _unwrap_array_decl_type(data["type"], sources)
        id_node = from_h(data["name"], sources)
        children = (type_name, id_node) + ((ary_size,) if ary_size is not None else ())
        return cls(source=source, start=start, end=end, children=children)

    def const_eval(self, symtab: SymbolTable) -> bool:
        self.add_symbol(symtab)
        return True

    def decl_type(self, symtab: SymbolTable) -> Type | None:
        dtype = self.type_name.type(symtab)
        if dtype is None:
            return None
        qualifiers = []
        if self.id.name[:1].isupper():
            qualifiers.append(Qualifier.CONST)
        if self.global_scope:
            qualifiers.append(Qualifier.GLOBAL)
        if dtype.kind == TypeKind.ENUM:
            dtype = Type(TypeKind.ENUM_REF, enum_class=dtype, qualifiers=qualifiers)
        else:
            for q in qualifiers:
                dtype = dtype.qualify(q)
        if self.ary_size is not None:
            try:
                width = self.ary_size.value(symtab)
                dtype = Type(TypeKind.ARRAY, width=width, sub_type=dtype, qualifiers=qualifiers)
            except IdlValueUnknown:
                dtype = Type(
                    TypeKind.ARRAY, width=WIDTH_UNKNOWN, sub_type=dtype, qualifiers=qualifiers
                )
        return dtype

    def type(self, symtab: SymbolTable) -> Type:
        return self.decl_type(symtab)

    def type_check(
        self,
        symtab: SymbolTable,
        *,
        strict: bool = False,
        add_sym: bool = True,
        is_function_arg: bool = False,
    ) -> None:
        if add_sym and symtab.defined_in_current_scope(self.id.name):
            self.type_error(f"Variable '{self.id.name}' is already declared in this scope")
        self.type_name.type_check(symtab, strict=strict)
        dtype = self.type_name.type(symtab)
        if dtype is None:
            self.type_error(f"No type '{self.type_name.text}'")
        if not is_function_arg and self.id.name[:1].isupper():
            self.type_error("Constants must be initialized at declaration")
        if self.id.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.id.name}' as variable name")
        if self.ary_size is not None:
            self.ary_size.type_check(symtab, strict=strict)
            try:
                self.ary_size.value(symtab)
            except IdlValueUnknown:
                if not self.ary_size.type(symtab).is_const:
                    self.type_error(f"Array size ({self.ary_size.text}) must be a constant")
        if add_sym:
            self.add_symbol(symtab)
        self.id.type_check(symtab, strict=strict)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if self.global_scope:
            symtab.add_unique(self.id.name, Var(self.id.name, self.decl_type(symtab), None))
        else:
            dtype = self.decl_type(symtab)
            if dtype is None:
                self.type_error(f"No Type '{self.type_name.text}'")
            symtab.add(self.id.name, Var(self.id.name, dtype, dtype.default()))


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDeclarationWithInitialization(Node):
    """A variable declaration with initialization (``type name = rhs;``).

    Ruby's ``VariableDeclarationWithInitializationAst``. Note the array-size
    child, when present, is the *last* child here (unlike plain
    :class:`VariableDeclaration`, where it is the third).
    """

    kind: ClassVar[str] = "var_decl_init"

    for_iter_var: bool = False
    global_scope: bool = False

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def lhs(self) -> Id:
        return self.children[1]  # type: ignore[return-value]

    @property
    def rhs(self) -> Node:
        return self.children[2]

    @property
    def ary_size(self) -> Node | None:
        return self.children[3] if len(self.children) > 3 else None

    @property
    def id(self) -> str:
        return self.lhs.name

    @property
    def is_declaration(self) -> bool:
        return True

    @property
    def is_executable(self) -> bool:
        return True

    def to_idl(self) -> str:
        if self.ary_size is None:
            return f"{self.type_name.to_idl()} {self.lhs.to_idl()} = {self.rhs.to_idl()}"
        return f"{self.type_name.to_idl()} {self.lhs.to_idl()}[{self.ary_size.to_idl()}] = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "type": _wrap_array_decl_type(self.type_name, self.ary_size),
            "name": self.lhs.to_h(),
            "value": self.rhs.to_h(),
            "in_for_loop": self.for_iter_var,
        }

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> VariableDeclarationWithInitialization:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name, ary_size = _unwrap_array_decl_type(data["type"], sources)
        lhs = from_h(data["name"], sources)
        rhs = from_h(data["value"], sources)
        children = (type_name, lhs, rhs) + ((ary_size,) if ary_size is not None else ())
        return cls(
            source=source, start=start, end=end, children=children, for_iter_var=data["in_for_loop"]
        )

    def const_eval(self, symtab: SymbolTable) -> bool:
        var = Var(self.id, self.lhs_type(symtab))
        symtab.add(self.id, var)
        if self.rhs.const_eval(symtab):
            return True
        var.const_incompatible()
        return False

    def lhs_type(self, symtab: SymbolTable) -> Type:
        decl_type = self.type_name.type(symtab)
        if decl_type is None:
            self.type_error(f"No type '{self.type_name.text}'")
        qualifiers = []
        if self.lhs.name[:1].isupper():
            qualifiers.append(Qualifier.CONST)
        if self.global_scope:
            qualifiers.append(Qualifier.GLOBAL)
        if decl_type.kind == TypeKind.ENUM:
            decl_type = Type(TypeKind.ENUM_REF, enum_class=decl_type)
        for q in qualifiers:
            decl_type = decl_type.qualify(q)
        if self.ary_size is not None:
            try:
                width = self.ary_size.value(symtab)
                decl_type = Type(
                    TypeKind.ARRAY, sub_type=decl_type, width=width, qualifiers=qualifiers
                )
            except IdlValueUnknown:
                self.type_error("Array size must be known at compile time")
        return decl_type

    def type(self, symtab: SymbolTable) -> Type:
        return self.lhs_type(symtab)

    def value(self, symtab: SymbolTable) -> Any:
        return self.rhs.value(symtab)

    def type_check(
        self, symtab: SymbolTable, *, strict: bool = False, add_sym: bool = True
    ) -> None:
        if add_sym and symtab.defined_in_current_scope(self.id):
            self.type_error(f"Variable '{self.id}' is already declared in this scope")
        self.rhs.type_check(symtab, strict=strict)
        self.type_name.type_check(symtab, strict=strict)
        if self.ary_size is not None:
            self.ary_size.type_check(symtab, strict=strict)

        decl_type = self.lhs_type(symtab)

        if decl_type.is_const:
            try:
                value = self.rhs.value(symtab)
                if add_sym:
                    symtab.add(
                        self.id, Var(self.id, decl_type, value, for_loop_iter=self.for_iter_var)
                    )
            except IdlValueUnknown:
                if not self.rhs.type(symtab).is_const:
                    self.type_error(
                        f"Declaring constant ({self.lhs.name}) with a non-constant value "
                        f"({self.rhs.text})"
                    )
                if add_sym:
                    symtab.add(self.id, Var(self.id, decl_type, for_loop_iter=self.for_iter_var))
        elif add_sym:
            symtab.add(self.id, Var(self.id, decl_type, for_loop_iter=self.for_iter_var))

        self.lhs.type_check(symtab, strict=strict)

        if self.rhs.type(symtab).convertable_to(decl_type):
            return
        self.type_error(f"Incompatible type ({decl_type}, {self.rhs.type(symtab)}) in assignment")

    def add_symbol(self, symtab: SymbolTable) -> None:
        if self.global_scope:
            if self.lhs.name[:1].isupper():
                try:
                    value = self.rhs.value(symtab)
                    symtab.add(
                        self.id,
                        Var(self.id, self.lhs_type(symtab), value, for_loop_iter=self.for_iter_var),
                    )
                except IdlValueUnknown:
                    symtab.add(
                        self.id,
                        Var(self.id, self.lhs_type(symtab), for_loop_iter=self.for_iter_var),
                    )
            else:
                symtab.add_unique(
                    self.id, Var(self.id, self.lhs_type(symtab), for_loop_iter=self.for_iter_var)
                )
        else:
            try:
                if self.for_iter_var:
                    symtab.add(
                        self.id,
                        Var(self.id, self.lhs_type(symtab), for_loop_iter=self.for_iter_var),
                    )
                else:
                    value = self.rhs.value(symtab)
                    symtab.add(
                        self.id,
                        Var(self.id, self.lhs_type(symtab), value, for_loop_iter=self.for_iter_var),
                    )
            except IdlValueUnknown:
                symtab.add(
                    self.id, Var(self.id, self.lhs_type(symtab), for_loop_iter=self.for_iter_var)
                )

    def execute(self, symtab: SymbolTable) -> None:
        if self.ary_size is not None:
            self.value_error("TODO: Array declaration")
        if self.global_scope:
            return  # never executed at compile time
        try:
            rhs_value = self.rhs.value(symtab)
        except IdlValueUnknown:
            symtab.add(
                self.id, Var(self.id, self.lhs_type(symtab), None, for_loop_iter=self.for_iter_var)
            )
            self.value_error("value of right-hand side of variable initialization is unknown")
        symtab.add(self.id, Var(self.id, self.lhs_type(symtab), rhs_value))


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiVariableDeclaration(Node):
    """``type name1, name2, ...;`` (declaring several variables of one type at once).

    Ruby's ``MultiVariableDeclarationAst``. ``global_scope`` mirrors the
    Ruby ``@global`` ivar / ``make_global``, but no Ruby construction site
    ever calls ``make_global`` on this class (dead code there too), so it
    always stays ``False`` in practice; kept for structural parity.
    """

    kind: ClassVar[str] = "multi_var_decl"

    global_scope: bool = False

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def var_names(self) -> tuple[Id, ...]:
        return self.children[1:]  # type: ignore[return-value]

    @property
    def is_declaration(self) -> bool:
        return True

    def to_idl(self) -> str:
        return f"{self.type_name.to_idl()} {_idl_join(self.var_names)}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"names": [n.to_h() for n in self.var_names], "type": self.type_name.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> MultiVariableDeclaration:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name = from_h(data["type"], sources)
        names = tuple(from_h(n, sources) for n in data["names"])
        return cls(source=source, start=start, end=end, children=(type_name, *names))

    def const_eval(self, symtab: SymbolTable) -> bool:
        self.add_symbol(symtab)
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.type_name.type_check(symtab, strict=strict)
        for v in self.var_names:
            if v.name in RESERVED_WORDS:
                self.type_error("reserved keyword")
            if symtab.defined_in_current_scope(v.name):
                self.type_error(f"Variable '{v.name}' is already declared in this scope")
        if len({v.name for v in self.var_names}) != len(self.var_names):
            self.type_error("Duplicate variable in declaration")
        self.add_symbol(symtab)

    def type(self, symtab: SymbolTable) -> Type:
        dtype = self.type_name.type(symtab)
        if self.global_scope:
            dtype = dtype.qualify(Qualifier.GLOBAL)
        return dtype

    def add_symbol(self, symtab: SymbolTable) -> None:
        for vname in self.var_names:
            dtype = self.type(symtab)
            symtab.add(vname.name, Var(vname.name, dtype, dtype.default()))


@dataclass(frozen=True, slots=True, kw_only=True)
class Global(Node):
    """A ``global`` (file-scope) variable declaration; Ruby's ``GlobalAst``."""

    kind: ClassVar[str] = "global_var_decl"

    @property
    def declaration(self) -> VariableDeclaration:
        """The wrapped declaration, forced into global scope.

        Ruby mutates the child in place via ``make_global``; since our AST is
        immutable, we cache a ``global_scope=True`` copy here instead
        (``AstNode#initialize`` calls ``make_global`` exactly once at
        construction time, so a single cached copy is equivalent).
        """
        cached = self._cache.get("_global_decl")
        if cached is None:
            cached = replace(self.children[0], global_scope=True, _cache={})
            self._cache["_global_decl"] = cached
        return cached  # type: ignore[return-value]

    @property
    def is_declaration(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.declaration.id.const  # default initialization gives a value

    @property
    def id(self) -> str:
        return self.declaration.id.name

    def to_idl(self) -> str:
        return self.declaration.to_idl()

    def _to_h_fields(self) -> dict[str, Any]:
        return {"decl": self.declaration.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Global:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        declaration = from_h(data["decl"], sources)
        return cls(source=source, start=start, end=end, children=(declaration,))

    def type_check(
        self, symtab: SymbolTable, *, strict: bool = False, add_sym: bool = True
    ) -> None:
        self.declaration.type_check(symtab, strict=strict, add_sym=add_sym)

    def type(self, symtab: SymbolTable) -> Type:
        return self.declaration.type(symtab)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if symtab.levels != 1:
            self.internal_error("Should be at global scope")
        self.declaration.add_symbol(symtab)


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalWithInitialization(Node):
    """A ``global`` (file-scope) variable declaration with initialization.

    Ruby's ``GlobalWithInitializationAst``.
    """

    kind: ClassVar[str] = "global_var_decl_with_init"

    @property
    def var_decl_with_init(self) -> VariableDeclarationWithInitialization:
        """The wrapped declaration, forced into global scope; see ``Global.declaration``."""
        cached = self._cache.get("_global_decl")
        if cached is None:
            cached = replace(self.children[0], global_scope=True, _cache={})
            self._cache["_global_decl"] = cached
        return cached  # type: ignore[return-value]

    @property
    def is_declaration(self) -> bool:
        return True

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        decl = self.var_decl_with_init
        return decl.lhs.const and decl.rhs.const_eval(symtab)

    @property
    def id(self) -> str:
        return self.var_decl_with_init.id

    @property
    def rhs(self) -> Node:
        return self.var_decl_with_init.rhs

    def to_idl(self) -> str:
        return self.var_decl_with_init.to_idl()

    def _to_h_fields(self) -> dict[str, Any]:
        return {"decl": self.var_decl_with_init.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> GlobalWithInitialization:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        var_decl_with_init = from_h(data["decl"], sources)
        return cls(source=source, start=start, end=end, children=(var_decl_with_init,))

    def type_check(
        self, symtab: SymbolTable, *, strict: bool = False, add_sym: bool = True
    ) -> None:
        self.var_decl_with_init.type_check(symtab, strict=strict, add_sym=add_sym)

    def type(self, symtab: SymbolTable) -> Type:
        return self.var_decl_with_init.lhs_type(symtab)

    def value(self, symtab: SymbolTable) -> Any:
        return self.var_decl_with_init.value(symtab)

    def execute(self, symtab: SymbolTable) -> None:
        self.var_decl_with_init.execute(symtab)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if symtab.levels != 1:
            self.internal_error("Symtab should be at global scope")
        # globals never have a compile-time value
        self.var_decl_with_init.add_symbol(symtab)


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumDefinition(Node):
    """An ``enum`` definition; Ruby's ``EnumDefinitionAst``.

    ``element_values[i]`` is ``None`` for auto-numbered members (Ruby assigns
    ``next_auto_value`` to those at construction time; :meth:`to_idl` mirrors
    that auto-numbering for round-trip purposes, but this is not part of
    ``to_h``, which just serializes each member's raw AST node or ``None``).
    """

    kind: ClassVar[str] = "enum_decl"

    user_type: UserTypeName
    element_names: tuple[UserTypeName, ...]
    element_values: tuple[IntLiteral | None, ...]

    @property
    def name(self) -> str:
        return self.user_type.name

    @property
    def is_declaration(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def enum_type(self, symtab: SymbolTable) -> Any:
        """Build (and cache) the ``EnumerationType`` for this definition.

        Ruby computes this once, at ``initialize`` time, from the literal
        AST values directly (no ``symtab`` needed); we memoize it lazily
        via ``self._cache`` since our nodes are frozen.
        """
        cached = self._cache.get("_enum_type")
        if cached is None:
            names = [n.name for n in self.element_names]
            values = list(self._resolved_values())
            cached = EnumerationType(self.name, names, values)
            self._cache["_enum_type"] = cached
        return cached

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        for e in self.element_names:
            if e.name in RESERVED_WORDS:
                self.type_error(f"Cannot use reserved word '{e.name}' as enum member")
        for e in self.element_values:
            if e is not None:
                e.type_check(symtab, strict=strict)
        self.add_symbol(symtab)
        self.user_type.type_check(symtab, strict=strict)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if symtab.levels != 1:
            self.internal_error("All enums should be declared in global scope")
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        dtype = self.type(symtab)
        if dtype is None:
            self.internal_error("Type is nil?")
        symtab.add_unique(self.name, dtype)

    def type(self, symtab: SymbolTable) -> Any:
        return self.enum_type(symtab)

    def value(self, symtab: SymbolTable) -> Any:
        self.internal_error("Enum definitions have no value")

    def _resolved_values(self) -> tuple[int, ...]:
        values: list[int] = []
        next_auto = 0
        for v in self.element_values:
            resolved = next_auto if v is None else v.unsigned_value()
            assert isinstance(resolved, int)
            values.append(resolved)
            next_auto = resolved + 1
        return tuple(values)

    def to_idl(self) -> str:
        resolved = self._resolved_values()
        members = "".join(f"{n.to_idl()} {v} " for n, v in zip(self.element_names, resolved))
        return f"enum {self.name} {{ {members}}}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "enum_class_name": self.user_type.to_h(),
            "members": [
                {"name": n.to_h(), "value": None if v is None else v.to_h()}
                for n, v in zip(self.element_names, self.element_values)
            ],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        user_type = from_h(data["enum_class_name"], sources)
        members = data["members"]
        element_names = tuple(from_h(m["name"], sources) for m in members)
        element_values = tuple(
            from_h(m["value"], sources) if m.get("value") is not None else None for m in members
        )
        children = (user_type, *element_names, *(v for v in element_values if v is not None))
        return cls(
            source=source,
            start=start,
            end=end,
            children=children,
            user_type=user_type,
            element_names=element_names,
            element_values=element_values,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinEnumDefinition(Node):
    """A ``builtin enum`` definition; Ruby's ``BuiltinEnumDefinitionAst``."""

    kind: ClassVar[str] = "builtin_enum_decl"

    @property
    def user_type(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    @property
    def name(self) -> str:
        return self.user_type.name

    @property
    def is_declaration(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        sym = symtab.get(self.name)
        if sym is None:
            self.type_error(f"Builtin enum {self.name} is not defined")
        if not isinstance(sym, EnumerationType):
            self.type_error(f"{self.name} is not an enum")
        if not sym.is_builtin:
            self.type_error(f"{self.name} is not a builtin enum")

    def type(self, symtab: SymbolTable) -> Any:
        return symtab.get(self.name)

    def add_symbol(self, symtab: SymbolTable) -> None:
        # doesn't actually do anything since the type has already been added to the symbol table
        pass

    def to_idl(self) -> str:
        return f"generated enum {self.user_type.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"name": self.user_type.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BuiltinEnumDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        user_type = from_h(data["name"], sources)
        return cls(source=source, start=start, end=end, children=(user_type,))


@dataclass(frozen=True, slots=True, kw_only=True)
class BitfieldFieldDefinition(Node):
    """One ``name msb[-lsb]`` field of a ``bitfield`` definition.

    Ruby's ``BitfieldFieldDefinitionAst``.
    """

    kind: ClassVar[str] = "bitfield_field_decl"

    field_name: str

    @property
    def msb(self) -> Node:
        return self.children[0]

    @property
    def lsb(self) -> Node | None:
        return self.children[1] if len(self.children) > 1 else None

    def to_idl(self) -> str:
        if self.lsb is None:
            return f"{self.field_name} {self.msb.to_idl()}"
        return f"{self.field_name} {self.msb.to_idl()}-{self.lsb.to_idl()}"

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.field_name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.field_name}' as field name")
        self.msb.type_check(symtab, strict=strict)
        try:
            self.msb.value(symtab)
        except IdlValueUnknown:
            self.msb.type_error("Bitfield position must be compile-time-known")
        if self.lsb is None:
            return
        self.lsb.type_check(symtab, strict=strict)
        try:
            self.lsb.value(symtab)
        except IdlValueUnknown:
            self.lsb.type_error("Bitfield position must be compile-time-known")

    def range(self, symtab: SymbolTable) -> range:
        msb_val = self.msb.value(symtab)
        if self.lsb is None:
            return range(msb_val, msb_val + 1)
        return range(self.lsb.value(symtab), msb_val + 1)

    def _to_h_fields(self) -> dict[str, Any]:
        lsb_h = self.msb.to_h() if self.lsb is None else self.lsb.to_h()
        return {"name": self.field_name, "range": {"lsb": lsb_h, "msb": self.msb.to_h()}}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BitfieldFieldDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        msb = from_h(data["range"]["msb"], sources)
        lsb = from_h(data["range"]["lsb"], sources)
        return cls(
            source=source, start=start, end=end, children=(msb, lsb), field_name=data["name"]
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BitfieldDefinition(Node):
    """A ``bitfield`` definition; Ruby's ``BitfieldDefinitionAst``."""

    kind: ClassVar[str] = "bitfield_decl"

    @property
    def name_node(self) -> UserTypeName | BuiltinTypeName:
        return self.children[0]  # type: ignore[return-value]

    @property
    def size(self) -> IntLiteral:
        return self.children[1]  # type: ignore[return-value]

    @property
    def bitfield_fields(self) -> tuple[BitfieldFieldDefinition, ...]:
        return self.children[2:]  # type: ignore[return-value]

    @property
    def name(self) -> str:
        return self.name_node.text

    @property
    def is_declaration(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def element_names(self) -> tuple[str, ...]:
        cached = self._cache.get("_element_names")
        if cached is None:
            cached = tuple(f.field_name for f in self.bitfield_fields)
            self._cache["_element_names"] = cached
        return cached

    def element_ranges(self, symtab: SymbolTable) -> tuple[range, ...]:
        cache = self._cache.setdefault("_element_ranges", {})
        if symtab.name not in cache:
            cache[symtab.name] = tuple(f.range(symtab) for f in self.bitfield_fields)
        return cache[symtab.name]

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        self.size.type_check(symtab, strict=strict)
        for f in self.bitfield_fields:
            f.type_check(symtab, strict=strict)
            r = f.range(symtab)
            if r.start >= self.size.value(symtab):
                self.type_error(
                    f"Field position ({r.start}...{r.stop}) is larger than the bitfield "
                    f"width ({self.size.value(symtab)} {self.size.text})"
                )
        self.add_symbol(symtab)
        self.name_node.type_check(symtab, strict=strict)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if symtab.levels != 1:
            self.internal_error("All Bitfields should be declared at global scope")
        symtab.add_unique(self.name, self.type(symtab))

    def type(self, symtab: SymbolTable) -> Any:
        cached = self._cache.get("_type")
        if cached is None:
            cached = BitfieldType(
                self.name,
                self.size.value(symtab),
                self.element_names(),
                self.element_ranges(symtab),
            )
            self._cache["_type"] = cached
        return cached

    def value(self, symtab: SymbolTable) -> Any:
        self.internal_error("Bitfield definitions have no value")

    def to_idl(self) -> str:
        parts = [f"bitfield ({self.size.to_idl()}) {self.name_node.to_idl()} {{ "]
        parts.extend(f.to_idl() for f in self.bitfield_fields)
        parts.append("}")
        return "\n".join(parts)

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name_node.to_h(),
            "size": self.size.to_h(),
            "fields": [f.to_h() for f in self.bitfield_fields],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BitfieldDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        name_node = from_h(data["name"], sources)
        size = from_h(data["size"], sources)
        fields = tuple(from_h(f, sources) for f in data["fields"])
        return cls(source=source, start=start, end=end, children=(name_node, size, *fields))


@dataclass(frozen=True, slots=True, kw_only=True)
class StructDefinition(Node):
    """A ``struct`` definition; Ruby's ``StructDefinitionAst``.

    Unlike every other definition node, ``name`` and each member's name are
    bare Python strings, not child nodes (mirroring Ruby, where they are
    plain ``String`` attributes, not part of ``children``).
    """

    kind: ClassVar[str] = "struct_decl"

    name: str
    member_names: tuple[str, ...]

    @property
    def member_types(self) -> tuple[Node, ...]:
        return self.children

    @property
    def is_declaration(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        for member_name in self.member_names:
            if member_name in RESERVED_WORDS:
                self.type_error(f"Cannot use reserved word '{member_name}' as variable name")
        for t in self.member_types:
            t.type_check(symtab, strict=strict)
        self.add_symbol(symtab)

    def type(self, symtab: SymbolTable) -> Any:
        member_types = []
        for t in self.member_types:
            member_type = t.type(symtab)
            if member_type is None:
                self.type_error(f"Type {t.text} is not known")
            if member_type.kind == TypeKind.ENUM:
                member_type = Type(TypeKind.ENUM_REF, enum_class=member_type)
            member_types.append(member_type)
        return StructType(self.name, member_types, self.member_names)

    def add_symbol(self, symtab: SymbolTable) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        if symtab.levels != 1:
            self.internal_error("Structs should be declared at global scope")
        symtab.add_unique(self.name, self.type(symtab))

    def member_type(self, name: str, symtab: SymbolTable) -> Any:
        try:
            idx = self.member_names.index(name)
        except ValueError:
            return None
        return self.member_types[idx].type(symtab)

    @property
    def num_members(self) -> int:
        return len(self.member_names)

    def to_idl(self) -> str:
        members = "; ".join(
            f"{t.to_idl()} {n}" for t, n in zip(self.member_types, self.member_names)
        )
        return f"struct {self.name} {{ {members}; }}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "members": [
                {"name": n, "type": t.to_h()} for n, t in zip(self.member_names, self.member_types)
            ],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> StructDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        members = data["members"]
        member_types = tuple(from_h(m["type"], sources) for m in members)
        member_names = tuple(m["name"] for m in members)
        return cls(
            source=source,
            start=start,
            end=end,
            children=member_types,
            name=data["name"],
            member_names=member_names,
        )
