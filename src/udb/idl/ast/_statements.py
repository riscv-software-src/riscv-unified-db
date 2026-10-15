# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Statements and control flow: plain/return/conditional statements, ``if``, and ``for``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..source import IdlSource
from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h
from ._builtins import ImplicationExpression


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
    def return_value_nodes(self) -> tuple[Node, ...]:
        return self.children

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
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

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
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

    @property
    def condition(self) -> Node:
        return self.children[1]

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
