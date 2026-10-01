# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone parsing, evaluation and instruction checking with the Python IDL API."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..cli_output import write_generated_source
from ..errors import UdbError
from ..idl_yaml_source import idl_field_source
from ..source import parse_yaml
from . import ROOTS, parse, parse_expression, parse_instruction_operation
from .errors import IdlError, IdlInternalError
from .source import IdlSource
from .symbols import IdlEnvironment, SymbolTable, Var
from .types import Type, TypeKind


class CliInputError(ValueError):
    """An invalid standalone compiler input or option."""


@dataclass(frozen=True)
class _XRegisters:
    name: str = "X"
    register_length: str = "return 64;"
    registers: tuple[str, ...] = tuple(f"x{index}" for index in range(32))


def _binding(text: str) -> tuple[str, str]:
    name, separator, value = text.partition("=")
    if not separator or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or not value:
        raise argparse.ArgumentTypeError("expected an IDL identifier followed by =VALUE")
    return name, value


def _decode_binding(text: str) -> tuple[str, int]:
    name, value = _binding(text)
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise argparse.ArgumentTypeError("decode width must be a positive decimal integer")
    return name, int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m udb.idl.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    compile_parser = commands.add_parser("compile", help="parse IDL and serialize its syntax tree")
    compile_parser.add_argument("file", help="UTF-8 input file, or - for stdin")
    compile_parser.add_argument("-r", "--root", choices=ROOTS, default="isa")
    compile_parser.add_argument("-f", "--format", choices=("yaml", "json"), default="yaml")
    compile_parser.add_argument("-o", "--output", default="-")
    eval_parser = commands.add_parser("eval", help="evaluate a standalone IDL expression")
    eval_parser.add_argument("expression")
    eval_parser.add_argument("-o", "--output", default="-")
    check_parser = commands.add_parser("tc", help="type-check IDL")
    check_commands = check_parser.add_subparsers(dest="scope", required=True)
    inst_parser = check_commands.add_parser("inst", help="type-check an instruction operation")
    inst_parser.add_argument("file", help="UTF-8 IDL/YAML file, or - for stdin")
    inst_parser.add_argument("-k", "--key", help="extract a string field from a YAML mapping")
    inst_parser.add_argument("-s", "--strict", action="store_true")
    inst_parser.add_argument("-d", "--var", action="append", type=_decode_binding, default=[])
    for command in (eval_parser, inst_parser):
        command.add_argument("-D", "--define", action="append", type=_binding, default=[])
    return parser


def _symbols(definitions: Sequence[tuple[str, str]]) -> SymbolTable:
    symbols = SymbolTable(IdlEnvironment(register_files=(_XRegisters(),)))
    for name, value in dict(definitions).items():
        expression = parse_expression(value, label=f"<define {name}>")
        expression.type_check(symbols, strict=False)
        symbols.add_unique(name, Var(name, expression.type(symbols), expression.value(symbols)))
    return symbols


def _read_source(path: str, key: str | None = None) -> IdlSource:
    if path == "-":
        raw = getattr(sys.stdin, "buffer", sys.stdin).read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    else:
        text = Path(path).read_bytes().decode("utf-8")
    if key is None:
        return IdlSource(text, path)
    try:
        parsed = parse_yaml(text, source=path)
    except YAMLError as error:
        raise CliInputError(f"{path}: invalid YAML: {error}") from error
    if not isinstance(parsed.value, Mapping) or key not in parsed.value:
        raise CliInputError(f"{path}: no YAML field {key!r}")
    value = parsed.value[key]
    if not isinstance(value, str):
        raise CliInputError(f"{path}: YAML field {key!r} must contain an IDL string")
    span = parsed.sources[(key,)]
    single_line_plain = span.style is None and span.start_line == span.end_line
    if single_line_plain or span.style == "|" or value == "":
        return idl_field_source(text, span, value, label=path)
    # Reflowed scalars have snippet coordinates, explicitly not enclosing-file coordinates.
    return IdlSource(value, f"{path} [{key}: decoded YAML scalar]")


def _value_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return "".join(_value_text(element) for element in value)
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (str, int)):
        text = str(value)
    else:
        raise IdlInternalError(f"Cannot print IDL value of type {type(value).__name__}")
    return text if text.endswith("\n") else text + "\n"


def _compile_text(source: IdlSource, root: str, format_: str) -> str:
    tree = parse(source.text, root=root, source=source).to_h()
    if format_ == "json":
        return json.dumps(tree, indent=2, ensure_ascii=False) + "\n"
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.explicit_start = True
    output = io.StringIO()
    yaml.dump(tree, output)
    return output.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            text = _compile_text(_read_source(args.file), args.root, args.format)
        elif args.command == "eval":
            symbols = _symbols(args.define)
            expression = parse_expression(args.expression, label="<expression>")
            expression.type_check(symbols, strict=False)
            text = _value_text(expression.value(symbols))
        else:
            symbols = _symbols(args.define)
            symbols.push(None)
            for name, width in dict(args.var).items():
                symbols.add_unique(
                    name, Var(name, Type(TypeKind.BITS, width=width), decode_var=True)
                )
            source = _read_source(args.file, args.key)
            operation = parse_instruction_operation(source.text, source=source)
            operation.type_check(symbols, strict=args.strict)
            return 0
        output = None if args.output == "-" else Path(args.output)
        write_generated_source(text, output, artifact="IDL output")
        return 0
    except (IdlError, UdbError, CliInputError, OSError, UnicodeError) as error:
        print(f"{parser.prog}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
