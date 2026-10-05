# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone ISA Description Language commands."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, reject_database_options, run_action


class IdlRoot(str, Enum):
    ISA = "isa"
    FUNCTION_BODY = "function_body"
    INSTRUCTION_OPERATION = "instruction_operation"
    EXPRESSION = "expression"
    CONSTRAINT_BODY = "constraint_body"
    FOR_LOOP = "for_loop"


class IdlFormat(str, Enum):
    YAML = "yaml"
    JSON = "json"


idl_app = typer.Typer(
    help="Compile, evaluate, and type-check IDL.",
    epilog='Example: [bold]udb idl eval -D XLEN=64 "XLEN / 8"[/bold]',
    no_args_is_help=True,
)
check_app = typer.Typer(help="Type-check standalone IDL.", no_args_is_help=True)


def register(app: typer.Typer) -> None:
    idl_app.add_typer(check_app, name="check")
    app.add_typer(idl_app, name="idl")


def _run(context: typer.Context, command: str, **options: object) -> None:
    state = context.ensure_object(CliState)

    def action(progress):
        del progress
        reject_database_options(state, f"idl {command}")
        return __import__("udb.commands.idl_impl", fromlist=["run_idl"]).run_idl(command, **options)

    run_action(context, action)


@idl_app.command(
    "compile",
    help="Parse IDL and serialize its syntax tree.",
    epilog="Example: [bold]udb idl compile functions.isa -f json[/bold]",
)
def compile_idl(
    context: typer.Context,
    file: str,
    root: Annotated[IdlRoot, typer.Option("--root")] = IdlRoot.ISA,
    format_: Annotated[IdlFormat, typer.Option("-f", "--format")] = IdlFormat.YAML,
    output: Annotated[Path, typer.Option("-o", "--output")] = Path("-"),
) -> None:
    _run(
        context,
        "compile",
        file=file,
        root=root.value,
        format=format_.value,
        output=output,
    )


@idl_app.command("eval", help="Evaluate a standalone 64-bit IDL expression.")
def evaluate_idl(
    context: typer.Context,
    expression: str,
    define: Annotated[
        list[str] | None,
        typer.Option("-D", "--define", help="Define NAME=EXPR; repeatable."),
    ] = None,
    output: Annotated[Path, typer.Option("-o", "--output")] = Path("-"),
) -> None:
    _run(
        context,
        "eval",
        expression=expression,
        define=list(define or ()),
        output=output,
    )


@check_app.command("instruction", help="Type-check one instruction operation.")
def check_instruction(
    context: typer.Context,
    file: str,
    define: Annotated[
        list[str] | None,
        typer.Option("-D", "--define", help="Define NAME=EXPR; repeatable."),
    ] = None,
    var: Annotated[
        list[str] | None,
        typer.Option("-d", "--var", help="Declare decode variable NAME=WIDTH; repeatable."),
    ] = None,
    key: Annotated[str | None, typer.Option("--key")] = None,
    strict: Annotated[bool, typer.Option("--strict")] = False,
) -> None:
    _run(
        context,
        "check instruction",
        file=file,
        define=list(define or ()),
        var=list(var or ()),
        key=key,
        strict=strict,
    )
