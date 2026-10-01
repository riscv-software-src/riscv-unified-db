# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Architecture source authoring commands."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .common import CliState, reject_database_options, run_action


class LayoutCollection(str, Enum):
    STANDARD = "standard"
    QC_IU = "qc-iu"


author_app = typer.Typer(help="Author database source files.", no_args_is_help=True)


def register(app: typer.Typer) -> None:
    app.add_typer(author_app, name="author", rich_help_panel="Authoring")


@author_app.command(
    "layouts",
    help="Generate architecture files from Python-native layout templates.",
    epilog="Example: [bold]udb author layouts --root . --check[/bold]",
)
def author_layouts(
    context: typer.Context,
    root: Annotated[Path, typer.Option("--root")] = Path("."),
    source_root: Annotated[Path | None, typer.Option("--source-root")] = None,
    collection: Annotated[
        list[LayoutCollection] | None,
        typer.Option("--collection"),
    ] = None,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    state = context.ensure_object(CliState)

    def action(progress):
        reject_database_options(state, "author layouts")
        return __import__("udb.commands.author_impl", fromlist=["run_author"]).run_author(
            root,
            source_root=source_root,
            collections=[item.value for item in collection or ()],
            check=check,
            progress=progress,
        )

    run_action(context, action)
