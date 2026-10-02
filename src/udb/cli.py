# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Root application for the installed ``udb`` command."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from typer._click.core import ParameterSource

from .commands import author, generation, idl, query, render, validation
from .commands.common import CliState, View, print_error, version_callback

_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="udb",
    help="Explore, validate, and generate artifacts from the RISC-V Unified Database.",
    epilog=(
        "Examples: [bold]udb list extension[/bold] · "
        "[bold]udb inspect encoding fff10093 --width 32[/bold] · "
        "[bold]udb generate instruction-table[/bold]"
    ),
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    context_settings=_CONTEXT_SETTINGS,
)


@app.callback()
def root(
    context: typer.Context,
    database: Annotated[
        Path | None,
        typer.Option(
            "--database",
            help="Explicit ISA database root; defaults to bundled standard ISA data.",
        ),
    ] = None,
    schema_dir: Annotated[
        Path | None,
        typer.Option(
            "--schema-dir",
            help="Schema directory for an explicit database or schema command.",
        ),
    ] = None,
    overlay: Annotated[
        list[Path] | None,
        typer.Option("--overlay", help="ISA overlay directory; repeat in precedence order."),
    ] = None,
    view: Annotated[
        View,
        typer.Option("--view", help="Record view for list and show."),
    ] = View.RESOLVED,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Disable progress rendering."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Show tracebacks for unexpected internal errors."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Print the installed package version and exit.",
        ),
    ] = False,
) -> None:
    """Set options shared by commands that consume ISA data."""

    del version
    context.obj = CliState(
        database=database,
        schema_dir=schema_dir,
        overlays=list(overlay or ()),
        view=view,
        quiet=quiet,
        debug=debug,
        database_options_used=database is not None or schema_dir is not None or bool(overlay),
        view_option_used=context.get_parameter_source("view") is ParameterSource.COMMANDLINE,
    )


for command_module in (query, validation, idl, generation, author, render):
    command_module.register(app)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed command and return its normalized status."""

    from typer._click.exceptions import ClickException

    try:
        result = app(
            args=None if argv is None else list(argv),
            prog_name="udb",
            standalone_mode=False,
        )
        return int(result or 0)
    except ClickException as error:
        print_error(error.format_message())
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
