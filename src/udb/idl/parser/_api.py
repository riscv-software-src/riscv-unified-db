# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Public parse entry points."""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .. import ast
from ..source import IdlSource
from ._base import _ParserBase
from ._definitions import _DefinitionRules
from ._expressions import _ExpressionRules
from ._lexical import _LexicalRules
from ._statements import _StatementRules

#: Entry points exposed by :func:`parse`, matching ``tools/ruby-gems/idlc/lib/idlc.rb``.
ROOTS: tuple[str, ...] = (
    "isa",
    "function_body",
    "instruction_operation",
    "expression",
    "constraint_body",
    "for_loop",
)


class _Parser(_DefinitionRules, _StatementRules, _ExpressionRules, _LexicalRules, _ParserBase):
    """The complete IDL grammar: one ``_r_<rule>`` method per ``idl.treetop`` rule."""

    __slots__ = ()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ROOT_RULES: dict[str, str] = {
    "isa": "_r_isa",
    "function_body": "_r_function_body",
    "instruction_operation": "_r_instruction_operation",
    "expression": "_r_expression",
    "constraint_body": "_r_constraint_body",
    "for_loop": "_r_for_loop",
}


# Recursive descent uses roughly 35 Python frames per level of bracket
# nesting, so the default recursion limit (1000) allows only ~28 levels.
# While parsing, raise the limit in proportion to the input length, up to a
# cap; deeper input raises IdlSyntaxError instead of RecursionError.
_FRAMES_PER_CHAR = 40
_MIN_RECURSION_LIMIT = 4_000
_MAX_RECURSION_LIMIT = 60_000
_recursion_lock = threading.Lock()
_recursion_users = 0
_recursion_saved = 0


@contextmanager
def _recursion_headroom(text: str) -> Iterator[None]:
    global _recursion_users, _recursion_saved
    wanted = min(_MAX_RECURSION_LIMIT, _MIN_RECURSION_LIMIT + _FRAMES_PER_CHAR * len(text))
    with _recursion_lock:
        if _recursion_users == 0:
            _recursion_saved = sys.getrecursionlimit()
        _recursion_users += 1
        if sys.getrecursionlimit() < wanted:
            sys.setrecursionlimit(wanted)
    try:
        yield
    finally:
        with _recursion_lock:
            _recursion_users -= 1
            if _recursion_users == 0:
                sys.setrecursionlimit(_recursion_saved)


def _finish_tree(parser: _Parser, root: ast.Node) -> None:
    """Re-link parent pointers and reject grammar-accepted but invalid nodes.

    Packrat memoization shares child nodes between speculative parents that
    backtracking later discards, and each construction re-parents the child,
    so parents are only trustworthy once the final tree is known. The walk
    is iterative because trees can be deeper than the recursion limit.
    """
    object.__setattr__(root, "parent", None)
    invalid = parser._invalid_nodes
    stack = [root]
    while stack:
        node = stack.pop()
        if invalid and id(node) in invalid:
            pos, message = invalid[id(node)]
            raise parser.error_at(pos, message, expected=[])
        for child in node.children:
            object.__setattr__(child, "parent", node)
            stack.append(child)


def parse(
    text: str,
    root: str = "isa",
    *,
    source: IdlSource | None = None,
    label: str = "<idl>",
    starting_line: int = 0,
    starting_offset: int = 0,
    line_file_offsets: tuple[int, ...] | None = None,
) -> ast.Node:
    """Parse ``text`` starting at grammar rule ``root``, returning the resulting AST node.

    Mirrors ``Idl::Compiler#compile_*`` (``tools/ruby-gems/idlc/lib/idlc.rb``):
    the whole of ``text`` must be consumed (trailing, non-whitespace input
    after a structurally-complete match is a syntax error, matching
    Treetop's top-level ``parse`` requiring the root rule to consume all
    input), and a failure anywhere raises :class:`~udb.idl.errors.IdlSyntaxError`
    describing the *furthest* position any alternative got to, with the set
    of terminals that would have allowed parsing to continue from there.

    Args:
        text: The IDL source to parse.
        root: One of :data:`ROOTS` (``"isa"`` by default).
        source: An already-constructed :class:`~udb.idl.source.IdlSource` to
            use instead of building one from ``label``/``starting_line``/etc.
            When given, ``text`` must equal ``source.text``.
        label: Passed to :class:`~udb.idl.source.IdlSource` when ``source``
            is not given.
        starting_line: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.
        starting_offset: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.
        line_file_offsets: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.

    Raises:
        ValueError: ``root`` is not one of :data:`ROOTS`.
        IdlSyntaxError: ``text`` could not be parsed as ``root``.
    """
    if root not in _ROOT_RULES:
        msg = f"unknown IDL parse root {root!r}; expected one of {ROOTS}"
        raise ValueError(msg)
    if source is None:
        source = IdlSource(
            text=text,
            label=label,
            starting_line=starting_line,
            starting_offset=starting_offset,
            line_file_offsets=line_file_offsets,
        )
    elif source.text != text:
        msg = "parse(): `text` must equal `source.text` when `source` is given"
        raise ValueError(msg)

    parser = _Parser(text, source)
    rule = getattr(parser, _ROOT_RULES[root])
    try:
        with _recursion_headroom(text):
            result = rule(0)
    except RecursionError:
        raise parser.error_at(0, "IDL nesting is too deep to parse", expected=[]) from None
    if result is None:
        raise parser.furthest_failure_error()
    node, end = result
    # Mirror Treetop's real `consume_all_input` semantics exactly (see
    # `treetop/runtime/compiled_parser.rb`): the parse only succeeds if the
    # root rule's own match consumed the *entire* input; there is no special
    # leniency for trailing whitespace at this outer level. Whichever
    # trailing whitespace a given root tolerates (e.g. `isa`, `function_body`)
    # is intentionally consumed by that rule's own grammar production, not by
    # this wrapper.
    if text[end:] != "":
        parser._fail(end, "end of input")
        raise parser.furthest_failure_error()
    _finish_tree(parser, node)
    return node


def parse_isa(text: str, **kwargs: Any) -> ast.Isa:
    """Parse ``text`` as the ``isa`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "isa", **kwargs)
    assert isinstance(node, ast.Isa)
    return node


def parse_function_body(text: str, **kwargs: Any) -> ast.FunctionBody:
    """Parse ``text`` as the ``function_body`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "function_body", **kwargs)
    assert isinstance(node, ast.FunctionBody)
    return node


def parse_instruction_operation(text: str, **kwargs: Any) -> ast.FunctionBody:
    """Parse ``text`` as the ``instruction_operation`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "instruction_operation", **kwargs)
    assert isinstance(node, ast.FunctionBody)
    return node


def parse_expression(text: str, **kwargs: Any) -> ast.Node:
    """Parse ``text`` as the ``expression`` root. See :func:`parse` for keyword arguments."""
    return parse(text, "expression", **kwargs)


def parse_constraint_body(text: str, **kwargs: Any) -> ast.ConstraintBody:
    """Parse ``text`` as the ``constraint_body`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "constraint_body", **kwargs)
    assert isinstance(node, ast.ConstraintBody)
    return node


def parse_for_loop(text: str, **kwargs: Any) -> ast.ForLoop:
    """Parse ``text`` as the ``for_loop`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "for_loop", **kwargs)
    assert isinstance(node, ast.ForLoop)
    return node
