# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Statements and control flow: plain/return/conditional statements, ``if``, and ``for``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..source import IdlSource
from ..symbols import SymbolTable
from ..types import VOID_TYPE, Type, TypeKind
from ._base import VOID_RETURN, Node, _check_kind, _idl_join, _source_and_span, from_h
from ._builtins import ImplicationExpression
from ._effects import invalidate_expressions, invalidate_statements


def _uniq(values: list[Any]) -> list[Any]:
    """Order-preserving de-duplication; mirrors Ruby's ``Array#uniq``.

    A plain equality scan (not a ``set``) since return-value lists may contain
    unhashable elements (nested lists from multi-value returns).
    """
    result: list[Any] = []
    for v in values:
        if v not in result:
            result.append(v)
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class Statement(Node):
    """An unconditional statement (``action;``); Ruby's ``StatementAst``.

    Shares ``kind = "stmt"`` with :class:`ReturnStatement`; the module-level
    :func:`from_h` disambiguates by inspecting the nested ``"expr"``'s kind.
    """

    kind: ClassVar[str] = "stmt"

    @property
    def action(self) -> Node:
        return self.children[0]

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.action.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.action.type_check(symtab, strict=strict)

    def execute(self, symtab: SymbolTable) -> None:
        if self.action.is_declaration:
            self.action.add_symbol(symtab)
        if self.action.is_executable:
            self.action.execute(symtab)

    def to_idl(self) -> str:
        return f"{self.action.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.action.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Statement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        action = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(action,))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionalStatement(Node):
    """A conditionally-executed statement (``action if (condition);``).

    Ruby's ``ConditionalStatementAst``; shares ``kind = "conditional_stmt"``
    with :class:`ConditionalReturnStatement`, disambiguated the same way as
    :class:`Statement`/:class:`ReturnStatement`.
    """

    kind: ClassVar[str] = "conditional_stmt"

    @property
    def action(self) -> Node:
        return self.children[0]

    @property
    def condition(self) -> Node:
        return self.children[1]

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.action.const_eval(symtab) and self.condition.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.action.type_check(symtab, strict=strict)
        if self.action.is_declaration:
            self.type_error("Cannot declare from a conditional statement")
        self.condition.type_check(symtab, strict=strict)
        if not self.condition.type(symtab).convertable_to(TypeKind.BOOLEAN):
            self.type_error("condition is not boolean")

    def execute(self, symtab: SymbolTable) -> None:
        try:
            cond = self.condition.value(symtab)
        except IdlValueUnknown:
            invalidate_expressions((self.action,), symtab)
            self.value_error("")
        if cond:
            self.action.execute(symtab)

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_expressions(self.children, symtab)

    def to_idl(self) -> str:
        return f"{self.action.to_idl()} if ({self.condition.to_idl()});"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "expr": self.action.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ConditionalStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        action = from_h(data["expr"], sources)
        condition = from_h(data["condition"], sources)
        return cls(source=source, start=start, end=end, children=(action, condition))


@dataclass(frozen=True, slots=True, kw_only=True)
class ReturnExpression(Node):
    """The (possibly multi-valued) expression list of a ``return``; Ruby's ``ReturnExpressionAst``."""

    kind: ClassVar[str] = "return_expr"

    @property
    def is_returning(self) -> bool:
        return True

    @property
    def return_value_nodes(self) -> tuple[Node, ...]:
        return self.children

    def const_eval(self, symtab: SymbolTable) -> bool:
        return all(node.const_eval(symtab) for node in self.return_value_nodes)

    def return_types(self, symtab: SymbolTable) -> list[Type]:
        nodes = self.return_value_nodes
        if not nodes:
            return [VOID_TYPE]
        if nodes[0].type(symtab).kind is TypeKind.TUPLE:
            return list(nodes[0].type(symtab).tuple_types)
        return [v.type(symtab) for v in nodes]

    def return_type(self, symtab: SymbolTable) -> Type:
        types = self.return_types(symtab)
        if not types:
            return VOID_TYPE
        if len(types) > 1:
            return Type(TypeKind.TUPLE, tuple_types=types)
        return types[0]

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        for v in self.return_value_nodes:
            v.type_check(symtab, strict=strict)
            if v.type(symtab) is None:
                self.type_error(f"Unknown type for {v.text}")

        nodes = self.return_value_nodes
        if nodes and nodes[0].type(symtab).kind is TypeKind.TUPLE and len(nodes) != 1:
            self.type_error("Can't combine tuple types in return")

        if not self.return_type(symtab).convertable_to(self.expected_return_type(symtab)):
            self.type_error(
                f"Return type ({self.return_type(symtab)}) not convertible to expected "
                f"return type ({self.expected_return_type(symtab)})"
            )

    @property
    def enclosing_function(self) -> Node | None:
        from ._functions import (
            FunctionDef,  # avoid import cycle: _declarations imports _statements
        )

        return self.find_ancestor(FunctionDef)

    def return_value(self, symtab: SymbolTable) -> Any:
        nodes = self.return_value_nodes
        if not nodes:
            return VOID_RETURN
        if len(nodes) == 1:
            return nodes[0].value(symtab)
        return [v.value(symtab) for v in nodes]

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        nodes = self.return_value_nodes
        if not nodes:
            return [VOID_RETURN]
        if len(nodes) == 1:
            return nodes[0].values(symtab)
        return [v.values(symtab) for v in nodes]

    def to_idl(self) -> str:
        return f"return {_idl_join(self.children, sep=',')}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"exprs": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ReturnExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        exprs = tuple(from_h(e, sources) for e in data["exprs"])
        return cls(source=source, start=start, end=end, children=exprs)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReturnStatement(Node):
    """A ``return ...;`` statement; Ruby's ``ReturnStatementAst``.

    Shares ``kind = "stmt"`` with :class:`Statement`.
    """

    kind: ClassVar[str] = "stmt"

    @property
    def is_returning(self) -> bool:
        return True

    @property
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.return_expression.const_eval(symtab)

    def return_types(self, symtab: SymbolTable) -> list[Type]:
        return self.return_expression.return_types(symtab)

    def return_type(self, symtab: SymbolTable) -> Type:
        return self.return_expression.return_type(symtab)

    def expected_return_type(self, symtab: SymbolTable) -> Type:
        return self.return_expression.expected_return_type(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.return_expression.type_check(symtab, strict=strict)

    @property
    def return_value_nodes(self) -> tuple[Node, ...]:
        return self.return_expression.return_value_nodes

    @property
    def enclosing_function(self) -> Node | None:
        return self.return_expression.enclosing_function

    def return_value(self, symtab: SymbolTable) -> Any:
        return self.return_expression.return_value(symtab)

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        return self.return_expression.return_values(symtab)

    def to_idl(self) -> str:
        return f"{self.return_expression.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.return_expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ReturnStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_expression = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(return_expression,))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionalReturnStatement(Node):
    """A conditionally-executed ``return`` (``return ... if (condition);``).

    Ruby's ``ConditionalReturnStatementAst``; shares ``kind = "conditional_stmt"``
    with :class:`ConditionalStatement`.
    """

    kind: ClassVar[str] = "conditional_stmt"

    @property
    def is_returning(self) -> bool:
        return True

    @property
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

    @property
    def condition(self) -> Node:
        return self.children[1]

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.condition.const_eval(symtab) and self.return_expression.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.condition.type_check(symtab, strict=strict)
        if self.condition.type(symtab).kind is not TypeKind.BOOLEAN:
            self.type_error("Condition must be boolean")
        self.return_expression.type_check(symtab, strict=strict)

    def return_type(self, symtab: SymbolTable) -> Type:
        return self.return_expression.return_type(symtab)

    def return_types(self, symtab: SymbolTable) -> list[Type]:
        return self.return_expression.return_types(symtab)

    def return_value(self, symtab: SymbolTable) -> Any:
        cond = self.condition.value(symtab)
        if cond:
            return self.return_expression.return_value(symtab)
        return None

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        try:
            cond = self.condition.value(symtab)
            return self.return_expression.return_values(symtab) if cond else []
        except IdlValueUnknown:
            # condition isn't known, so the return value is always possible
            return self.return_expression.return_values(symtab)

    def to_idl(self) -> str:
        return f"{self.return_expression.to_idl()} if ({self.condition.to_idl()});"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "expr": self.return_expression.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> ConditionalReturnStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_expression = from_h(data["expr"], sources)
        condition = from_h(data["condition"], sources)
        return cls(source=source, start=start, end=end, children=(return_expression, condition))


@dataclass(frozen=True, slots=True, kw_only=True)
class ImplicationStatement(Node):
    """A top-level implication statement inside a ``constraint_body``.

    Ruby's ``ImplicationStatementAst``. Note: Ruby's own ``from_h`` for this
    class checks for ``kind == "implication_expr"``, but real ``to_h`` output
    always has ``kind == "implication_stmt"`` -- so Ruby's ``from_h`` can
    never actually succeed on real output (it always raises immediately).
    Python's :meth:`from_h` is not buggy: it correctly reconstructs this node
    from ``kind == "implication_stmt"``.
    """

    kind: ClassVar[str] = "implication_stmt"

    @property
    def expression(self) -> ImplicationExpression:
        return self.children[0]  # type: ignore[return-value]

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.expression.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)

    def satisfied(self, symtab: SymbolTable) -> bool:
        return self.expression.satisfied(symtab)

    def to_idl(self) -> str:
        return f"{self.expression.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ImplicationStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expression = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expression,))


@dataclass(frozen=True, slots=True, kw_only=True)
class IfBody(Node):
    """The statement list of an ``if``/``else if``/``else`` block body.

    Ruby's ``IfBodyAst``. When empty, this is always a synthetic zero-width
    node (Ruby forces ``super("", 0...0, [])`` in that case), matching the
    convention used by :class:`Noop`.
    """

    kind: ClassVar[str] = "if_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    @property
    def is_executable(self) -> bool:
        return True

    @property
    def is_returning(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return all(stmt.const_eval(symtab) for stmt in self.stmts)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        symtab.push(self)
        try:
            for s in self.stmts:
                s.type_check(symtab, strict=strict)
        finally:
            symtab.pop()

    def return_type(self, symtab: SymbolTable) -> Type:
        # the return type is determined by the function
        return self.expected_return_type(symtab)

    def return_value(self, symtab: SymbolTable) -> Any:
        symtab.push(self)
        try:
            for index, s in enumerate(self.stmts):
                try:
                    if s.is_returning:
                        v = s.return_value(symtab)
                        if v is not None:
                            return v
                    else:
                        s.execute(symtab)
                except IdlValueUnknown:
                    invalidate_expressions(self.stmts[index + 1 :], symtab)
                    raise
        finally:
            symtab.pop()
        return None

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        values: list[Any] = []
        symtab.push(self)
        try:
            for index, s in enumerate(self.stmts):
                try:
                    if s.is_returning:
                        try:
                            v = s.return_value(symtab)
                            if v is not None:
                                values.append(v)
                                return _uniq(values)
                        except IdlValueUnknown:
                            values.extend(s.return_values(symtab))
                    else:
                        s.execute(symtab)
                except IdlValueUnknown:
                    invalidate_expressions(self.stmts[index + 1 :], symtab)
                    break
        finally:
            symtab.pop()
        return _uniq(values)

    def execute(self, symtab: SymbolTable) -> None:
        symtab.push(self)
        try:
            self._execute_stmts(symtab)
        finally:
            symtab.pop()

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_statements(self.stmts, symtab, self)

    def _execute_stmts(self, symtab: SymbolTable) -> None:
        err = False
        for s in self.stmts:
            try:
                if s.is_returning:
                    try:
                        v = s.return_value(symtab)
                        if v is not None:
                            # nil means this is a conditional return and the condition is false
                            break
                    except IdlValueUnknown:
                        # not known, keep going
                        err = True
                else:
                    s.execute(symtab)
            except IdlValueUnknown:
                # keep going so that we invalidate everything
                err = True
        if err:
            self.value_error("")

    def to_idl(self) -> str:
        return "".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> IfBody:
        _check_kind(data, cls.kind)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        if not stmts:
            return cls(source=IdlSource(text="", label="<synthetic>"), start=0, end=0, children=())
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, children=stmts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ElseIf(Node):
    """An ``else if (condition) { body }`` clause; Ruby's ``ElseIfAst``."""

    kind: ClassVar[str] = "else_if_stmt"

    @property
    def condition(self) -> Node:
        return self.children[0]

    @property
    def body(self) -> IfBody:
        return self.children[1]  # type: ignore[return-value]

    @property
    def is_returning(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.condition.const_eval(symtab) and self.body.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.condition.type_check(symtab, strict=strict)

        cond_value = None
        try:
            cond_value = self.condition.value(symtab)
        except IdlValueUnknown:
            pass

        if not self.condition.type(symtab).convertable_to(TypeKind.BOOLEAN):
            self.type_error(f"'{self.condition.text}' is not boolean")

        if cond_value is not False:
            self.body.type_check(symtab, strict=strict)

    def return_type(self, symtab: SymbolTable) -> Type:
        # the return type is determined by the function
        return self.expected_return_type(symtab)

    def return_value(self, symtab: SymbolTable) -> Any:
        try:
            condition = self.condition.value(symtab)
        except IdlValueUnknown:
            self.nullify_assignments(symtab)
            raise
        if condition:
            return self.body.return_value(symtab)
        return None

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        try:
            condition = self.condition.value(symtab)
        except IdlValueUnknown:
            context = symtab.deep_clone()
            try:
                values = self.body.return_values(context)
            finally:
                context.release()
                self.nullify_assignments(symtab)
            return values
        return self.body.return_values(symtab) if condition else []

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_expressions((self.condition,), symtab)
        self.body.nullify_assignments(symtab)

    def to_idl(self) -> str:
        return f" else if ({self.condition.to_idl()}) {{ {self.body.to_idl()} }}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "body": self.body.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ElseIf:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        condition = from_h(data["condition"], sources)
        body = from_h(data["body"], sources)
        return cls(source=source, start=start, end=end, children=(condition, body))


@dataclass(frozen=True, slots=True, kw_only=True)
class If(Node):
    """An ``if``/``else if``/``else`` statement; Ruby's ``IfAst``."""

    kind: ClassVar[str] = "if_stmt"

    @property
    def if_cond(self) -> Node:
        return self.children[0]

    @property
    def if_body(self) -> IfBody:
        return self.children[1]  # type: ignore[return-value]

    @property
    def elseifs(self) -> tuple[ElseIf, ...]:
        return self.children[2:-1]  # type: ignore[return-value]

    @property
    def final_else_body(self) -> IfBody:
        return self.children[-1]  # type: ignore[return-value]

    @property
    def is_executable(self) -> bool:
        return True

    @property
    def is_returning(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return (
            self.if_cond.const_eval(symtab)
            and self.if_body.const_eval(symtab)
            and all(eif.const_eval(symtab) for eif in self.elseifs)
            and self.final_else_body.const_eval(symtab)
        )

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        level = symtab.levels
        self.if_cond.type_check(symtab, strict=strict)

        if not self.if_cond.type(symtab).convertable_to(TypeKind.BOOLEAN):
            if self.if_cond.type(symtab).kind is TypeKind.BITS:
                self.type_error(
                    f"'{self.if_cond.text}' is not boolean. "
                    f"Maybe you meant 'if (({self.if_cond.text}) != 0)'?"
                )
            else:
                self.type_error(f"'{self.if_cond.text}' is not boolean")

        if_cond_value = None
        try:
            if_cond_value = self.if_cond.value(symtab)
        except IdlValueUnknown:
            pass

        # short-circuit the if body if we can
        if if_cond_value is not False:
            self.if_body.type_check(symtab, strict=strict)

        if level != symtab.levels:
            self.internal_error(f"not at same level {level} {symtab.levels}")

        if if_cond_value is not True and self.elseifs:
            for eif in self.elseifs:
                eif.type_check(symtab, strict=strict)

        if level != symtab.levels:
            self.internal_error(f"not at same level {level} {symtab.levels}")

        if if_cond_value is not True:
            self.final_else_body.type_check(symtab, strict=strict)

        if level != symtab.levels:
            self.internal_error(f"not at same level {level} {symtab.levels}")

    def taken_body(self, symtab: SymbolTable) -> IfBody | None:
        """The statically-known taken branch's body, or ``None`` for an empty final else.

        Mirrors ``IfAst#taken_body``; raises :class:`IdlValueUnknown` if the taken
        path isn't known at compile time.
        """
        if self.if_cond.value(symtab):
            return self.if_body

        for eif in self.elseifs:
            if eif.condition.value(symtab):
                return eif.body

        return None if not self.final_else_body.stmts else self.final_else_body

    def return_type(self, symtab: SymbolTable) -> Type:
        rt = self.if_body.return_type(symtab)
        if rt is None:
            for eif in self.elseifs:
                candidate = eif.return_type(symtab)
                if candidate is not None:
                    rt = candidate
                    break
        if rt is None:
            rt = self.final_else_body.return_type(symtab)
        return rt

    def return_value(self, symtab: SymbolTable) -> Any:
        try:
            body = self.taken_body(symtab)
        except IdlValueUnknown:
            self.nullify_assignments(symtab)
            raise
        if body is None:
            return None
        return body.return_value(symtab)

    def _possible_paths(self, symtab: SymbolTable) -> tuple[list[IfBody], list[Node]]:
        bodies: list[IfBody] = []
        conditions: list[Node] = []
        context = symtab.deep_clone()
        try:
            branches = [(self.if_cond, self.if_body)]
            branches.extend((clause.condition, clause.body) for clause in self.elseifs)
            for condition, body in branches:
                conditions.append(condition)
                try:
                    taken = condition.value(context)
                except IdlValueUnknown:
                    bodies.append(body)
                    continue
                if taken:
                    bodies.append(body)
                    break
            else:
                bodies.append(self.final_else_body)
        finally:
            context.release()
        return bodies, conditions

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        try:
            body = self.taken_body(symtab)
        except IdlValueUnknown:
            bodies, conditions = self._possible_paths(symtab)
            values: list[Any] = []
            try:
                for possible in bodies:
                    context = symtab.deep_clone()
                    try:
                        values.extend(possible.return_values(context))
                    finally:
                        context.release()
            finally:
                invalidate_expressions(conditions, symtab)
                for possible in bodies:
                    possible.nullify_assignments(symtab)
            return _uniq(values)
        return [] if body is None else body.return_values(symtab)

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        bodies, conditions = self._possible_paths(symtab)
        invalidate_expressions(conditions, symtab)
        for body in bodies:
            body.nullify_assignments(symtab)

    def execute(self, symtab: SymbolTable) -> None:
        try:
            body = self.taken_body(symtab)
        except IdlValueUnknown:
            self.nullify_assignments(symtab)
            raise
        if body is not None:
            body.execute(symtab)

    def to_idl(self) -> str:
        result = f"if ({self.if_cond.to_idl()}) {{ "
        result += self.if_body.to_idl()
        result += "} "
        for elseif in self.elseifs:
            result += elseif.to_idl()
        if self.final_else_body.stmts:
            result += " else { "
            result += self.final_else_body.to_idl()
            result += "} "
        return result

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "condition": self.if_cond.to_h(),
            "taken_body": self.if_body.to_h(),
            "else_ifs": [e.to_h() for e in self.elseifs],
            "else": self.final_else_body.to_h() if self.final_else_body.stmts else None,
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> If:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        if_cond = from_h(data["condition"], sources)
        if_body = from_h(data["taken_body"], sources)
        elseifs = tuple(from_h(e, sources) for e in data["else_ifs"])
        else_data = data["else"]
        final_else_body = (
            from_h(else_data, sources)
            if else_data is not None
            else IfBody(source=IdlSource(text="", label="<synthetic>"), start=0, end=0, children=())
        )
        return cls(
            source=source,
            start=start,
            end=end,
            children=(if_cond, if_body, *elseifs, final_else_body),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ForLoop(Node):
    """A ``for (init; condition; update) { stmts }`` loop; Ruby's ``ForLoopAst``."""

    kind: ClassVar[str] = "for_loop_stmt"

    @property
    def init(self) -> Node:
        return self.children[0]

    @property
    def condition(self) -> Node:
        return self.children[1]

    @property
    def update(self) -> Node:
        return self.children[2]

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children[3:]

    @property
    def is_executable(self) -> bool:
        return True

    @property
    def is_returning(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return (
            self.init.const_eval(symtab)
            and self.condition.const_eval(symtab)
            and self.update.const_eval(symtab)
            and all(stmt.const_eval(symtab) for stmt in self.stmts)
        )

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        symtab.push(self)
        try:
            self.init.type_check(symtab, strict=strict)
            self.condition.type_check(symtab, strict=strict)
            self.update.type_check(symtab, strict=strict)

            for stmt in self.stmts:
                stmt.type_check(symtab, strict=strict)
        finally:
            symtab.pop()

    def satisfied(self, symtab: SymbolTable) -> bool:
        symtab.push(self)
        try:
            self.init.execute(symtab)
            while self.condition.value(symtab):
                for s in self.stmts:
                    if not s.satisfied(symtab):
                        return False
                self.update.execute(symtab)
            return True
        finally:
            symtab.pop()

    def return_value(self, symtab: SymbolTable) -> Any:
        symtab.push(self)
        try:
            try:
                self.init.execute(symtab)

                while self.condition.value(symtab):
                    for s in self.stmts:
                        if s.is_returning:
                            v = s.return_value(symtab)
                            if v is not None:
                                return v
                        elif not isinstance(s, ImplicationStatement):
                            s.execute(symtab)
                    self.update.execute(symtab)
            except IdlValueUnknown:
                self.nullify_assignments(symtab)
                raise
        finally:
            symtab.pop()
        return None

    def return_type(self, symtab: SymbolTable) -> Type:
        # the return type is determined by the function
        return self.expected_return_type(symtab)

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        try:
            return [self.return_value(symtab)]
        except IdlValueUnknown:
            pass

        values: list[Any] = []
        symtab.push(self)
        try:
            try:
                self.init.execute(symtab)

                while self.condition.value(symtab):
                    for s in self.stmts:
                        if s.is_returning:
                            try:
                                v = s.return_value(symtab)
                                if v is not None:
                                    return _uniq([*values, v])
                            except IdlValueUnknown:
                                values.extend(s.return_values(symtab))
                        elif not isinstance(s, ImplicationStatement):
                            s.execute(symtab)
                    self.update.execute(symtab)
            except IdlValueUnknown:
                self.nullify_assignments(symtab)
        finally:
            symtab.pop()

        return _uniq(values)

    def execute(self, symtab: SymbolTable) -> Any:
        return self.return_value(symtab)

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_statements((self.init, self.condition, *self.stmts, self.update), symtab, self)

    def to_idl(self) -> str:
        idl = f"for ({self.init.to_idl()}; {self.condition.to_idl()}; {self.update.to_idl()}) {{"
        idl += "".join(s.to_idl() for s in self.stmts)
        idl += "}"
        return idl

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "init_expr": self.init.to_h(),
            "condition_expr": self.condition.to_h(),
            "update_expr": self.update.to_h(),
            "body": [s.to_h() for s in self.stmts],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ForLoop:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        init = from_h(data["init_expr"], sources)
        condition = from_h(data["condition_expr"], sources)
        update = from_h(data["update_expr"], sources)
        stmts = tuple(from_h(s, sources) for s in data["body"])
        return cls(source=source, start=start, end=end, children=(init, condition, update, *stmts))
