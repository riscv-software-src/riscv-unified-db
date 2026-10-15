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

#: Sentinel used as a ``return_value``/``return_values`` element for a ``void``-returning
#: function, matching Ruby's ``:void`` symbol. The oracle encodes Ruby symbols with
#: ``Symbol#to_s`` (``:void`` -> ``"void"``), and Python's own ``_encode`` passes strings
#: through unchanged, so this plain string round-trips identically to Ruby's output.
VOID_RETURN = "void"


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
    # Unsupported semantic operations fail explicitly rather than returning
    # a value that a caller could mistake for a successful computation.

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.internal_error(f"type_check: not yet supported: {type(self).__name__}")

    def type(self, symtab: SymbolTable) -> Type:
        self.internal_error(f"type: not yet supported: {type(self).__name__}")

    def value(self, symtab: SymbolTable) -> Any:
        self.internal_error(f"value: not yet supported: {type(self).__name__}")

    def const_eval(self, symtab: SymbolTable) -> bool:
        """Whether this node's value is guaranteed knowable at compile time given const args.

        Mirrors Ruby's ``AstNode#const_eval?``, which is abstract on every
        concrete node (``ast.rb`` ~line 217).
        """
        self.internal_error(f"const_eval: not yet supported: {type(self).__name__}")

    def execute(self, symtab: SymbolTable) -> Any:
        """Execute this node for its side effects (assignment, mutation, ...).

        Mirrors Ruby's ``Executable#execute``.
        """
        self.internal_error(f"execute: not yet supported: {type(self).__name__}")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        """Invalidate written bindings when a conditional action cannot be resolved."""
        self.internal_error(f"nullify_assignments: not supported: {type(self).__name__}")

    def add_symbol(self, symtab: SymbolTable) -> None:
        """Register this declaration's symbol(s) into *symtab*. Mirrors ``Declaration#add_symbol``."""
        self.internal_error(f"add_symbol: not yet supported: {type(self).__name__}")

    def return_type(self, symtab: SymbolTable) -> Type:
        """The type of value this node (a statement/body) may return. Mirrors ``Returns#return_type``."""
        self.internal_error(f"return_type: not yet supported: {type(self).__name__}")

    def return_value(self, symtab: SymbolTable) -> Any:
        """The single known return value reachable from this node, or ``None`` if none is definite.

        Mirrors ``Returns#return_value``.
        """
        self.internal_error(f"return_value: not yet supported: {type(self).__name__}")

    def return_values(self, symtab: SymbolTable) -> list[Any]:
        """Every possible return value reachable from this node. Mirrors ``Returns#return_values``."""
        self.internal_error(f"return_values: not yet supported: {type(self).__name__}")

    @property
    def is_declaration(self) -> bool:
        """Whether this node is a ``Declaration`` (has ``add_symbol``). Mirrors ``AstNode#declaration?``."""
        return False

    @property
    def is_executable(self) -> bool:
        """Whether this node is ``Executable`` (has ``execute``). Mirrors ``AstNode#executable?``."""
        return False

    @property
    def is_returning(self) -> bool:
        """Whether this node is a ``Returns`` (has ``return_type``/``return_value``/``return_values``).

        Ruby checks this with ``s.is_a?(Returns)`` (e.g. in
        ``FunctionBodyAst#return_type``); there is no ``AstNode#returns?``
        predicate in Ruby, so this is a Python-only addition serving the
        same purpose.
        """
        return False

    def expected_return_type(self, symtab: SymbolTable) -> Type:
        """The return type expected by the enclosing function. Mirrors ``Returns#expected_return_type``.

        Walks up to the nearest enclosing ``FunctionDef`` and asks for its
        return type; if there is none (e.g. an isolated ``function_body``
        test case), falls back to ``symtab.get("__expected_return_type")``.
        """
        from ._functions import (
            FunctionDef,  # avoid import cycle: _declarations imports _statements
        )

        func_def = self.find_ancestor(FunctionDef)
        if func_def is None:
            rtype = symtab.get("__expected_return_type")
            if rtype is None:
                self.internal_error("Forgot to set __expected_return_type in the symbol table")
            return rtype
        local = symtab.deep_clone()
        try:
            while local.levels > 2:
                local.pop()
            return func_def.return_type(local)
        finally:
            local.release()

    def values(self, symtab: SymbolTable) -> list[Any]:
        """The complete list of possible compile-time values. Mirrors ``Rvalue#values``.

        The default (used by every node except :class:`TernaryOperatorExpression`)
        is a single-entry list holding :meth:`value`.
        """
        return [self.value(symtab)]

    @staticmethod
    def truncate(value: int, width: int, signed: bool) -> int:
        """Mask *value* to *width* bits, sign-extending if *signed*. Mirrors ``Rvalue#truncate``."""
        if width <= 0:
            return 0
        if isinstance(value, int):
            if value >= 0 and (
                value.bit_length() < width or (not signed and value.bit_length() == width)
            ):
                return int(value)
            if signed and value < 0 and (~value).bit_length() < width:
                return value
        else:
            from ._leaves import UnknownLiteral

            if (
                isinstance(value, UnknownLiteral)
                and value.known_value >= 0
                and value.unknown_mask >= 0
                and (value.bit_length() < width or (not signed and value.bit_length() == width))
            ):
                return value if value.unknown_mask else value.known_value
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


def extract_base_var_name(node: Node) -> str | None:
    """The name of the root variable a (possibly nested) lvalue ultimately writes to.

    Mirrors ``AstNode.extract_base_var_name`` (``ast.rb`` ~line 400):
    recurses through array-element/array-range accesses down to the base
    ``Id``. Dispatches on ``node.kind`` (rather than ``isinstance``) to avoid
    an import cycle with ``_leaves``/``_aggregates``.
    """
    if node.kind == "id":
        return node.name  # type: ignore[attr-defined]
    if node.kind in ("array_access", "array_range_access"):
        return extract_base_var_name(node.var)  # type: ignore[attr-defined]
    return None


def write_back_nested(target: Node, new_value: Any, symtab: SymbolTable) -> None:
    """Write *new_value* back through a (possibly nested) lvalue *target*.

    Mirrors ``AstNode.write_back_nested`` (``ast.rb`` ~line 430): the base
    case assigns directly to the named ``Var``; array-element/array-range
    accesses read their parent container/integer, splice in the new value,
    and recurse one level up.
    """
    if target.kind == "id":
        var = symtab.get(target.name)  # type: ignore[attr-defined]
        var.value = new_value
        return
    if target.kind == "array_access":
        ary_value = target.var.value(symtab)  # type: ignore[attr-defined]
        ary_value[target.index.value(symtab)] = new_value  # type: ignore[attr-defined]
        write_back_nested(target.var, ary_value, symtab)  # type: ignore[attr-defined]
        return
    if target.kind == "array_range_access":
        int_value = int(target.var.value(symtab))  # type: ignore[attr-defined]
        msb_value = target.msb.value(symtab)  # type: ignore[attr-defined]
        lsb_value = target.lsb.value(symtab)  # type: ignore[attr-defined]
        mask = ((1 << (msb_value - lsb_value + 1)) - 1) << lsb_value
        updated = (int_value & ~mask) | ((new_value << lsb_value) & mask)
        write_back_nested(target.var, updated, symtab)  # type: ignore[attr-defined]
        return
    raise IdlInternalError(f"Unexpected lvalue node kind {target.kind!r}")


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
