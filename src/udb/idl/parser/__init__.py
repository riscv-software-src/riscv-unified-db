# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

r"""Hand-written packrat PEG parser for IDL.

This module is a pure-Python port of the Treetop grammar
``tools/ruby-gems/idlc/lib/idlc/idl.treetop``. Every rule in that grammar has
a corresponding ``_r_<rule_name>`` method on the parser class (split across this package's grammar-area modules), tried in
exactly the same alternative order, with exactly the same repetition and
lookahead (``&``/``!``) semantics. Results are memoized by ``(rule, position)``
(packrat parsing) so the whole grammar runs in linear time in the size of the
input.

Lowering (building :mod:`udb.idl.ast` nodes from a successful parse) happens
inline in each ``_r_*`` method, mirroring the corresponding ``SyntaxNode#to_ast``
method in ``tools/ruby-gems/idlc/lib/idlc/ast.rb``.

Grammar summary
----------------

Whitespace and comments
    Whitespace is *only* the literal characters ``' '`` (space) and ``'\n'``
    (newline) -- no tab, no carriage return. A comment starts with ``#`` and
    extends to (and consumes) the next ``'\n'``; a ``#`` with no following
    ``'\n'`` before the end of input does **not** count as whitespace at all
    (this is a faithfully-reproduced Treetop grammar quirk).

Numeric literals (``int``)
    Fourteen alternative forms, tried in this order:

    1. Plain decimal with an explicit width/signedness suffix:
       ``<width>'s<value>`` (e.g. ``32's5``) -- decimal ``value``, ``width``
       decimal digits, signed.
    2. Plain decimal: ``[0-9]+`` (unsigned, width is the natural width).
    3. C++-style signed hex/octal/binary: ``0x<hex>s``, ``0<octal>s``,
       ``0b<binary>s``.
    4. C++-style unsigned hex/octal/binary: ``0x<hex>``, ``0<octal>``,
       ``0b<binary>``.
    5. Bare ``0`` (optionally followed by ``s``, but not by a ``'`` -- that
       is reserved for the Verilog-style forms below).
    6. Verilog-style: ``[<width>|MXLEN]'[s]<radix><digits>`` where ``<radix>``
       is one of ``b``, ``o``, ``d``, ``h`` (unsigned) or ``sb``, ``so``,
       ``sd``, ``sh`` (signed), and ``<digits>`` may contain ``x``/``X`` to
       denote unknown bits (producing an :class:`~udb.idl.ast.UnknownLiteral`
       instead of an :class:`~udb.idl.ast.IntLiteral`). The width may be the
       literal identifier ``MXLEN`` instead of a decimal number, or omitted
       entirely (defaulting to the natural width of ``<digits>``).

Strings
    ``"..."`` with no escape processing at all: any run of non-``"``
    characters, terminated by the closing ``"``.

Identifiers
    * ``id``: ``[A-Za-z][A-Za-z_0-9]*`` (no leading underscore).
    * ``dollar_variable`` name: ``[a-zA-Z_][a-zA-Z0-9_]*`` (leading
      underscore *is* allowed, unlike ``id``).
    * ``dollar_function_call`` name: ``[a-zA-Z_][a-zA-Z0-9_?]*`` (allows a
      trailing ``?``, e.g. ``$array_includes?``).
    * ``field_name``: ``[a-zA-Z][a-zA-Z0-9_]*``.
    * ``csr_name``: ``[a-z][a-z0-9_.]*`` (lowercase only).
    * ``csr_field_name``: ``[a-zA-Z][a-zA-Z0-9]*`` (no underscore, unlike
      ``field_name``).
    * ``function_name``: ``[a-zA-Z][a-zA-Z0-9_]*'?'?``.
    * ``version_string``: ``[0-9]+'.'[0-9]+``.
    * ``type_name``: either ``Bits<template_safe_expression>`` or
      ``[A-Z][A-Za-z0-9_]*``.

Reserved words
    See ``ReservedWords`` in ``ast.rb``. The grammar does not reject them;
    rejecting reserved binding names is a semantic check (Stage 4 slice 15
    in ``doc/stage4-idl.md``).

Expression precedence (loosest to tightest)
    ``ternary_expression`` (``a ? b : c``, both branches always parsed as
    plain, never template-safe, ``expression``) and
    ``implication_expression`` (``[(] [antecedent] -> consequent [)]``, with a
    synthetic zero-width :class:`~udb.idl.ast.TrueExpression` substituted for
    a missing antecedent) sit above the binary-operator precedence chain,
    which runs ``p9`` (loosest) down to ``p0`` (tightest):

    =====  =================================================================
    Level  Operators
    =====  =================================================================
    p9     ``||``
    p8     ``&&``
    p7     ``|``
    p6     ``^``
    p5     ``&``
    p4     ``==``, ``!=``
    p3     ``<=``, ``>=``, ``<``, ``>``
    p2     ``<<``, ``>>``, ``>>>``
    p1     ``+``, ``-``
    p0     ``*``, ``/``, ``%``
    =====  =================================================================

    A "template-safe" parallel chain (``template_safe_p9_binary_expression``
    down to ``template_safe_p3_binary_expression`` -- there is no
    ``template_safe_p{0,1,2}``) exists so that a bare ``>`` inside a
    ``Bits<...>`` template argument is not misparsed as a right-shift or
    comparison operator; per the grammar, the *right-hand* operand of each
    ``template_safe_p{4..9}_binary_expression`` level is deliberately the
    **non**-template-safe ``p{n-1}_binary_expression`` (only the left operand
    stays template-safe), and ``template_safe_p3_binary_expression`` uses
    plain ``p2_binary_expression`` for *both* operands and only allows
    ``<=``/``<`` (not ``>=``/``>``, which would be ambiguous with the
    enclosing ``<...>``).

    Above the binary chain: unary ``-``, ``!``, ``~`` and post ``++``/``--``,
    array element/range access, field access, ``$``-builtins, ``csr[...]``
    access, function calls, enum references, replication (``{N{expr}}``),
    concatenation (``{a, b, c}``), array literals (``[a, b, c]``), and
    parenthesized expressions.

Entry points (``root=`` argument to :func:`parse`)
    ``isa``, ``function_body``, ``instruction_operation``, ``expression``,
    ``constraint_body``, ``for_loop``.
"""

from __future__ import annotations

from ._api import (
    ROOTS,
    parse,
    parse_constraint_body,
    parse_expression,
    parse_for_loop,
    parse_function_body,
    parse_instruction_operation,
    parse_isa,
)

__all__ = [
    "ROOTS",
    "parse",
    "parse_constraint_body",
    "parse_expression",
    "parse_for_loop",
    "parse_function_body",
    "parse_instruction_operation",
    "parse_isa",
]
