# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exceptions raised by the IDL parser, type checker, and evaluator."""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "IdlError",
    "IdlInternalError",
    "IdlSemanticError",
    "IdlSyntaxError",
    "IdlTypeError",
    "IdlValueUnknown",
]


class IdlError(Exception):
    """Base class for all errors raised while processing IDL source."""


class IdlSyntaxError(IdlError):
    """IDL source could not be parsed.

    Attributes:
        message: Human-readable description of the failure.
        offset: 0-based character offset of the furthest parse failure.
        line: 1-based line number of ``offset`` (including any ``starting_line``
            offset carried by the :class:`~udb.idl.source.IdlSource`).
        column: 1-based column number of ``offset`` within its line.
        expected: The set of terminal descriptions that would have allowed
            parsing to continue past ``offset`` (e.g. ``{"';'", "'if'"}``).
        source: The source label (``IdlSource.label``) the text came from.
    """

    def __init__(
        self,
        message: str,
        *,
        offset: int,
        line: int,
        column: int,
        expected: Iterable[str] = (),
        source: str | None = None,
    ) -> None:
        self.offset = offset
        self.line = line
        self.column = column
        self.expected = tuple(sorted(set(expected)))
        self.source = source
        location = f"{source}:{line}:{column}" if source is not None else f"{line}:{column}"
        detail = f" (expected {', '.join(self.expected)})" if self.expected else ""
        super().__init__(f"{location}: {message}{detail}")


class IdlSemanticError(IdlError):
    """Base class for errors raised while type-checking or evaluating IDL.

    Attributes:
        reason: Human-readable description of the failure.
        node: The offending AST node, when known.
    """

    def __init__(self, reason: str, node: object | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.node = node


class IdlTypeError(IdlSemanticError):
    """A type error was found while type-checking IDL (Ruby ``AstNode::TypeError``)."""


class IdlInternalError(IdlSemanticError):
    """An internal compiler invariant was violated (Ruby ``AstNode::InternalError``)."""


class IdlValueUnknown(IdlSemanticError):
    """The compile-time value of an IDL expression is not known.

    Replaces Ruby's ``throw(:value_error)`` / ``AstNode.value_try`` /
    ``AstNode.value_else`` control flow; callers use ``try``/``except
    IdlValueUnknown`` instead of process-wide error state.
    """
