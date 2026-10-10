# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Variable/global declarations, function/enum/bitfield/struct definitions, and function bodies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h
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

    Ruby's ``VariableDeclarationAst``.
    """

    kind: ClassVar[str] = "var_decl"

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def id(self) -> Id:
        return self.children[1]  # type: ignore[return-value]

    @property
    def ary_size(self) -> Node | None:
        return self.children[2] if len(self.children) > 2 else None

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


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDeclarationWithInitialization(Node):
    """A variable declaration with initialization (``type name = rhs;``).

    Ruby's ``VariableDeclarationWithInitializationAst``. Note the array-size
    child, when present, is the *last* child here (unlike plain
    :class:`VariableDeclaration`, where it is the third).
    """

    kind: ClassVar[str] = "var_decl_init"

    for_iter_var: bool = False

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


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiVariableDeclaration(Node):
    """``type name1, name2, ...;`` (declaring several variables of one type at once).

    Ruby's ``MultiVariableDeclarationAst``.
    """

    kind: ClassVar[str] = "multi_var_decl"

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def var_names(self) -> tuple[Id, ...]:
        return self.children[1:]  # type: ignore[return-value]

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


@dataclass(frozen=True, slots=True, kw_only=True)
class Global(Node):
    """A ``global`` (file-scope) variable declaration; Ruby's ``GlobalAst``."""

    kind: ClassVar[str] = "global_var_decl"

    @property
    def declaration(self) -> VariableDeclaration:
        return self.children[0]  # type: ignore[return-value]

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


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalWithInitialization(Node):
    """A ``global`` (file-scope) variable declaration with initialization.

    Ruby's ``GlobalWithInitializationAst``.
    """

    kind: ClassVar[str] = "global_var_decl_with_init"

    @property
    def var_decl_with_init(self) -> VariableDeclarationWithInitialization:
        return self.children[0]  # type: ignore[return-value]

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


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionDef(Node):
    """A function definition; Ruby's ``FunctionDefAst``.

    ``qualifier`` is one of ``"normal"``, ``"builtin"``, ``"generated"``,
    ``"external"``. ``children = return_types + arguments (+ [body] if
    present)``; ``num_return_types``/``num_arguments`` record the split
    points (``body`` is builtin-and-generated functions' absence, so it
    cannot be inferred purely from ``len(children)``).
    """

    kind: ClassVar[str] = "function_decl"

    name: str
    qualifier: str
    description: str
    num_return_types: int
    num_arguments: int

    @property
    def return_types(self) -> tuple[Node, ...]:
        return self.children[: self.num_return_types]

    @property
    def arguments(self) -> tuple[Node, ...]:
        end = self.num_return_types + self.num_arguments
        return self.children[self.num_return_types : end]

    @property
    def body(self) -> FunctionBody | None:
        idx = self.num_return_types + self.num_arguments
        return self.children[idx] if len(self.children) > idx else None  # type: ignore[return-value]

    @property
    def builtin(self) -> bool:
        return self.qualifier == "builtin"

    @property
    def generated(self) -> bool:
        return self.qualifier == "generated"

    @property
    def external(self) -> bool:
        return self.qualifier == "external"

    def to_idl(self) -> str:
        returns_idl = f"returns {_idl_join(self.return_types)}" if self.return_types else ""
        args_idl = f"arguments {_idl_join(self.arguments)}" if self.arguments else ""
        qualifier = "" if self.qualifier == "normal" else self.qualifier
        body_idl = "" if self.builtin or self.generated else f"body {{ {self.body.to_idl()} }}"
        return (
            f"{qualifier} function {self.name} {{\n"
            f"  {returns_idl}\n"
            f"  {args_idl}\n"
            f"  description {{ {self.description} }}\n"
            f"  {body_idl}\n"
            "}\n"
        )

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualifier": self.qualifier,
            "return_types": [r.to_h() for r in self.return_types],
            "arguments": [a.to_h() for a in self.arguments],
            "description": self.description,
            "body": None if self.body is None else self.body.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FunctionDef:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_types = tuple(from_h(r, sources) for r in data["return_types"])
        arguments = tuple(from_h(a, sources) for a in data["arguments"])
        body_data = data["body"]
        body = None if body_data is None else from_h(body_data, sources)
        children = return_types + arguments + ((body,) if body is not None else ())
        return cls(
            source=source,
            start=start,
            end=end,
            children=children,
            name=data["name"],
            qualifier=data["qualifier"],
            description=data["description"],
            num_return_types=len(return_types),
            num_arguments=len(arguments),
        )


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


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionBody(Node):
    """A function/instruction-operation body (a statement list); Ruby's ``FunctionBodyAst``.

    This is the AST produced by both the ``function_body`` root and the
    ``instruction_operation`` root (Ruby has no separate
    ``InstructionOperationAst`` class -- both grammar rules lower to
    ``FunctionBodyAst``).
    """

    kind: ClassVar[str] = "function_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return "\n".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FunctionBody:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        return cls(source=source, start=start, end=end, children=stmts)
