# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Base :class:`Node` class and module-level helpers shared by every node module."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, NoReturn

from ..errors import IdlInternalError, IdlTypeError, IdlValueUnknown
from ..source import IdlSource
from ..symbols import SymbolTable
from ..types import (
    Type,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    """Base class for every IDL syntax tree node.

    Mirrors Ruby's ``Idl::AstNode``: an immutable node with a source
    reference, a half-open ``(start, end)`` interval into that source's text,
    a tuple of child nodes, and a parent link (set once, at construction).
    """

    kind: ClassVar[str] = ""

    source: IdlSource
    start: int
    end: int
    children: tuple[Node, ...] = ()
    parent: Node | None = field(default=None, compare=False, repr=False)
    _cache: dict[str, Any] = field(default_factory=dict, compare=False, repr=False, hash=False)

    def __post_init__(self) -> None:
        for child in self.children:
            object.__setattr__(child, "parent", self)

    @property
    def text(self) -> str:
        """The exact source text spanned by this node (Ruby's ``text_value``)."""
        return self.source.text[self.start : self.end]

    @property
    def lineno(self) -> int:
        """1-based line number this node starts on."""
        return self.source.lineno(self.start)

    @property
    def column(self) -> int:
        """1-based column number this node starts on."""
        return self.source.column(self.start)

    def _to_h_fields(self) -> dict[str, Any]:
        """Subclass-specific ``to_h`` keys (everything but ``kind``/``source``)."""
        return {}

    def to_h(self) -> dict[str, Any]:
        """Dict serialization matching Ruby's ``AstNode#to_h`` exactly."""
        result: dict[str, Any] = {"kind": self.kind}
        result.update(self._to_h_fields())
        result["source"] = self.source.source_dict(self.start, self.end)
        return result

    def to_idl(self) -> str:  # pragma: no cover - overridden by every concrete subclass
        raise NotImplementedError(f"{type(self).__name__}.to_idl")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.text!r})"

    # -- semantic error/diagnostic helpers -----------------------------------
    # Ports of ``Idl::AstNode#lines_around``/``#type_error``/``#internal_error``/
    # ``#truncation_warn`` (``ast.rb`` ~lines 335-478). ``value_error`` replaces
    # Ruby's global ``throw(:value_error)`` with :class:`IdlValueUnknown` (see
    # ``doc/stage4-idl.md`` "Semantics").

    @property
    def input_file(self) -> str:
        """Mirrors ``AstNode#input_file`` (here, always the tree's source label)."""
        return self.source.label

    def find_ancestor(self, klass: type[Node]) -> Node | None:
        """The nearest ancestor that is an instance of *klass*. Mirrors ``AstNode#find_ancestor``."""
        node = self.parent
        while node is not None:
            if isinstance(node, klass):
                return node
            node = node.parent
        return None

    def _lines_around(self) -> tuple[str, tuple[int, int], tuple[int, int]]:
        """Port of ``AstNode#lines_around``: +-2/+3 lines of context around this node's span."""
        text = self.source.text
        interval_min = self.start
        interval_max = self.end - 1 if self.end > self.start else self.start

        interval_start = interval_min
        cnt = 0
        while cnt < 2:
            if text[interval_start] == "\n":
                cnt += 1
            if interval_start == 0:
                break
            interval_start -= 1

        interval_end = interval_max
        cnt = 0
        while cnt < 3:
            if text[interval_end] == "\n":
                cnt += 1
            if interval_end >= len(text) - 1:
                break
            if cnt == 3:
                break
            interval_end += 1

        lines = text[interval_start : interval_end + 1]
        problem_interval = (interval_min - interval_start, interval_max - interval_start)
        lines_interval = (interval_start + 1, interval_end)
        return lines, problem_interval, lines_interval

    def _format_type_error(self, reason: str) -> str:
        """Port of ``AstNode#type_error``'s message formatting (always the non-tty branch)."""
        lines, (pmin, pmax), (li_min, _li_max) = self._lines_around()
        marked = (
            f"{lines[:pmin]}**HERE** >> {lines[pmin : pmax + 1]} << **HERE**{lines[pmax + 1 :]}"
        )

        prefix = self.source.text[: li_min + 1]
        starting_lineno = prefix.count("\n")
        numbered_lines = []
        for line in marked.splitlines(keepends=True):
            starting_lineno += 1
            numbered_lines.append(f"{self.source.starting_line + starting_lineno - 1}: {line}")
        numbered = "".join(numbered_lines)

        return (
            f"In file {self.input_file}\n"
            f"On line {self.lineno}\n"
            "In the code:\n\n"
            f"  {numbered.replace(chr(10), chr(10) + '  ')}\n\n"
            "A type error occurred\n"
            f"  {reason}\n"
        )

    def type_error(self, reason: str) -> NoReturn:
        """Raise :class:`IdlTypeError`. Mirrors ``AstNode#type_error``."""
        raise IdlTypeError(reason, self, message=self._format_type_error(reason))

    def internal_error(self, reason: str) -> NoReturn:
        """Raise :class:`IdlInternalError`. Mirrors ``AstNode#internal_error``."""
        message = f"In file {self.input_file}\nOn line {self.lineno}\n  An internal error occurred\n  {reason}\n"
        raise IdlInternalError(reason, self, message=message)

    def value_error(self, reason: str) -> NoReturn:
        """Raise :class:`IdlValueUnknown`. Replaces Ruby's ``throw(:value_error)``."""
        raise IdlValueUnknown(reason, self)

    def truncation_warn(self, reason: str) -> None:
        """Warn that a value was truncated. Mirrors ``AstNode#truncation_warn``."""
        message = (
            f"In file {self.input_file}\n"
            f"On line {self.lineno}\n"
            "  A value was truncated\n"
            f"  {reason}.\n"
            "  Perhaps you want to use a widening operator (`+, `-, `*, `<<)?\n"
        )
        warnings.warn(message, stacklevel=2)

    # -- semantic (type/value) defaults --------------------------------------
    # Every concrete expression node overrides ``type_check``/``type``/``value``;
    # these defaults only fire for nodes that are explicitly out of scope for
    # this slice (statements, declarations, function calls, CSR/register-file
    # access, ...), matching the task's "raise IdlInternalError" guidance.

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.internal_error(f"type_check: not yet supported: {type(self).__name__}")

    def type(self, symtab: SymbolTable) -> Type:
        self.internal_error(f"type: not yet supported: {type(self).__name__}")

    def value(self, symtab: SymbolTable) -> Any:
        self.internal_error(f"value: not yet supported: {type(self).__name__}")

    def values(self, symtab: SymbolTable) -> list[Any]:
        """The complete list of possible compile-time values. Mirrors ``Rvalue#values``.

        The default (used by every node except :class:`TernaryOperatorExpression`)
        is a single-entry list holding :meth:`value`.
        """
        return [self.value(symtab)]

    @staticmethod
    def truncate(value: int, width: int, signed: bool) -> int:
        """Mask *value* to *width* bits, sign-extending if *signed*. Mirrors ``Rvalue#truncate``."""
        masked = value & ((1 << width) - 1) if width > 0 else 0
        if signed and width > 0 and (masked >> (width - 1)) & 1:
            return masked - (1 << width)
        return masked


def _source_and_span(
    data: Mapping[str, Any], sources: Mapping[str, str]
) -> tuple[IdlSource, int, int]:
    """Build an :class:`IdlSource`/``(start, end)`` triple from a ``to_h`` ``"source"`` dict."""
    src = data["source"]
    label = src["file"]
    source = IdlSource(text=sources[label], label=label)
    return source, src["begin"], src["end"]


def _check_kind(data: Mapping[str, Any], kind: str) -> None:
    if data.get("kind") != kind:
        raise ValueError(f"Bad YAML: expected kind {kind!r}, got {data.get('kind')!r}")


def _idl_join(nodes: tuple[Node, ...], sep: str = ", ") -> str:
    return sep.join(n.to_idl() for n in nodes)


def _try_value(node: Node, symtab: SymbolTable) -> Any | None:
    """Evaluate ``node.value(symtab)``, or ``None`` if unknown. Mirrors Ruby's ``value_try``.

    None of the value domains used by this slice (``bool``, ``int``, ``str``,
    ``list``, ``UnknownLiteral``) are ever the Python object ``None``, so
    ``None`` is a safe "unknown" sentinel here.
    """
    try:
        return node.value(symtab)
    except IdlValueUnknown:
        return None


def _ruby_shl(value: Any, amount: int) -> Any:
    """``value << amount`` with Ruby's rule that a negative count shifts right."""
    return value << amount if amount >= 0 else value >> -amount


def _ruby_shr(value: Any, amount: int) -> Any:
    """``value >> amount`` with Ruby's rule that a negative count shifts left."""
    return value >> amount if amount >= 0 else value << -amount


def _values_disjoint(a: Iterable[Any], b: Iterable[Any]) -> bool:
    """Whether no value in *a* equals any value in *b*. Mirrors Ruby's ``Array#intersection.empty?``.

    Compares with ``==`` rather than relying on hashing, since ``UnknownLiteral``
    values may appear in either list.
    """
    b_list = list(b)
    return not any(any(x == y for y in b_list) for x in a)


#: Reserved words that cannot be used as identifiers/type names. Mirrors Ruby's
#: ``Idl::ReservedWords::RESERVED`` (``ast.rb`` ~lines 38-49).
RESERVED_WORDS = frozenset(
    (
        "if",
        "else",
        "for",
        "return",
        "returns",
        "arguments",
        "description",
        "body",
        "function",
        "builtin",
        "generated",
        "enum",
        "bitfield",
        "CSR",
        "true",
        "false",
        "XReg",
        "Bits",
        "Boolean",
        "String",
        "U64",
        "U32",
    )
)


def from_h(data: Mapping[str, Any], sources: Mapping[str, str]) -> Node:
    """Forward to the real dispatcher in :mod:`udb.idl.ast._registry`.

    Every other node module calls this (recursively, while reconstructing
    child nodes in its own ``from_h`` classmethods), so it must be importable
    from here without triggering a circular import. ``_registry`` itself has
    to import *every* concrete node class to build its kind-to-class table,
    so it is necessarily the last module in the package's import order; the
    import below is local (rather than module-level) specifically to break
    that cycle.
    """
    from ._registry import from_h as _dispatch

    return _dispatch(data, sources)
