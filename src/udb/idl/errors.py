# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exceptions raised by the IDL parser and (in later slices) the type checker."""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "IdlError",
    "IdlInternalError",
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


class IdlTypeError(IdlError):
    """An IDL type error was found during type checking (stubbed for slice 13).

    This is populated in a later migration slice that ports ``AstNode#type_check``.
    """


class IdlInternalError(IdlError):
    """An internal compiler invariant was violated (stubbed for slice 13).

    This is populated in a later migration slice that ports ``AstNode#internal_error``.
    """


class IdlValueUnknown(IdlError):
    """A compile-time value could not be determined (stubbed for slice 13).

    This is populated in a later migration slice that ports ``AstNode#value_error``
    (Ruby's ``throw(:value_error, ...)`` control-flow mechanism).
    """
