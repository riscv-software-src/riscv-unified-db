# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement installed artifact generators."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from ..cli_output import write_generated_source
from ..progress import ProgressCallback, report_progress
from .common import CliError, CliState, View, load_architecture, load_database


def _apply(plan, output: Path, *, check: bool) -> int:
    drift = plan.apply(output, check=check)
    if check:
        for path in drift:
            print(path.as_posix())
    return 1 if check and drift else 0


def _schema_bundle(state: CliState, output: Path, *, check: bool) -> int:
    from ..authoring import AuthoringPlan, GeneratedFile
    from ..database import Database
    from ..schema import SchemaStore
    from ..serialization import SCHEMAS_BASE_URL, dumps_json

    schema_root = state.schema_dir or Database.bundled().schemas_root
    if schema_root is None:
        raise CliError("selected database has no schema directory")
    store = SchemaStore(schema_root)
    outputs = tuple(
        GeneratedFile(
            relative,
            dumps_json(schema, source=relative.as_posix(), sort_keys=False).encode(),
            "schema-bundle",
            (PurePosixPath("schemas", relative.name),),
            0o644,
        )
        for relative, schema in store.resolved_schemas(base_url=SCHEMAS_BASE_URL).items()
    )
    return _apply(AuthoringPlan(outputs), output, check=check)


def _single_file(
    output: Path | None,
    text: str,
    artifact: str,
    *,
    check: bool,
) -> int:
    drift = write_generated_source(
        text,
        output,
        artifact=artifact,
        create_parents=True,
        check=check,
    )
    return 1 if drift else 0


def _generic(
    state: CliState,
    generator: str,
    options: dict[str, object],
    progress: ProgressCallback | None,
) -> int:
    from ..generators.generic_cli import render

    architecture = load_architecture(state, str(options["config"]), progress=progress)
    internal = "go" if generator == "go-encoding" else generator
    arch = options.get("arch") or ("64" if internal == "go" else "both")
    args = SimpleNamespace(
        arch={"32": "RV32", "64": "RV64", "both": "BOTH"}[str(arch)],
        extensions=options.get("extension") or None,
        include_all=bool(options.get("include_all")),
        exception_records=options.get("exception_records"),
        package_name=options.get("package_name"),
        output=options.get("output"),
    )
    report_progress(progress, "generation", f"Generating {generator}", completed=0, total=1)
    text = render(architecture, args, internal)
    report_progress(
        progress,
        "generation",
        f"Generating {generator}",
        completed=1,
        total=1,
        finished=True,
    )
    return _single_file(
        options.get("output"),
        text,
        generator,
        check=bool(options.get("check")),
    )


def _extension_document(
    state: CliState,
    options: dict[str, object],
    progress: ProgressCallback | None,
) -> int:
    from ..authoring import AuthoringPlan, GeneratedFile
    from ..extension_docs.documents import render_extension_document
    from ..extension_docs.model import DocumentOptions, basename_for, select_extensions
    from ..extension_docs.source_assets import source_asset_closure
    from ..extension_docs.xqci import xqci_selectors

    architecture = load_architecture(state, str(options["config"]), progress=progress)
    selectors = list(options.get("extension") or ())
    xqci_version = options.get("xqci_version")
    if xqci_version is not None:
        if selectors:
            raise CliError("--xqci-version cannot be combined with --extension")
        selectors = list(xqci_selectors(architecture.database, str(xqci_version)))
    if not selectors:
        raise CliError("extension-document requires --extension or --xqci-version")
    try:
        today = date.fromisoformat(str(options["date"])) if options.get("date") else None
    except ValueError as error:
        raise CliError(f"invalid --date: {error}") from error
    document_options = DocumentOptions(
        include_implied=bool(options.get("include_implied")),
        include_csr_field_descriptions=not bool(options.get("omit_csr_field_descriptions")),
        basename=options.get("output_basename"),
        revision=str(options.get("revision", "unknown")),
        today=today,
    )
    selections = select_extensions(architecture, selectors)
    basename = basename_for(selections, document_options)
    report_progress(
        progress,
        "extension-document",
        "Generating extension document",
        completed=0,
        total=2,
    )
    text = render_extension_document(
        architecture,
        selectors,
        options=document_options,
        progress=progress,
    )
    report_progress(
        progress,
        "extension-document",
        "Collecting document assets",
        completed=1,
        total=2,
    )
    assets = source_asset_closure(text, supplied=document_options.source_assets)
    outputs = [
        GeneratedFile(
            PurePosixPath(f"{basename}.adoc"),
            text.encode(),
            "extension-document",
            (PurePosixPath("extension-document-input"),),
            0o644,
        )
    ]
    outputs.extend(
        GeneratedFile(
            PurePosixPath(relative.as_posix()),
            content,
            "extension-document",
            (PurePosixPath("extension-document-assets"),),
            0o644,
        )
        for relative, content in sorted(assets.items())
    )
    result = _apply(
        AuthoringPlan(tuple(outputs)),
        options["output"],
        check=bool(options.get("check")),
    )
    report_progress(
        progress,
        "extension-document",
        "Generating extension document",
        completed=2,
        total=2,
        finished=True,
    )
    return result


def _schema_docs(state: CliState, options: dict[str, object]) -> int:
    from ..errors import UdbError
    from ..schema import SchemaStore
    from ..schema_docs import SchemaDocumentation
    from ..serialization import dumps_json

    try:
        store = SchemaStore(state.schema_dir) if state.schema_dir is not None else None
        docs = SchemaDocumentation(store)
        output = options["output"]
        plan = docs.plan(
            output,
            schema=options.get("schema"),
            output_file=options.get("output_file"),
            generate_index=not bool(options.get("no_index")),
        )
        drift = plan.apply(
            output,
            check=bool(options.get("check")),
            replace_current=bool(options.get("replace_current")),
        )
    except (UdbError, OSError, UnicodeError, ValueError, KeyError) as error:
        if options.get("diagnostics"):
            print(
                dumps_json(
                    {
                        "status": "error",
                        "check": bool(options.get("check")),
                        "paths": [],
                        "notices": [],
                        "error": str(error),
                    }
                ),
                end="",
            )
        raise
    if options.get("diagnostics"):
        print(
            dumps_json(
                {
                    "status": ("drift" if options.get("check") else "generated")
                    if drift
                    else "unchanged",
                    "check": bool(options.get("check")),
                    "paths": [path.as_posix() for path in drift],
                    "notices": [asdict(notice) for notice in plan.notices],
                }
            ),
            end="",
        )
    else:
        for path in drift:
            print(path.as_posix() if options.get("check") else f"generated: {path}")
    return 1 if options.get("check") and drift else 0


def _configuration_overlays(configurations, overlays: list[Path]) -> tuple[tuple[Path, ...], ...]:
    """Match declared overlays by basename; otherwise apply all explicit overlays."""

    by_name: dict[str, Path] = {}
    for path in overlays:
        if path.name in by_name:
            raise CliError(f"duplicate --overlay input named {path.name!r}")
        by_name[path.name] = path
    declared = {config.overlay for config in configurations if config.overlay is not None}
    missing = declared - by_name.keys()
    if missing:
        raise CliError("missing --overlay input for " + ", ".join(sorted(missing)))
    if declared and all(config.overlay is not None for config in configurations):
        unused = by_name.keys() - declared
        if unused:
            raise CliError("unused --overlay input: " + ", ".join(sorted(unused)))
    return tuple(
        (by_name[config.overlay],) if config.overlay is not None else tuple(overlays)
        for config in configurations
    )


def _cpp_hart(
    state: CliState,
    options: dict[str, object],
    progress: ProgressCallback | None,
) -> int:
    from ..configuration import Configuration
    from ..cpp_hart import CppHartGenerator, RuntimeResources
    from ..database import Database
    from ..schema import SchemaStore

    selectors = list(options.get("config") or ())
    all_configs = bool(options.get("all_configs"))
    config_dir = options.get("config_dir")
    if bool(selectors) == all_configs:
        raise CliError("select one or more --config values or --all-configs")
    if all_configs:
        if config_dir is None:
            selectors = ["_", "rv32", "rv64"]
        else:
            selectors = [str(path) for path in sorted(Path(config_dir).glob("*.yaml"))]
            if not selectors:
                raise CliError(f"no configuration YAML files found in {config_dir}")
    if any("," in selector for selector in selectors):
        raise CliError("repeat --config instead of using comma-separated values")

    database = (
        Database.from_path(state.database, schemas_path=state.schema_dir)
        if state.database is not None
        else Database.bundled()
    )
    if state.schema_dir is not None and state.database is None:
        database = Database(database.isa_root, schemas_root=state.schema_dir)
    schema_store = SchemaStore(database.schemas_root) if database.schemas_root is not None else None
    configurations = []
    for selector in selectors:
        if selector in {"_", "rv32", "rv64"} and config_dir is None:
            configurations.append(Configuration.builtin(selector))
            continue
        path = Path(selector)
        if config_dir is not None and not path.is_file():
            path = Path(config_dir) / f"{selector}.yaml"
        configurations.append(Configuration.from_file(path, schema_store=schema_store))

    overlay_groups = _configuration_overlays(configurations, state.overlays)
    resolved_databases = {}
    architectures = []
    for configuration, overlays in zip(configurations, overlay_groups, strict=True):
        resolved = resolved_databases.get(overlays)
        if resolved is None:
            resolved = database.resolve(overlays=overlays, progress=progress)
            resolved_databases[overlays] = resolved
        architectures.append(resolved.configure(configuration))

    def cpp_progress(phase: str, current: int, total: int) -> None:
        report_progress(
            progress,
            f"cpp-hart:{phase}",
            f"Generating C++ hart: {phase}",
            completed=current,
            total=total,
            finished=current == total,
        )

    # Generation is currently single-process; accept the stable jobs/progress
    # options while the shared CLI progress callback owns presentation.
    _ = options.get("jobs"), options.get("show_progress")
    generator = CppHartGenerator(
        architectures,
        resources=(
            RuntimeResources.from_path(options["runtime_root"])
            if options.get("runtime_root") is not None
            else None
        ),
        build_name=options.get("build_name"),
        build_type=str(options.get("build_type", "RelWithDebInfo")),
        progress=cpp_progress if progress is not None else None,
    )
    changed = generator.generate(options["output"], check=bool(options.get("check")))
    return 1 if options.get("check") and changed else 0


def run_generation(
    state: CliState,
    generator: str,
    *,
    progress: ProgressCallback | None = None,
    **options: object,
) -> int:
    from ..database import ResolvedDatabase

    if generator == "schema-bundle":
        return _schema_bundle(state, options["output"], check=bool(options.get("check")))
    if generator == "schema-docs":
        if state.database is not None or state.overlays or state.view_option_used:
            raise CliError("generate schema-docs does not accept ISA database options")
        return _schema_docs(state, options)
    if state.view is View.RAW:
        raise CliError("--view raw is only accepted by list and show")
    if generator == "cpp-hart":
        return _cpp_hart(state, options, progress)
    if generator == "profile-configs":
        from ..profile_configs import profile_configuration_plan

        database = load_database(state, progress=progress)
        assert isinstance(database, ResolvedDatabase)
        return _apply(
            profile_configuration_plan(database, options.get("profile") or None),
            options["output"],
            check=bool(options.get("check")),
        )
    if generator in ("c-encoding", "sv-decode", "go-encoding"):
        return _generic(state, generator, options, progress)
    if generator == "extension-document":
        return _extension_document(state, options, progress)
    architecture = load_architecture(state, str(options["config"]), progress=progress)
    if generator == "instruction-table":
        from ..instruction_table import render_instruction_table

        text = render_instruction_table(architecture, file_name=options.get("output"))
        return _single_file(
            options.get("output"),
            text,
            "instruction table",
            check=bool(options.get("check")),
        )
    from ..generators.config_headers import generate_config_header

    language = "c" if generator == "config-c-header" else "svh"
    text = generate_config_header(architecture, language)
    return _single_file(
        options.get("output"),
        text,
        "header",
        check=bool(options.get("check")),
    )
