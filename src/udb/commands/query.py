# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Record queries and configured architecture inspection."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, run_action


class RecordKind(str, Enum):
    CSR = "csr"
    EXCEPTION_CODE = "exception-code"
    EXTENSION = "extension"
    INSTRUCTION = "instruction"
    INSTRUCTION_OPCODE = "instruction-opcode"
    INSTRUCTION_SUBTYPE = "instruction-subtype"
    INSTRUCTION_TYPE = "instruction-type"
    INSTRUCTION_VARIABLE = "instruction-variable"
    INSTRUCTION_VARIABLE_TYPE = "instruction-variable-type"
    INTERRUPT_CODE = "interrupt-code"
    MANUAL = "manual"
    MANUAL_VERSION = "manual-version"
    PARAMETER = "parameter"
    PROFILE = "profile"
    PROFILE_FAMILY = "profile-family"
    PROFILE_RELEASE = "profile-release"
    REGISTER_FILE = "register-file"


class ListFormat(str, Enum):
    NAMES = "names"
    JSON = "json"
    YAML = "yaml"


class RecordFormat(str, Enum):
    JSON = "json"
    YAML = "yaml"


class ParameterFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class Selection(str, Enum):
    CATALOG = "catalog"
    POSSIBLE = "possible"
    MANDATORY = "mandatory"


inspect_app = typer.Typer(
    help="Inspect a configured architecture.",
    epilog="Example: [bold]udb inspect extension I -c rv64[/bold]",
    no_args_is_help=True,
)


def register(app: typer.Typer) -> None:
    """Register query commands on the root application."""

    app.command(
        "list",
        help="List database record names.",
        epilog="Example: [bold]udb list instruction -f json[/bold]",
    )(list_records)
    app.command(
        "show",
        help="Show one complete database record.",
        epilog="Example: [bold]udb show extension Zvkg -f yaml[/bold]",
    )(show_record)
    app.add_typer(inspect_app, name="inspect")


def list_records(
    context: typer.Context,
    kind: RecordKind,
    format_: Annotated[ListFormat, typer.Option("-f", "--format")] = ListFormat.NAMES,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    """List sorted record names in text, JSON, or YAML."""

    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__("udb.commands.query_impl", fromlist=["run_list"]).run_list(
            state, kind.value, format_.value, output, progress=progress
        ),
    )


def show_record(
    context: typer.Context,
    kind: RecordKind,
    name: str,
    format_: Annotated[RecordFormat, typer.Option("-f", "--format")] = RecordFormat.JSON,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    """Show a complete record with stable key order."""

    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__("udb.commands.query_impl", fromlist=["run_show"]).run_show(
            state, kind.value, name, format_.value, output, progress=progress
        ),
    )


@inspect_app.command("extension", help="Show a human-readable extension report.")
def inspect_extension(
    context: typer.Context,
    name: str,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
) -> None:
    _inspect(context, "extension", config=config, name=name)


@inspect_app.command("parameter", help="Show a human-readable parameter report.")
def inspect_parameter(
    context: typer.Context,
    name: str,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
) -> None:
    _inspect(context, "parameter", config=config, name=name)


@inspect_app.command("extensions", help="List possible extensions.")
def inspect_extensions(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    _inspect(context, "extensions", config=config, output=output)


@inspect_app.command("parameters", help="Report configurable parameters.")
def inspect_parameters(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    extension: Annotated[
        list[str] | None,
        typer.Option("-e", "--extension", help="Filter by defining extension; repeatable."),
    ] = None,
    format_: Annotated[
        ParameterFormat,
        typer.Option("-f", "--format"),
    ] = ParameterFormat.TABLE,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    _inspect(
        context,
        "parameters",
        config=config,
        extension=list(extension or ()),
        format=format_.value,
        output=output,
    )


@inspect_app.command("csrs", help="List catalog, possible, or mandatory CSRs.")
def inspect_csrs(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    selection: Annotated[Selection, typer.Option("--selection")] = Selection.CATALOG,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    _inspect(
        context,
        "csrs",
        config=config,
        selection=selection.value,
        output=output,
    )


@inspect_app.command(
    "encoding",
    help="Match a hexadecimal encoding against instruction descriptors.",
    epilog="Example: [bold]udb inspect encoding fff10093 --width 32 --xlen 64[/bold]",
)
def inspect_encoding(
    context: typer.Context,
    encoding: str,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    width: Annotated[int | None, typer.Option("--width", min=16, max=32)] = None,
    xlen: Annotated[int | None, typer.Option("--xlen", min=32, max=64)] = None,
    selection: Annotated[Selection, typer.Option("--selection")] = Selection.CATALOG,
) -> None:
    if width not in (None, 16, 32):
        raise typer.BadParameter("must be 16 or 32", param_hint="--width")
    if xlen not in (None, 32, 64):
        raise typer.BadParameter("must be 32 or 64", param_hint="--xlen")
    _inspect(
        context,
        "encoding",
        config=config,
        encoding=encoding,
        width=width,
        xlen=xlen,
        selection=selection.value,
    )


def _inspect(context: typer.Context, subject: str, *, config: str, **options: object) -> None:
    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__(
            "udb.commands.query_impl", fromlist=["run_inspect"]
        ).run_inspect(state, subject, config, progress=progress, **options),
    )
