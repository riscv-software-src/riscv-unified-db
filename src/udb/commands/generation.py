# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Installed source and documentation generators."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, run_action


class ArchSelection(str, Enum):
    RV32 = "32"
    RV64 = "64"
    BOTH = "both"


generate_app = typer.Typer(
    help="Generate deterministic source and documentation artifacts.",
    epilog="Example: [bold]udb generate config-c-header -c rv64 -o config.h[/bold]",
    no_args_is_help=True,
)


def register(app: typer.Typer) -> None:
    app.add_typer(generate_app, name="generate")


def _run(context: typer.Context, generator: str, **options: object) -> None:
    state = context.ensure_object(CliState)
    run_action(
        context,
        lambda progress: __import__(
            "udb.commands.generation_impl", fromlist=["run_generation"]
        ).run_generation(state, generator, progress=progress, **options),
    )


@generate_app.command("schema-bundle", help="Write versioned resolved JSON Schemas.")
def schema_bundle(
    context: typer.Context,
    output: Annotated[Path, typer.Option("-o", "--output")],
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _run(context, "schema-bundle", output=output, check=check)


@generate_app.command("profile-configs", help="Write solver-expanded profile configurations.")
def profile_configs(
    context: typer.Context,
    output: Annotated[Path, typer.Option("-o", "--output")],
    profile: Annotated[list[str] | None, typer.Option("--profile")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _run(
        context,
        "profile-configs",
        output=output,
        profile=list(profile or ()),
        check=check,
    )


def _config_header(
    context: typer.Context,
    generator: str,
    config: str,
    output: Path | None,
    check: bool,
) -> None:
    _run(context, generator, config=config, output=output, check=check)


@generate_app.command("config-c-header", help="Generate a fully configured C header.")
def config_c_header(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _config_header(context, "config-c-header", config, output, check)


@generate_app.command("config-sv-header", help="Generate a fully configured SystemVerilog header.")
def config_sv_header(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _config_header(context, "config-sv-header", config, output, check)


def _generic(
    context: typer.Context,
    generator: str,
    *,
    config: str,
    output: Path | None,
    check: bool,
    arch: ArchSelection | None,
    extension: list[str] | None,
    include_all: bool,
    exception_records: Path | None = None,
    package_name: str | None = None,
) -> None:
    _run(
        context,
        generator,
        config=config,
        output=output,
        check=check,
        arch=None if arch is None else arch.value,
        extension=list(extension or ()),
        include_all=include_all,
        exception_records=exception_records,
        package_name=package_name,
    )


@generate_app.command("c-encoding", help="Generate generic C encoding definitions.")
def c_encoding(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
    arch: Annotated[ArchSelection | None, typer.Option("--arch")] = None,
    extension: Annotated[list[str] | None, typer.Option("-e", "--extension")] = None,
    include_all: Annotated[bool, typer.Option("--include-all")] = False,
    exception_records: Annotated[
        Path | None,
        typer.Option("--exception-records"),
    ] = None,
) -> None:
    _generic(
        context,
        "c-encoding",
        config=config,
        output=output,
        check=check,
        arch=arch,
        extension=extension,
        include_all=include_all,
        exception_records=exception_records,
    )


@generate_app.command("sv-decode", help="Generate a SystemVerilog decode package.")
def sv_decode(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
    arch: Annotated[ArchSelection | None, typer.Option("--arch")] = None,
    extension: Annotated[list[str] | None, typer.Option("-e", "--extension")] = None,
    include_all: Annotated[bool, typer.Option("--include-all")] = False,
    exception_records: Annotated[
        Path | None,
        typer.Option("--exception-records"),
    ] = None,
    package_name: Annotated[str | None, typer.Option("--package-name")] = None,
) -> None:
    _generic(
        context,
        "sv-decode",
        config=config,
        output=output,
        check=check,
        arch=arch,
        extension=extension,
        include_all=include_all,
        exception_records=exception_records,
        package_name=package_name,
    )


@generate_app.command("go-encoding", help="Generate Go instruction encodings.")
def go_encoding(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
    arch: Annotated[ArchSelection | None, typer.Option("--arch")] = None,
    extension: Annotated[list[str] | None, typer.Option("-e", "--extension")] = None,
    include_all: Annotated[bool, typer.Option("--include-all")] = False,
) -> None:
    _generic(
        context,
        "go-encoding",
        config=config,
        output=output,
        check=check,
        arch=arch,
        extension=extension,
        include_all=include_all,
    )


@generate_app.command("instruction-table", help="Generate the complete instruction table.")
def instruction_table(
    context: typer.Context,
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _run(
        context,
        "instruction-table",
        config=config,
        output=output,
        check=check,
    )


@generate_app.command(
    "extension-document",
    help="Generate standalone extension AsciiDoc and required assets.",
    epilog=("Example: [bold]udb generate extension-document -e Zba -o build/Zba[/bold]"),
)
def extension_document(
    context: typer.Context,
    output: Annotated[Path, typer.Option("-o", "--output")],
    config: Annotated[str, typer.Option("-c", "--config")] = "_",
    extension: Annotated[list[str] | None, typer.Option("-e", "--extension")] = None,
    xqci_version: Annotated[str | None, typer.Option("--xqci-version")] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
    output_basename: Annotated[str | None, typer.Option("--output-basename")] = None,
    include_implied: Annotated[bool, typer.Option("--include-implied")] = False,
    omit_csr_field_descriptions: Annotated[
        bool,
        typer.Option("--omit-csr-field-descriptions"),
    ] = False,
    revision: Annotated[str, typer.Option("--revision")] = "unknown",
    date_: Annotated[str | None, typer.Option("--date")] = None,
) -> None:
    _run(
        context,
        "extension-document",
        config=config,
        extension=list(extension or ()),
        xqci_version=xqci_version,
        output=output,
        check=check,
        output_basename=output_basename,
        include_implied=include_implied,
        omit_csr_field_descriptions=omit_csr_field_descriptions,
        revision=revision,
        date=date_,
    )


@generate_app.command("schema-docs", help="Generate versioned schema documentation.")
def schema_docs(
    context: typer.Context,
    output: Annotated[Path, typer.Option("-o", "--output")],
    schema: Annotated[str | None, typer.Option("--schema")] = None,
    output_file: Annotated[str | None, typer.Option("--output-file")] = None,
    no_index: Annotated[bool, typer.Option("--no-index")] = False,
    replace_current: Annotated[bool, typer.Option("--replace-current")] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics")] = False,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    _run(
        context,
        "schema-docs",
        output=output,
        schema=schema,
        output_file=output_file,
        no_index=no_index,
        replace_current=replace_current,
        diagnostics=diagnostics,
        check=check,
    )
