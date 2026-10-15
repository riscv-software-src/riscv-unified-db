# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Function definitions and executable bodies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ..types import VOID_TYPE, FunctionType, Type, TypeKind
from ._base import RESERVED_WORDS, Node, _check_kind, _idl_join, _source_and_span, from_h
from ._effects import invalidate_expressions
from ._statements import _uniq


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionDef(Node):
    """A function definition; Ruby's ``FunctionDefAst``."""

    kind: ClassVar[str] = "function_decl"

    name: str
    qualifier: str
    description: str
    num_return_types: int
    num_arguments: int

    @property
    def is_declaration(self) -> bool:
        return True

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
    def argument_nodes(self) -> tuple[Node, ...]:
        """Alias for :attr:`arguments`; satisfies ``types.FunctionDefinitionLike``."""
        return self.arguments

    def num_args(self) -> int:
        return len(self.arguments)

    @property
    def builtin(self) -> bool:
        return self.qualifier == "builtin"

    @property
    def generated(self) -> bool:
        return self.qualifier == "generated"

    @property
    def external(self) -> bool:
        return self.qualifier == "external"

    def semantic_arguments(self, symtab: SymbolTable) -> tuple[tuple[Type, str], ...]:
        local = symtab.deep_clone()
        local.push(self)
        try:
            arguments = []
            for argument in self.arguments:
                arg_type = argument.type(local)
                if arg_type is None:
                    self.type_error(f"No type for {argument.text}")
                if arg_type.kind == TypeKind.ENUM:
                    arg_type = arg_type.ref_type
                if argument.id.name[:1].isupper():
                    arg_type = arg_type.make_const()
                name = argument.id.name
                arguments.append((arg_type, name))
                bound = (
                    local.get(name)
                    if symtab.levels > 1 and symtab.defined_in_current_scope(name)
                    else None
                )
                local.add(
                    name, Var(name, arg_type, bound.value if isinstance(bound, Var) else None)
                )
            return tuple(arguments)
        finally:
            local.pop()
            local.release()

    def return_type(self, symtab: SymbolTable) -> Type:
        if symtab.levels != 2:
            self.internal_error(
                f"Function bodies should be at global + 1 scope (at global + {symtab.levels - 1})"
            )
        if not self.return_types:
            return VOID_TYPE
        types = []
        for node in self.return_types:
            rtype = node.type(symtab)
            if rtype.kind == TypeKind.ENUM:
                rtype = rtype.ref_type
            types.append(rtype)
        return types[0] if len(types) == 1 else Type(TypeKind.TUPLE, tuple_types=tuple(types))

    def const_eval(self, symtab: SymbolTable) -> bool:
        if self.builtin or self.generated:
            return False
        local = symtab.global_clone()
        local.push(self)
        try:
            for arg_type, name in self.semantic_arguments(local):
                local.add(name, Var(name, arg_type.make_const()))
            local.add("__expected_return_type", self.return_type(local))
            return self.body.const_eval(local)
        finally:
            local.pop()
            local.release()

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if symtab.levels != 1:
            self.internal_error(f"Functions must be declared at global scope (at {symtab.levels})")
        local = symtab.deep_clone()
        local.push(self)
        try:
            for (arg_type, name), argument in zip(self.semantic_arguments(local), self.arguments):
                local.add(name, Var(name, arg_type))
                argument.type_check(local, add_sym=False, strict=strict, is_function_arg=True)
            for node in self.return_types:
                node.type_check(local, strict=strict)
            if self.body is not None:
                self.body.type_check(local, strict=strict)
        finally:
            local.pop()
            local.release()

    def add_symbol(self, symtab: SymbolTable) -> None:
        if symtab.levels != 1:
            self.internal_error("Functions should be declared at global scope")
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as function name")
        symtab.add_unique(self.name, FunctionType(self.name, self, symtab))

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
class FunctionBody(Node):
    """A function/instruction-operation body (a statement list); Ruby's ``FunctionBodyAst``.

    Both the ``function_body`` and ``instruction_operation`` roots lower to
    this node.
    """

    kind: ClassVar[str] = "function_body"

    @property
    def is_executable(self) -> bool:
        return True

    @property
    def is_returning(self) -> bool:
        return True

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def const_eval(self, symtab: SymbolTable) -> bool:
        return all(stmt.const_eval(symtab) for stmt in self.stmts)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if symtab.levels != 2:
            self.internal_error(
                f"Function bodies should be at global + 1 scope (at {symtab.levels})"
            )
        for stmt in self.stmts:
            stmt.type_check(symtab, strict=strict)

    def return_type(self, symtab: SymbolTable) -> Type:
        for stmt in self.stmts:
            if stmt.is_returning:
                return stmt.return_type(symtab)
            if stmt.action.is_declaration:
                stmt.action.add_symbol(symtab)
        return VOID_TYPE

    def return_value(self, symtab: SymbolTable) -> Any:
        if symtab.levels != 2:
            self.internal_error("Function bodies should be at global + 1 scope")
        for index, stmt in enumerate(self.stmts):
            try:
                if stmt.is_returning:
                    value = stmt.return_value(symtab)
                    if value is not None:
                        return value
                else:
                    stmt.execute(symtab)
            except IdlValueUnknown:
                invalidate_expressions(self.stmts[index + 1 :], symtab)
                raise
        self.value_error("No function body statement returned a value")

    def execute(self, symtab: SymbolTable) -> Any:
        return self.return_value(symtab)

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        if symtab.levels != 2:
            self.internal_error("Function bodies should be at global + 1 scope")
        try:
            return [self.return_value(symtab)]
        except IdlValueUnknown:
            pass
        values: list[Any] = []
        for index, stmt in enumerate(self.stmts):
            try:
                if stmt.is_returning:
                    try:
                        value = stmt.return_value(symtab)
                        if value is not None:
                            return _uniq([*values, value])
                    except IdlValueUnknown:
                        values.extend(stmt.return_values(symtab))
                else:
                    stmt.execute(symtab)
            except IdlValueUnknown:
                invalidate_expressions(self.stmts[index + 1 :], symtab)
                raise
        return _uniq(values)

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
