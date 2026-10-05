# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement installed validation and resolution commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from ..progress import ProgressCallback, report_progress
from .common import CliError, CliState, View, load_architecture, load_database


def _xlen_values(value: str) -> tuple[int, ...]:
    return (32, 64) if value == "all" else (int(value),)


def run_validation(
    state: CliState,
    validation: str,
    *,
    progress: ProgressCallback | None = None,
    **options: object,
) -> int:
    from ..architecture import ArchitectureCheckStatus
    from ..configuration import ConfigurationKind
    from ..configuration_diagnostics import format_check_diagnostics
    from ..database import ResolvedDatabase
    from ..encoding import OverlapKind

    if state.view is View.RAW:
        raise CliError("--view raw is only accepted by list and show")
    if validation == "data":
        database = load_database(state, progress=progress)
        assert isinstance(database, ResolvedDatabase)
        report_progress(progress, "validation", "Validating database", completed=0, total=1)
        database.validate(progress=progress)
        report_progress(
            progress,
            "validation",
            "Validating database",
            completed=1,
            total=1,
            finished=True,
        )
        return 0
    config = str(options.get("config", "_"))
    architecture = load_architecture(state, config, progress=progress)
    if validation == "cfg":
        result = architecture.check()
        status = result.status.value
        incomplete = False
        if result.status is ArchitectureCheckStatus.VALID and options.get("strict_partial"):
            incomplete = architecture.kind is not ConfigurationKind.FULL and (
                bool(architecture.parameters_without_values)
                or {item.name for item in architecture.possible_extensions}
                != {item.name for item in architecture.mandatory_extensions}
            )
            if incomplete:
                status = "incomplete"
        print(f"{architecture.name}: {status}")
        for line in format_check_diagnostics(architecture, result):
            print(line, file=__import__("sys").stderr)
        if incomplete or result.status is ArchitectureCheckStatus.UNSAT:
            return 1
        return 0 if result.status is ArchitectureCheckStatus.VALID else 2
    if validation in ("encodings", "csrs"):
        report_progress(progress, "validation", f"Validating {validation}", completed=0, total=1)
        overlaps = (
            architecture.encoding_overlaps(architecture.database.instructions)
            if validation == "encodings"
            else architecture.csr_address_overlaps(architecture.database.csrs)
        )
        selected = [
            overlap
            for overlap in overlaps
            if overlap.xlen in _xlen_values(str(options["xlen"]))
            and overlap.kind is not OverlapKind.ALIAS
        ]
        for overlap in selected:
            suffix = ""
            if validation == "csrs":
                suffix = f" at {overlap.key.space}:{overlap.key.address:#x}"
            print(
                f"RV{overlap.xlen}: {overlap.left.name} conflicts with "
                f"{overlap.right.name}{suffix} ({overlap.kind.value})"
            )
        report_progress(
            progress,
            "validation",
            f"Validating {validation}",
            completed=1,
            total=1,
            finished=True,
        )
        return 1 if selected else 0
    _validate_idl(architecture, progress)
    return 0


def _validate_idl(architecture, progress: ProgressCallback | None) -> None:
    instructions = [
        instruction
        for instruction in architecture.possible_instructions
        if isinstance(instruction.data.get("operation()"), str)
    ]
    csrs = tuple(architecture.possible_csrs)
    total = len(instructions) + len(csrs)
    completed = 0
    xlens = (architecture.configuration.mxlen,) if architecture.configuration.mxlen else (32, 64)
    for instruction in instructions:
        for xlen in xlens:
            architecture.instruction_operation(instruction.name, effective_xlen=xlen)
        completed += 1
        report_progress(
            progress,
            "validation",
            "Type-checking IDL",
            completed=completed,
            total=total,
        )
    for csr in csrs:
        for key, value in csr.data.items():
            if isinstance(key, str) and key.endswith("()") and isinstance(value, str):
                architecture.csr_behavior(
                    csr.name,
                    key,
                    effective_xlen=architecture.configuration.mxlen,
                )
        completed += 1
        report_progress(
            progress,
            "validation",
            "Type-checking IDL",
            completed=completed,
            total=total,
        )
    report_progress(
        progress,
        "validation",
        "Type-checking IDL",
        completed=total,
        total=total,
        finished=True,
    )


def _resolved_contents(database) -> dict[PurePosixPath, bytes]:
    from ..schema import SchemaStore
    from ..serialization import _version_document_schema, dumps_json, dumps_yaml

    store = SchemaStore(database.schemas_root) if database.schemas_root is not None else None
    contents: dict[PurePosixPath, bytes] = {}
    for name in sorted(database.documents):
        path = PurePosixPath(name)
        document = _version_document_schema(database.documents[name], store, source=name)
        contents[path] = dumps_yaml(document, source=name).encode()
    index = sorted(database.documents)
    contents[PurePosixPath("index.yaml")] = dumps_yaml(index, source="index.yaml").encode()
    contents[PurePosixPath("index.json")] = dumps_json(index, source="index.json").encode()
    ownership = {
        "version": 1,
        "documents": {
            path.as_posix(): hashlib.sha256(content).hexdigest()
            for path, content in contents.items()
            if path.suffix in (".yaml", ".yml") and path.name != "index.yaml"
        },
    }
    contents[PurePosixPath(".udb-serialization.json")] = dumps_json(
        ownership, source=".udb-serialization.json"
    ).encode()
    return contents


def _compiled_idl_contents(database) -> dict[PurePosixPath, bytes]:
    from ..idl import parse
    from ..serialization import dumps_yaml

    result: dict[PurePosixPath, bytes] = {}
    for name, source in sorted(database.idl_sources.items()):
        root = "isa" if name.endswith(".isa") else "function_body"
        tree = parse(source.text, root=root, source=source.label).to_h()
        result[PurePosixPath(f"{name}.ast.yaml")] = dumps_yaml(tree, source=source.label).encode()
    return result


def run_resolve(
    state: CliState,
    output: Path,
    *,
    compile_idl: bool,
    check: bool,
    progress: ProgressCallback | None = None,
) -> int:
    from ..database import ResolvedDatabase

    if state.view is View.RAW:
        raise CliError("--view raw is only accepted by list and show")
    database = load_database(state, progress=progress)
    assert isinstance(database, ResolvedDatabase)
    if not check and not compile_idl:
        database.write(output)
        return 0
    expected = _resolved_contents(database)
    compiled = _compiled_idl_contents(database) if compile_idl else {}
    expected.update(compiled)
    drift: list[PurePosixPath] = []
    for relative, content in expected.items():
        target = output.joinpath(*relative.parts)
        if not target.is_file() or target.read_bytes() != content:
            drift.append(relative)
    manifest = output / ".udb-serialization.json"
    if manifest.is_file():
        owned = json.loads(manifest.read_text(encoding="utf-8")).get("documents", {})
        for name in owned:
            relative = PurePosixPath(name)
            if relative not in expected and (output / name).exists():
                drift.append(relative)
    for relative in sorted(set(drift)):
        print(relative.as_posix())
    if check:
        return 1 if drift else 0
    database.write(output)
    for relative, content in compiled.items():
        target = output.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return 0
