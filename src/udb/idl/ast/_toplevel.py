# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Top-level nodes: constraint bodies, ``fetch``, ``include``, ``isa``, and parse-time type errors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..source import IdlSource
from ..symbols import SymbolTable
from ..types import (
    Type,
)
from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h
from ._declarations import (
    BitfieldDefinition,
    BuiltinEnumDefinition,
    EnumDefinition,
    FunctionBody,
    FunctionDef,
    Global,
    GlobalWithInitialization,
    StructDefinition,
)
from ._leaves import StringLiteral


@dataclass(frozen=True, slots=True, kw_only=True)
class ConstraintBody(Node):
    """A ``constraint_body`` root's statement list (``ImplicationStatement``/``ForLoop`` mix).

    Ruby's ``ConstraintBodyAst``.
    """

    kind: ClassVar[str] = "constraint_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return "\n".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ConstraintBody:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        return cls(source=source, start=start, end=end, children=stmts)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fetch(Node):
    """A top-level ``fetch { ... }`` block; Ruby's ``FetchAst``."""

    kind: ClassVar[str] = "fetch_decl"

    @property
    def body(self) -> FunctionBody:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"fetch {{\n  {self.body.to_idl()}\n}}\n"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"function_body": self.body.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Fetch:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        body = from_h(data["function_body"], sources)
        return cls(source=source, start=start, end=end, children=(body,))


@dataclass(frozen=True, slots=True, kw_only=True)
class IncludeStatement(Node):
    """An ``include "filename"`` statement; Ruby's ``IncludeStatementAst``.

    The single child is a full :class:`StringLiteral` (the grammar's
    ``include_statement`` rule reuses the ``string`` sub-rule).

    Ruby's own ``IncludeStatementAst#to_h`` unconditionally raises
    (``"unreachable"``), and ``IsaAst#to_h``/``IsaAst.from_h`` have no
    special-casing or dispatch branch for an ``include`` child at all --
    calling ``to_h`` on any real Ruby ``IsaAst`` containing an ``include``
    statement crashes, and there is no ``from_h`` support for it either.
    Python instead defines a real, bare ``{"kind": "include", "filename":
    ...}`` form (:meth:`to_h` is overridden to omit the usual ``"source"``
    key entirely, matching what independent black-box test fixtures expect),
    with :meth:`from_h` reconstructing a synthetic source on read since there
    is no Ruby contract to mirror.
    """

    kind: ClassVar[str] = "include"

    @property
    def string_literal(self) -> StringLiteral:
        return self.children[0]  # type: ignore[return-value]

    @property
    def filename(self) -> str:
        return self.string_literal.raw_text[1:-1]

    def to_idl(self) -> str:
        return f'include "{self.filename}"'

    def to_h(self) -> dict[str, Any]:
        return {"kind": self.kind, "filename": self.filename}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> IncludeStatement:
        _check_kind(data, cls.kind)
        filename = data["filename"]
        if data.get("source") is None:
            text = f'include "{filename}"'
            source = IdlSource(text=text, label="<synthetic>")
            start, end = 0, len(text)
        else:
            source, start, end = _source_and_span(data, sources)
        string_literal = StringLiteral(
            source=source, start=start, end=end, raw_text=f'"{filename}"'
        )
        return cls(source=source, start=start, end=end, children=(string_literal,))


@dataclass(frozen=True, slots=True, kw_only=True)
class Isa(Node):
    """The top-level ``isa`` root: a whole IDL file's list of definitions.

    Ruby's ``IsaAst``. Whitespace-only definitions are dropped by
    ``IsaSyntaxNode#to_ast`` before construction, so ``children`` here is
    already just the real top-level definitions.
    """

    kind: ClassVar[str] = "isa"

    @property
    def definitions(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        globals_ = tuple(
            d for d in self.definitions if isinstance(d, (GlobalWithInitialization, Global))
        )
        enums = tuple(
            d for d in self.definitions if isinstance(d, (EnumDefinition, BuiltinEnumDefinition))
        )
        bitfields = tuple(d for d in self.definitions if isinstance(d, BitfieldDefinition))
        structs = tuple(d for d in self.definitions if isinstance(d, StructDefinition))
        functions = tuple(d for d in self.definitions if isinstance(d, FunctionDef))
        fetch = next(d for d in self.definitions if isinstance(d, Fetch))
        return (
            "%version 1.0\n\n"
            f"{_idl_join(globals_, sep='\n')}\n"
            f"{_idl_join(enums, sep='\n')}\n"
            f"{_idl_join(bitfields, sep='\n')}\n"
            f"{_idl_join(structs, sep='\n')}\n"
            f"{_idl_join(functions, sep='\n')}\n"
            f"{fetch.to_idl()}"
        )

    def _to_h_fields(self) -> dict[str, Any]:
        return {"children": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Isa:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        children = tuple(from_h(c, sources) for c in data["children"])
        return cls(source=source, start=start, end=end, children=children)


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseTimeDetectedTypeError(Node):
    """A parse-time-detected ``$``-builtin misuse (bad arg count/type, unknown builtin).

    Ruby's ``ParseTimeDetectedTypeError`` (note: unlike every other node
    class, this one keeps its un-suffixed Ruby name verbatim, since Ruby's
    class is *not* named ``ParseTimeDetectedTypeErrorAst``). Produced by
    lowering in place of e.g. ``WidthReveal``/``EnumSize``/etc. when a
    ``$``-builtin call has the wrong argument count or an invalid argument
    type. Ruby has no ``self.from_h`` entry for this kind at all (it is
    simply absent from the master dispatch table); Python adds one for
    completeness.
    """

    kind: ClassVar[str] = "ParseTimeDetectedTypeError"

    reason: str

    def to_idl(self) -> str:
        return self.text

    def _to_h_fields(self) -> dict[str, Any]:
        return {"reason": self.reason}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> ParseTimeDetectedTypeError:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, reason=data["reason"])

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.type_error(self.reason)

    def type(self, symtab: SymbolTable) -> Type:
        self.type_error(self.reason)

    def value(self, symtab: SymbolTable) -> Any:
        self.value_error("Can't take value of a type error")
