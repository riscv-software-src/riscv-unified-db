# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Validation and deterministic database resolution commands."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, run_action


class XlenSelection(str, Enum):
    RV32 = "32"
    RV64 = "64"
    ALL = "all"


validate_app = typer.Typer(
    help="Validate database and architecture invariants.",
    epilog="Example: [bold]udb validate cfg -c rv64[/bold]",
    no_args_is_help=True,
)


def register(app: typer.Typer) -> None:
    app.add_typer(validate_app, name="validate")
    app.command(
        "resolve",
        help="Write a deterministic resolved YAML database tree.",
        epilog="Example: [bold]udb resolve -o build/resolved[/bold]",
    )(resolve_database)


def _validate(context: typer.Context, kind: str, **options: object) -> None:
    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__(
            "udb.commands.validation_impl", fromlist=["run_validation"]
        ).run_validation(state, kind, progress=progress, **options),
    )


@validate_app.command("data", help="Resolve and schema-validate every selected document.")
def validate_data(context: typer.Context) -> None:
    _validate(context, "data")


@validate_app.command("cfg", help="Check configuration satisfiability and completeness.")
def validate_cfg(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    strict_partial: Annotated[
        bool,
        typer.Option("--strict-partial", help="Require every configurable choice to be fixed."),
    ] = False,
) -> None:
    _validate(context, "cfg", config=config, strict_partial=strict_partial)


@validate_app.command("encodings", help="Report fixed-bit instruction encoding conflicts.")
def validate_encodings(
    context: typer.Context,
    xlen: Annotated[XlenSelection, typer.Option("--xlen")] = XlenSelection.ALL,
) -> None:
    _validate(context, "encodings", config="_", xlen=xlen.value)


@validate_app.command("csrs", help="Report direct and indirect CSR address conflicts.")
def validate_csrs(
    context: typer.Context,
    xlen: Annotated[XlenSelection, typer.Option("--xlen")] = XlenSelection.ALL,
) -> None:
    _validate(context, "csrs", config="_", xlen=xlen.value)


@validate_app.command("idl", help="Parse and type-check available architecture IDL.")
def validate_idl(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
) -> None:
    _validate(context, "idl", config=config)


def resolve_database(
    context: typer.Context,
    output: Annotated[Path, typer.Option("-o", "--output")],
    compile_idl: Annotated[
        bool,
        typer.Option("--compile-idl", help="Serialize global IDL syntax trees beside sources."),
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="Report drift without writing."),
    ] = False,
) -> None:
    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__(
            "udb.commands.validation_impl", fromlist=["run_resolve"]
        ).run_resolve(
            state,
            output,
            compile_idl=compile_idl,
            check=check,
            progress=progress,
        ),
    )
