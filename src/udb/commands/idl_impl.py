# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement standalone IDL commands through the compiler API."""

from __future__ import annotations

import re

from ..cli_output import write_generated_source
from .common import CliError


def _binding(text: str) -> tuple[str, str]:
    name, separator, value = text.partition("=")
    if not separator or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or not value:
        raise CliError("expected an IDL identifier followed by =VALUE")
    return name, value


def _decode_binding(text: str) -> tuple[str, int]:
    name, value = _binding(text)
    if not value.isdecimal() or int(value) <= 0:
        raise CliError("decode width must be a positive decimal integer")
    return name, int(value)


def run_idl(command: str, **options: object) -> int:
    from ..idl import parse_expression, parse_instruction_operation
    from ..idl.cli import _compile_text, _read_source, _symbols, _value_text
    from ..idl.symbols import Var
    from ..idl.types import Type, TypeKind

    if command == "compile":
        text = _compile_text(
            _read_source(str(options["file"])),
            str(options["root"]),
            str(options["format"]),
        )
        write_generated_source(
            text,
            options["output"],
            artifact="IDL output",
            create_parents=True,
        )
        return 0
    definitions = [_binding(value) for value in options.get("define", [])]
    if command == "eval":
        symbols = _symbols(definitions)
        expression = parse_expression(str(options["expression"]), label="<expression>")
        expression.type_check(symbols, strict=False)
        text = _value_text(expression.value(symbols))
        write_generated_source(
            text,
            options["output"],
            artifact="IDL output",
            create_parents=True,
        )
        return 0
    symbols = _symbols(definitions)
    symbols.push(None)
    for name, width in dict(_decode_binding(value) for value in options.get("var", [])).items():
        symbols.add_unique(name, Var(name, Type(TypeKind.BITS, width=width), decode_var=True))
    source = _read_source(str(options["file"]), options.get("key"))
    operation = parse_instruction_operation(source.text, source=source)
    operation.type_check(symbols, strict=bool(options.get("strict")))
    return 0
