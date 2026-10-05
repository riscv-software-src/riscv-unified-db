# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement record queries and configured reports."""

from __future__ import annotations

from pathlib import Path

from ..cli_output import write_generated_source
from ..progress import ProgressCallback
from .common import CliError, CliState, View, load_architecture, load_database

_INTERNAL_KIND = {
    "exception-code": "exception_code",
    "instruction-opcode": "instruction_opcode",
    "instruction-subtype": "instruction_subtype",
    "instruction-type": "instruction_type",
    "instruction-variable": "instruction_variable",
    "instruction-variable-type": "instruction_variable_type",
    "interrupt-code": "interrupt_code",
    "manual-version": "manual version",
    "profile-family": "profile family",
    "profile-release": "profile release",
    "register-file": "register_file",
}


def _kind(value: str) -> str:
    return _INTERNAL_KIND.get(value, value)


def run_list(
    state: CliState,
    kind: str,
    format_: str,
    output: Path | None,
    *,
    progress: ProgressCallback | None = None,
) -> int:
    from ..serialization import dumps_json, dumps_yaml

    database = load_database(state, resolve=state.view is View.RESOLVED, progress=progress)
    names = sorted(record.name for record in database.objects(_kind(kind)))
    if format_ == "names":
        text = "".join(f"{name}\n" for name in names)
    elif format_ == "json":
        text = dumps_json(names)
    else:
        text = dumps_yaml(names)
    write_generated_source(text, output, artifact=f"{kind} list", create_parents=True)
    return 0


def run_show(
    state: CliState,
    kind: str,
    name: str,
    format_: str,
    output: Path | None,
    *,
    progress: ProgressCallback | None = None,
) -> int:
    from ..serialization import dumps_json, dumps_yaml

    database = load_database(state, resolve=state.view is View.RESOLVED, progress=progress)
    value = database.get(_kind(kind), name).to_dict()
    text = dumps_json(value, sort_keys=False) if format_ == "json" else dumps_yaml(value)
    write_generated_source(text, output, artifact=f"{kind} record", create_parents=True)
    return 0


def run_inspect(
    state: CliState,
    subject: str,
    config: str,
    *,
    progress: ProgressCallback | None = None,
    **options: object,
) -> int:
    from ..query_reports.formatting import ReportError
    from ..query_reports.matching import InstructionMatcher, parse_encoding
    from ..query_reports.reports import (
        ReportBuilder,
        render_extension,
        render_names,
        render_parameter,
    )

    if state.view is View.RAW:
        raise CliError("--view raw is only accepted by list and show")
    architecture = load_architecture(state, config, progress=progress)
    builder = ReportBuilder(architecture)
    try:
        if subject == "extension":
            name = str(options["name"])
            text = render_extension(builder.extension(name), name)
        elif subject == "parameter":
            name = str(options["name"])
            text = render_parameter(builder.parameter(name), name)
        elif subject == "extensions":
            text = render_names(builder.extensions())
        elif subject == "parameters":
            extensions = options.get("extension") or None
            report = builder.parameters(extensions)
            format_ = str(options["format"])
            text = report.render("ascii" if format_ == "table" else format_)
        elif subject == "csrs":
            text = render_names(builder.csrs(selection=str(options["selection"])))
        else:
            encoding = str(options["encoding"])
            parse_encoding(encoding)
            result = InstructionMatcher(architecture).match(
                encoding,
                width=options.get("width"),
                xlen=options.get("xlen"),
                selection=str(options["selection"]),
            )
            text = result.render()
            if not any(item.matches for item in result.results):
                write_generated_source(text, None, artifact="encoding report")
                return 1
    except ReportError as error:
        raise CliError(str(error), 1) from error
    output = options.get("output")
    write_generated_source(
        text,
        output if isinstance(output, Path) else None,
        artifact=f"{subject} report",
        create_parents=True,
    )
    if subject in ("extension", "parameter") and text.startswith("Could not find "):
        return 1
    return 0
