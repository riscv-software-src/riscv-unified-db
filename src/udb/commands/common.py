# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Shared database, configuration, progress, and error handling."""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ..progress import ProgressCallback, ProgressEvent, report_progress

if TYPE_CHECKING:
    from ..configuration import Configuration
    from ..database import Database, ResolvedDatabase


class View(str, Enum):
    """Available record views."""

    RAW = "raw"
    RESOLVED = "resolved"


@dataclass(slots=True)
class CliState:
    """Global installed-command options."""

    database: Path | None = None
    schema_dir: Path | None = None
    overlays: list[Path] = field(default_factory=list)
    view: View = View.RESOLVED
    quiet: bool = False
    debug: bool = False
    database_options_used: bool = False
    view_option_used: bool = False


class CliError(Exception):
    """A diagnosed command failure with a stable installed-CLI exit status."""

    def __init__(self, message: str, status: int = 2) -> None:
        super().__init__(message)
        self.status = status


class ExternalToolError(CliError):
    """A required external program failed or is unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 3)


def package_version() -> str:
    """Return the installed distribution version."""

    try:
        return version("udb")
    except PackageNotFoundError:
        return "0.1.0a0"


def version_callback(value: bool) -> None:
    """Print the package version for Typer's eager root option."""

    if value:
        typer.echo(f"udb {package_version()}")
        raise typer.Exit()


def reject_database_options(state: CliState, command: str) -> None:
    """Reject irrelevant root options rather than silently ignoring them."""

    if state.database_options_used:
        raise CliError(f"{command} does not accept database options")
    if state.view_option_used:
        raise CliError(f"{command} does not accept --view")


class _RichProgressRenderer:
    """Translate library progress events into one Rich progress display."""

    def __init__(self) -> None:
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        self._tasks: dict[str, int] = {}
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=Console(stderr=True),
            transient=True,
        )
        self._progress.start()

    def __call__(self, event: ProgressEvent) -> None:
        task_id = self._tasks.get(event.task)
        if task_id is None:
            task_id = self._progress.add_task(event.description, total=event.total)
            self._tasks[event.task] = task_id
        values: dict[str, Any] = {"description": event.description}
        if event.total is not None:
            values["total"] = event.total
        if event.completed is not None:
            values["completed"] = event.completed
        self._progress.update(task_id, **values)
        if event.finished:
            self._progress.update(task_id, completed=event.total)
            self._progress.stop_task(task_id)

    def close(self) -> None:
        self._progress.stop()


def _progress_enabled(state: CliState) -> bool:
    return (
        not state.quiet
        and sys.stderr.isatty()
        and os.environ.get("TERM") != "dumb"
        and "NO_COLOR" not in os.environ
    )


@contextmanager
def progress_renderer(state: CliState) -> Iterator[ProgressCallback | None]:
    """Yield the CLI progress callback, importing Rich only for an eligible TTY."""

    if not _progress_enabled(state):
        yield None
        return
    renderer = _RichProgressRenderer()
    try:
        yield renderer
    finally:
        renderer.close()


def print_error(message: str) -> None:
    """Write one styled diagnostic line to stderr."""

    color = (
        sys.stderr.isatty() and os.environ.get("TERM") != "dumb" and "NO_COLOR" not in os.environ
    )
    typer.secho(f"Error: {message}", err=True, fg=typer.colors.RED if color else None)


def run_action(
    context: typer.Context,
    action: Callable[[ProgressCallback | None], int | None],
) -> None:
    """Run a command with common progress and exit-code normalization."""

    state = context.ensure_object(CliState)
    try:
        with progress_renderer(state) as progress:
            result = action(progress)
    except CliError as error:
        print_error(str(error))
        raise typer.Exit(error.status) from error
    except Exception as error:
        from ..errors import UdbError
        from ..idl.errors import IdlError

        if isinstance(error, (IdlError, UdbError, OSError, UnicodeError, ValueError, KeyError)):
            print_error(str(error))
            raise typer.Exit(2) from error
        print_error(f"internal error: {error}")
        if state.debug or os.environ.get("UDB_DEBUG") == "1":
            traceback.print_exc()
        raise typer.Exit(4) from error
    if result:
        raise typer.Exit(result)


def load_database(
    state: CliState,
    *,
    resolve: bool = True,
    progress: ProgressCallback | None = None,
) -> Database:
    """Load the selected database without checkout discovery."""

    from ..database import Database

    report_progress(progress, "database", "Loading database", completed=0, total=2)
    database = (
        Database.from_path(state.database, schemas_path=state.schema_dir)
        if state.database is not None
        else Database.bundled()
    )
    if state.schema_dir is not None and state.database is None:
        database = Database(database.isa_root, schemas_root=state.schema_dir)
    report_progress(progress, "database", "Loading database", completed=1, total=2)
    if not resolve:
        if state.overlays:
            raise CliError("--overlay is invalid with --view raw")
        report_progress(
            progress,
            "database",
            "Loading database",
            completed=2,
            total=2,
            finished=True,
        )
        return database
    resolved = database.resolve(overlays=state.overlays, progress=progress)
    report_progress(
        progress,
        "database",
        "Resolving database",
        completed=2,
        total=2,
        finished=True,
    )
    return resolved


def load_configuration(
    selector: str,
    *,
    database: ResolvedDatabase | None = None,
) -> Configuration:
    """Load a bundled or explicit configuration."""

    from ..configuration import Configuration
    from ..schema import SchemaStore

    if selector in ("_", "rv32", "rv64"):
        return Configuration.builtin(selector)
    schema_store = None
    if database is not None and database.schemas_root is not None:
        schema_store = SchemaStore(database.schemas_root)
    return Configuration.from_file(selector, schema_store=schema_store)


def load_architecture(
    state: CliState,
    selector: str,
    *,
    progress: ProgressCallback | None = None,
):
    """Resolve and configure the selected architecture once."""

    from ..database import ResolvedDatabase

    database = load_database(state, progress=progress)
    assert isinstance(database, ResolvedDatabase)
    configuration = load_configuration(selector, database=database)
    declaration = configuration.to_dict().get("arch_overlay")
    if declaration is not None:
        declared = Path(str(declaration))
        if not any(overlay.name == declared.name for overlay in state.overlays):
            raise CliError(
                f"configuration declares arch_overlay {declared}; "
                f"supply --overlay with basename {declared.name!r}"
            )
    report_progress(progress, "configuration", "Configuring architecture", completed=0, total=1)
    architecture = database.configure(configuration)
    report_progress(
        progress,
        "configuration",
        "Configuring architecture",
        completed=1,
        total=1,
        finished=True,
    )
    return architecture
