# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Installed rendering commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, reject_database_options, run_action

render_app = typer.Typer(help="Render generated source artifacts.", no_args_is_help=True)


def register(app: typer.Typer) -> None:
    app.add_typer(render_app, name="render", rich_help_panel="Rendering")


@render_app.command(
    "pdf",
    help="Render one AsciiDoc input with the official asciidoctor-pdf toolchain.",
    epilog="Example: [bold]udb render pdf Zba.adoc -o Zba.pdf[/bold]",
)
def render_pdf(
    context: typer.Context,
    input: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    theme: Annotated[Path | None, typer.Option("--theme")] = None,
    fonts: Annotated[Path | None, typer.Option("--fonts")] = None,
    images: Annotated[Path | None, typer.Option("--images")] = None,
    qc_theme: Annotated[bool, typer.Option("--qc-theme")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0.001)] = 600,
) -> None:
    state = context.ensure_object(CliState)

    def action(progress):
        reject_database_options(state, "render pdf")
        return __import__("udb.commands.render_impl", fromlist=["run_render"]).run_render(
            input,
            output,
            theme=theme,
            fonts=fonts,
            images=images,
            qc_theme=qc_theme,
            timeout=timeout,
            progress=progress,
        )

    run_action(context, action)
